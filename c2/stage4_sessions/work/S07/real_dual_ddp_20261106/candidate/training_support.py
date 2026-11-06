"""Frozen imports, canonical state identity, CPU evidence and zero-update recovery."""
import importlib
import inspect
import json
import os
from pathlib import Path
import sys
import time

import cpu36_contract as cpu36
from runtime_guard import record_event, write_rank_report
from supervisor import check_deadline

ROOT = Path(__file__).resolve().parents[1]


def verify_sources():
    manifest = json.loads((ROOT / 'SOURCE_MANIFEST.json').read_text(encoding='utf-8'))
    for row in manifest['delivery_files']:
        path = ROOT / row['path']
        if path.stat().st_size != row['bytes'] or cpu36.sha(path) != row['sha256']:
            raise ValueError('training source drift: ' + row['path'])
    return cpu36.sha(ROOT / 'SOURCE_MANIFEST.json')


def load_reference(root, ready_path):
    root, ready_path = Path(root).resolve(), Path(ready_path).resolve()
    binding = json.loads((ROOT / 'reference_binding.json').read_text(encoding='utf-8'))
    if cpu36.sha(ready_path) != binding['ready_sha256']:
        raise ValueError('S02 frozen READY SHA mismatch')
    for row in binding['files']:
        path = root / row['path']
        if path.stat().st_size != row['bytes'] or cpu36.sha(path) != row['sha256']:
            raise ValueError('S02 frozen source drift: ' + row['path'])
    sys.path.insert(0, str(root))
    ref = importlib.import_module('dual_reference')
    if Path(ref.__file__).resolve() != root / 'dual_reference.py':
        raise ValueError('wrong reference module origin')
    return ref, binding


def checkpoint(record, directory, stage, receipt, torch=None):
    value = dict(name=stage, snapshot=cpu36.snapshot_threads(os.getpid()),
                 calling_tid=os.getpid(), calling_affinity=sorted(os.sched_getaffinity(0)),
                 environment={key: os.environ.get(key) for key in cpu36.ENVIRONMENT})
    if torch is not None:
        value.update(torch_intraop=torch.get_num_threads(), torch_interop=torch.get_num_interop_threads(),
                     parallel_info=torch.__config__.parallel_info(), runtime=cpu36.runtime_info())
    cpu36.validate_checkpoint(value, receipt)
    record['stage'] = stage
    record['cpu_checkpoints'].append(value)
    write_rank_report(directory / f'rank{record["rank"]}.json', record)
    record_event(directory / f'rank{record["rank"]}.events.jsonl', 'checkpoint', stage=stage)


def validate_ddp_api(torch, config):
    from torch.nn.parallel import DistributedDataParallel
    if torch.__version__.split('+')[0] != '2.7.1':
        raise ValueError('require reviewed installed Torch2.7.1, no API fallback')
    params = inspect.signature(DistributedDataParallel.__init__).parameters
    if not set(config) <= set(params):
        raise ValueError('installed DDP API differs from reviewed Torch2.7.1 interface')
    import torch.nn.parallel.distributed as implementation
    return dict(path=implementation.__file__, sha256=cpu36.sha(implementation.__file__),
                signature=str(inspect.signature(DistributedDataParallel.__init__)),
                config=config, torch_file=torch.__file__, torch_sha256=cpu36.sha(torch.__file__),
                reducer='unmodified installed default SUM/world_size; no comm hook/no_sync/join')


def state_identity(torch, encoder, opt, step, cursor):
    import hashlib
    model = hashlib.sha256()
    adam = hashlib.sha256()
    names = []

    def feed(digest, name, value):
        if not torch.isfinite(value).all():
            raise ValueError('nonfinite state: ' + name)
        digest.update(json.dumps([name, str(value.dtype), list(value.shape)]).encode())
        digest.update(value.detach().contiguous().numpy().tobytes())

    for name, value in encoder.state_dict().items():
        feed(model, name, value)
    for name, parameter in encoder.named_parameters():
        names.append(name)
        state = opt.state[parameter]
        if set(state) != {'step', 'exp_avg', 'exp_avg_sq'} or state['step'].item() != step:
            raise ValueError('AdamW state/step mismatch: ' + name)
        if parameter.grad is None or not torch.isfinite(parameter.grad).all():
            raise ValueError('missing/nonfinite canonical gradient: ' + name)
        for key in sorted(state):
            feed(adam, name + '.' + key, state[key])
    return dict(step=step, cursor=cursor, parameters=len(names),
                names_sha256=hashlib.sha256(json.dumps(names).encode()).hexdigest(),
                model_sha256=model.hexdigest(), adamw_sha256=adam.hexdigest())


def gather_tensor(torch, dist, tensor, rank):
    tensor = tensor.detach().contiguous()
    values = [torch.empty_like(tensor) for _ in range(2)] if rank == 0 else None
    dist.gather(tensor, gather_list=values, dst=0)
    return torch.cat(values, dim=0) if rank == 0 else None


def save_and_restore(torch, ref, encoder, opt, masks, post_init, values,
                     directory, rank, identity, progress, normalization, deadline_ns):
    check_deadline(deadline_ns)
    path = directory / f'rank{rank}.checkpoint.pt'
    if path.exists():
        raise ValueError('refuse existing training checkpoint')
    rng = ref.training.rng_state(torch)
    mask_state = masks.state_dict()
    payload = dict(identity=identity, progress=progress, normalization=normalization,
                   model=encoder.state_dict(), optimizer=opt.state_dict(), rng=rng, masks=mask_state)
    temporary = path.with_suffix('.pt.tmp')
    with temporary.open('xb') as stream:
        torch.save(payload, stream)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)
    index = dict(path=str(path), bytes=path.stat().st_size, sha256=cpu36.sha(path))
    write_rank_report(directory / f'rank{rank}.checkpoint_index.json', index)
    check_deadline(deadline_ns)
    saved = torch.load(path, map_location='cpu', weights_only=True)
    if (cpu36.sha(path) != index['sha256'] or saved['identity'] != identity
            or saved['progress'] != progress or saved['normalization'] != normalization):
        raise ValueError('checkpoint identity/cursor/normalization mismatch')
    try:
        restored, restored_opt, _, restored_post, _ = ref.initialize(torch)
        restored.load_state_dict(saved['model'], strict=True)
        restored_opt.load_state_dict(saved['optimizer'])
        restored_masks = ref.new_mask_stream(torch, restored_post)
        restored_masks.load_state_dict(saved['masks'])
        ref.training.restore_rng(torch, saved['rng'])
        exact = ref.training.exact
        for label, left, right in (
                ('model', encoder.state_dict(), restored.state_dict()),
                ('AdamW', opt.state_dict(), restored_opt.state_dict()),
                ('RNG', rng, ref.training.rng_state(torch)),
                ('mask RNG/cursor', mask_state, restored_masks.state_dict()),
                ('original post-init RNG', post_init, restored_post)):
            if not exact(torch, left, right):
                raise ValueError('restore mismatch: ' + label)
        metrics = []
        left, right = ref.training.probe(torch, encoder, values), ref.training.probe(torch, restored, values)
        for name in left:
            ref.accepted.compare(torch, 'restore.' + name, left[name], right[name], 'tensor', metrics)
        if (not exact(torch, rng, ref.training.rng_state(torch))
                or not exact(torch, mask_state, masks.state_dict())
                or not exact(torch, opt.state_dict(), restored_opt.state_dict())):
            raise ValueError('recovery probe changed RNG/mask stream/AdamW')
        check_deadline(deadline_ns)
        return dict(status='PASS_NO_EXTRA_UPDATE', extra_updates=0, index=index,
                    model_exact=True, optimizer_exact=True, rng_exact=True, mask_rng_exact=True,
                    cursor_exact=True, identity_exact=True, forward_metrics=metrics)
    finally:
        ref.training.restore_rng(torch, rng)
