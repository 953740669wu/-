"""Original encoder mean/AdamW arithmetic, isolated val RNG, and exact recovery."""
import hashlib
from pathlib import Path
import random


def optimizer(torch,model):
    return torch.optim.AdamW(model.parameters(),lr=1e-4,betas=(0.9,0.999),eps=1e-8,weight_decay=0.01)


def tensor(torch,array):
    import numpy as np
    value=np.ascontiguousarray(array,dtype=np.float32)
    return torch.frombuffer(bytearray(value.tobytes()),dtype=torch.float32).reshape(value.shape)


def batch(torch,part,indices,angles):
    v=tensor(torch,part['v'][indices]);image=tensor(torch,part['y0'][indices])
    return v,image,angles.expand(len(indices),208,4),torch.zeros(len(indices),208)


def losses(torch,model,v,image,angles,belt,mask):
    F=torch.nn.functional
    h=model(v,angles,belt,mask)
    voltage=F.mse_loss(model.head_v(h)[...,0][mask],v[mask])
    coarse=F.mse_loss(model.head_coarse(h.mean(1)),F.adaptive_avg_pool2d(image,16).flatten(1))
    return voltage+coarse,voltage,coarse


def train_step(torch,model,opt,values,mask):
    v,image,angles,belt=values
    v.requires_grad_();image.requires_grad_()
    opt.zero_grad(set_to_none=True)
    total,voltage,coarse=losses(torch,model,v,image,angles,belt,mask)
    opt.zero_grad()
    total.backward();opt.step()
    return dict(total=total.detach(),voltage=voltage.detach(),coarse=coarse.detach())


def validate_update(torch,model,opt,values,step):
    for name,p in model.named_parameters():
        if p.grad is None or not torch.isfinite(p).all() or not torch.isfinite(p.grad).all():
            raise ValueError('missing/nonfinite encoder gradient/parameter: '+name)
        state=opt.state[p]
        if set(state)!={'step','exp_avg','exp_avg_sq'} or state['step'].item()!=step:
            raise ValueError('AdamW state/step mismatch: '+name)
        if any(not torch.isfinite(v).all() for v in state.values()):raise ValueError('nonfinite AdamW state')
    if any(v.grad is None or not torch.isfinite(v.grad).all() for v in values[:2]):
        raise ValueError('missing/nonfinite input gradient')


def evaluate(torch,model,part,batch_size,angles):
    if part is None:return dict(status='VAL_NOT_RUN_NO_FORMAL_VAL')
    rng=torch.get_rng_state().clone();generator=torch.Generator().manual_seed(1000003)
    training=model.training;fastpath=torch.backends.mha.get_fastpath_enabled()
    mask_digest=hashlib.sha256();voltage_sum=coarse_sum=0.;masked=frames=0
    try:
        model.eval()
        # Preserve the already validated F.linear/KML + native SDPA path in eval.
        torch.backends.mha.set_fastpath_enabled(False)
        with torch.no_grad():
            for start in range(0,len(part['v']),batch_size):
                indices=list(range(start,min(start+batch_size,len(part['v']))))
                v,image,a,belt=batch(torch,part,indices,angles)
                mask=torch.rand(v.shape,generator=generator)<0.5
                if not mask.any():raise ValueError('empty validation mask; no resampling')
                mask_digest.update(mask.numpy().tobytes())
                h=model(v,a,belt,mask);pv=model.head_v(h)[...,0];pc=model.head_coarse(h.mean(1))
                vs=torch.nn.functional.mse_loss(pv[mask],v[mask],reduction='sum')
                cs=torch.nn.functional.mse_loss(pc,torch.nn.functional.adaptive_avg_pool2d(image,16).flatten(1),reduction='sum')
                if not torch.isfinite(vs+cs):raise ValueError('nonfinite validation loss')
                voltage_sum+=vs.item();coarse_sum+=cs.item();masked+=int(mask.sum());frames+=len(indices)
    finally:
        torch.backends.mha.set_fastpath_enabled(fastpath);model.train(training)
    if not torch.equal(rng,torch.get_rng_state()):raise ValueError('validation changed training RNG')
    voltage=voltage_sum/masked;coarse=coarse_sum/(frames*256)
    return dict(status='FORMAL_VAL_ONLY',frames=frames,masked_elements=masked,voltage=voltage,coarse=coarse,
                total=voltage+coarse,mask_sha256=mask_digest.hexdigest(),training_rng_unchanged=True,
                aggregation='sum squared errors / global component denominator',eval_fastpath=False)


def rng_state(torch):
    import numpy as np
    algorithm,keys,position,has_gauss,cached=np.random.get_state()
    return dict(torch=torch.get_rng_state().clone(),python=random.getstate(),
        numpy=dict(algorithm=algorithm,keys=keys.tolist(),position=position,has_gauss=has_gauss,cached=cached))


def restore_rng(torch,value):
    import numpy as np
    torch.set_rng_state(value['torch']);random.setstate(value['python'])
    n=value['numpy'];np.random.set_state((n['algorithm'],np.array(n['keys'],dtype=np.uint32),n['position'],n['has_gauss'],n['cached']))


def exact(torch,left,right):
    if isinstance(left,torch.Tensor):return isinstance(right,torch.Tensor) and left.dtype==right.dtype and left.shape==right.shape and torch.equal(left,right)
    if isinstance(left,dict):return isinstance(right,dict) and set(left)==set(right) and all(exact(torch,left[k],right[k]) for k in left)
    if isinstance(left,(list,tuple)):return type(left)==type(right) and len(left)==len(right) and all(exact(torch,a,b) for a,b in zip(left,right))
    return type(left)==type(right) and left==right


def model_sha(model):
    digest=hashlib.sha256()
    for name,value in model.state_dict().items():
        digest.update(name.encode());digest.update(value.detach().contiguous().numpy().tobytes())
    return digest.hexdigest()


def save_checkpoint(torch,path,model,opt,identity,progress,normalization):
    if path.exists():raise ValueError('refuse existing checkpoint')
    path.parent.mkdir(parents=True,exist_ok=True)
    temporary=path.with_suffix('.tmp')
    if temporary.exists():raise ValueError('refuse stale checkpoint temporary file')
    payload=dict(protocol='REAL_CORPUS_PILOT_V1',identity=identity,progress=progress,normalization=normalization,
                 model=model.state_dict(),optimizer=opt.state_dict(),rng=rng_state(torch))
    torch.save(payload,temporary);temporary.replace(path)
    from real_data import sha
    return dict(path=str(path.resolve()),bytes=path.stat().st_size,sha256=sha(path))


def probe(torch,model,values):
    v,image,angles,belt=values
    generator=torch.Generator().manual_seed(8102026)
    mask=torch.rand(v.shape,generator=generator)<0.5
    training=model.training;fastpath=torch.backends.mha.get_fastpath_enabled()
    try:
        model.eval();torch.backends.mha.set_fastpath_enabled(False)
        with torch.no_grad():
            h=model(v,angles,belt,mask)
            return dict(h=h.clone(),voltage=model.head_v(h)[...,0].clone(),coarse=model.head_coarse(h.mean(1)).clone())
    finally:
        torch.backends.mha.set_fastpath_enabled(fastpath);model.train(training)


def verify_restore(torch,checkpoint,model,opt,factory,identity,progress,normalization,probe_values,compare):
    from real_data import sha
    path=Path(checkpoint['path'])
    if sha(path)!=checkpoint['sha256']:raise ValueError('checkpoint SHA mismatch')
    saved=torch.load(path,map_location='cpu',weights_only=True)
    if saved['protocol']!='REAL_CORPUS_PILOT_V1' or saved['identity']!=identity or saved['progress']!=progress or saved['normalization']!=normalization:
        raise ValueError('checkpoint source/data/config/cursor identity mismatch')
    restored=factory();restored_opt=optimizer(torch,restored)
    restored.load_state_dict(saved['model'],strict=True);restored_opt.load_state_dict(saved['optimizer'])
    restore_rng(torch,saved['rng'])
    if not exact(torch,model.state_dict(),restored.state_dict()) or not exact(torch,opt.state_dict(),restored_opt.state_dict()):
        raise ValueError('restored parameters/AdamW differ')
    if not exact(torch,saved['rng'],rng_state(torch)):raise ValueError('restored RNG differs')
    metrics=[];left=probe(torch,model,probe_values);right=probe(torch,restored,probe_values)
    for name in left:compare(torch,'restore.'+name,left[name],right[name],'tensor',metrics)
    if not exact(torch,saved['rng'],rng_state(torch)):raise ValueError('recovery probe changed training RNG')
    if not exact(torch,opt.state_dict(),restored_opt.state_dict()):raise ValueError('recovery performed an optimizer update')
    return dict(status='PASS_NO_EXTRA_UPDATE',parameters_exact=True,optimizer_exact=True,rng_exact=True,
                cursor_exact=True,identity_exact=True,forward_metrics=metrics,extra_updates=0)
