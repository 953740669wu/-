"""Observe the unchanged first update without retaining full per-layer tensors."""
import hashlib
import json
import math

import numpy as np
import torch
import torch.nn.functional as F


def tensor_sha(x):
    return hashlib.sha256(x.detach().numpy().tobytes(order='C')).hexdigest()


def file_sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def error(reference, candidate):
    assert reference.shape == candidate.shape and reference.dtype == candidate.dtype
    max_abs, worst, delta_squares, ref_squares = -1, None, 0.0, 0.0
    chunk = 4 if reference.ndim == 4 else reference.shape[0]
    for start in range(0, reference.shape[0], chunk):
        a = reference[start:start+chunk].detach().double()
        d = (candidate[start:start+chunk].detach().double() - a).abs()
        value, idx = d.reshape(-1).max(0)
        if value.item() > max_abs:
            max_abs = value.item()
            where = list(np.unravel_index(idx.item(), tuple(d.shape)))
            where[0] += start
            worst = [int(i) for i in where]
        delta_squares += d.square().sum().item()
        ref_squares += a.square().sum().item()
    return dict(max_abs=max_abs, relative_l2=math.sqrt(delta_squares)/max(math.sqrt(ref_squares),1e-12), worst_index=worst)


class FirstErrorTrace:
    def __init__(self, args, result, model):
        self.baseline = args.variant == 'baseline'
        self.output = args.output
        self.ref = args.reference / args.output.name
        self.record = result['first_error_trace'] = {}
        self.layers = {}
        self.native = F.scaled_dot_product_attention
        self.hooks = [layer.register_forward_hook(self.layer_hook(i)) for i,layer in enumerate(model.tf.layers)]
        F.scaled_dot_product_attention = self.sdpa

    def layer_hook(self, i):
        def sample(_module, _inputs, output):
            if i in self.layers:
                return
            rng = torch.get_rng_state()
            x = output.detach()
            assert tuple(x.shape) == (32,928,512)
            _, tokens, width = x.shape
            idx = torch.arange(8192, dtype=torch.int64) * x.numel() // 8192
            self.layers[i] = x[idx//(tokens*width), idx//width%tokens, idx%width]
            assert torch.equal(rng,torch.get_rng_state())
        return sample

    def sdpa(self, q, k, v, *args, **kwargs):
        out = self.native(q,k,v,*args,**kwargs)
        if 'attention_layer0' in self.record:
            return out
        rng = torch.get_rng_state()
        hashes = {name:tensor_sha(x) for name,x in zip(('q','k','v'),(q,k,v))}
        path = self.ref/'diagnostic_first_attention.pt'
        trace = self.record['attention_layer0'] = dict(qkv_sha256=hashes, shape=list(q.shape), dtype=str(q.dtype),
            qkv_strides={name:list(x.stride()) for name,x in zip(('q','k','v'),(q,k,v))}, output_sha256=tensor_sha(out))
        if self.baseline:
            torch.save(out.detach(),path)
            trace['reference_file_sha256'] = file_sha(path)
        else:
            old = json.loads((self.ref/'result.json').read_bytes())['first_error_trace']['attention_layer0']
            assert hashes==old['qkv_sha256'] and trace['shape']==old['shape'] and trace['dtype']==old['dtype']
            assert file_sha(path)==old['reference_file_sha256']
            ref = torch.load(path,map_location='cpu',mmap=True,weights_only=True)
            trace['same_qkv'] = True
            trace['output_error'] = error(ref,out)
            trace['reference_output_sha256'] = old['output_sha256']
            b,h,_,_ = trace['output_error']['worst_index']
            if trace['output_error']['max_abs']>0:
                head = self.output/'layer0_worst_head.npy'
                np.save(head,np.stack([x[b,h].detach().numpy() for x in (q,k,v,ref,out)]),allow_pickle=False)
                trace['head_evidence'] = dict(batch=b,head=h,path=head.name,sha256=file_sha(head),
                                              order=['q','k','v','sdpa_output','m1_output'])
        assert torch.equal(rng,torch.get_rng_state())
        return out

    def finish(self, result, captured, accepted):
        assert len(self.layers)==12 and 'attention_layer0' in self.record
        for h in self.hooks:
            h.remove()
        F.scaled_dot_product_attention = self.native
        path = self.ref/'strict_step1.pt'
        hidden = captured['h']
        self.record['hidden_sha256'] = tensor_sha(hidden)
        if self.baseline:
            torch.save(dict(layers=self.layers,hidden=hidden),path)
            result['reference_snapshots'] = [dict(step=1,bytes=path.stat().st_size,sha256=file_sha(path))]
        else:
            old = json.loads((self.ref/'result.json').read_bytes())
            assert old['status']=='PASS_STRICT_REFERENCE1_DIAGNOSTIC' and old['completed_updates']==1
            assert file_sha(path)==old['reference_snapshots'][0]['sha256']
            ref = torch.load(path,map_location='cpu',mmap=True,weights_only=True)
            self.record['encoder_layer_output_samples'] = [dict(layer=i, n=8192, **error(ref['layers'][i],self.layers[i])) for i in range(12)]
            accepted.compare(torch,'1.output.h',ref['hidden'],hidden,'tensor',result['metrics'])
