"""One permitted path per invocation; original Tiny AST/wrapper/comparator are read-only."""
import argparse
import ast
from collections import defaultdict
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parent
PROJECT = ROOT.parents[4]
OLD = ROOT.parent / 'real_dual_ddp_20261106'
REFERENCE = PROJECT / 'c2/stage4_sessions/work/S02/real_dual_ddp_reference_20261106'


def write_json(path, value):
    temporary = path.with_name(path.name + '.tmp')
    temporary.write_bytes((json.dumps(value, indent=2, allow_nan=False) + '\n').encode())
    os.replace(temporary, path)


def digest(tensor):
    return hashlib.sha256(tensor.detach().contiguous().numpy().tobytes()).hexdigest()


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def verify_inputs():
    for row in json.loads((ROOT / 'SOURCE_INPUTS.json').read_text())['files']:
        path = Path(row['path'])
        if (path.stat().st_size != row['bytes']
                or hashlib.sha256(path.read_bytes()).hexdigest() != row['sha256']):
            raise ValueError('frozen input changed: ' + str(path))


def original_tiny(torch):
    source = OLD / 'tests/torch_checks_worker.py'
    tree = ast.parse(source.read_text())
    nodes = [node for node in ast.walk(tree) if isinstance(node, ast.ClassDef) and node.name == 'TinyEncoder']
    if len(nodes) != 1:
        raise ValueError('exact original TinyEncoder definition required')
    namespace = dict(torch=torch)
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(source), 'exec'), namespace)
    return namespace['TinyEncoder']


def data(torch, size):
    return (torch.ones(size, 208, requires_grad=True),
            torch.zeros(size, 1, 16, 16, requires_grad=True),
            torch.ones(size, 208, 4), torch.zeros(size, 208))


def global_mask(torch):
    mask = torch.zeros(64, 208, dtype=torch.bool)
    mask.reshape(-1)[[0, 6656, 6657, 6658]] = True
    return mask


def environment(torch):
    import numpy
    return dict(python=sys.executable, torch=str(torch.__version__), numpy=str(numpy.__version__),
                torch_file=torch.__file__, torch_sha256=hashlib.sha256(Path(torch.__file__).read_bytes()).hexdigest(),
                intraop=torch.get_num_threads(), interop=torch.get_num_interop_threads(),
                default_dtype=str(torch.get_default_dtype()), torch_config=torch.__config__.show(),
                environment={name: os.environ.get(name) for name in (
                    'OMP_NUM_THREADS', 'MKL_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'OMP_PLACES',
                    'OMP_PROC_BIND', 'GLOO_SOCKET_IFNAME', 'USE_LIBUV', 'PYTHONPATH')})


def capture(encoder):
    captured = defaultdict(list)
    order = []

    def save(key, value):
        captured[key].append(value.detach().clone())
        order.append(dict(key=key, monotonic_ns=time.monotonic_ns()))

    for name, module in encoder.named_modules():
        name = name or 'encoder'

        def before(_module, args, name=name):
            save('activation.' + name + '.input', args[0])

        def after(_module, _args, value, name=name):
            save('activation.' + name + '.output', value)
            if value.requires_grad:
                value.register_hook(lambda grad, name=name: save('adjoint.' + name + '.output', grad))

        module.register_forward_pre_hook(before)
        module.register_forward_hook(after)
    for name, parameter in encoder.named_parameters():
        parameter.register_hook(lambda grad, name=name: save('local_parameter_vjp.' + name, grad))
    return captured, order


def metric(torch, accepted, name, left, right):
    rows = []
    error = None
    try:
        accepted.compare(torch, name, left, right, 'tensor', rows)
    except AssertionError as exc:
        error = str(exc)
    if not rows:
        return dict(name=name, passed=error is None, error=error)
    result = rows[0]
    result.update(exact=digest(left)==digest(right), torch_equal=bool(torch.equal(left,right)),
                  shape=list(left.shape), dtype=str(left.dtype))
    if error is not None:
        result['error'] = error
    return result


def compare_snapshots(torch, full, got):
    accepted = load_module('r1_original_compare', REFERENCE / 'tests/check_equivalence.py')
    rows = []
    for name in full['tensors']:
        rows.append(metric(torch, accepted, name, full['tensors'][name], got['tensors'][name]))
    for name in ('voltage', 'coarse', 'total'):
        rows.append(metric(torch, accepted, 'loss.' + name, full['losses'][name], got['losses'][name]))
    for name in full['parameter_grads']:
        rows.append(metric(torch, accepted, 'parameter.' + name, full['parameter_grads'][name], got['parameter_grads'][name]))
    for name in ('v', 'image'):
        rows.append(metric(torch, accepted, 'input.' + name, full['input_grads'][name], got['input_grads'][name]))
    forward_order = ['activation.' + name + '.' + part for name in (
        'val', 'pos', 'tf', 'encoder', 'head_v', 'head_coarse') for part in ('input', 'output')]
    backward_order = ['adjoint.' + name + '.output' for name in (
        'head_coarse', 'head_v', 'encoder', 'tf', 'pos', 'val')]
    by_name = {row['name']: row for row in rows}

    def first(order, predicate):
        return next((by_name[name] for name in order if name in by_name and predicate(by_name[name])), None)

    operands = {}
    for name in ('val', 'pos', 'tf'):
        operands[name] = dict(
            input_exact=digest(full['tensors']['activation.'+name+'.input'])==digest(got['tensors']['activation.'+name+'.input']),
            adjoint_exact=digest(full['tensors']['adjoint.'+name+'.output'])==digest(got['tensors']['adjoint.'+name+'.output']))
    old = json.loads((OLD / 'evidence/tiny_ddp_192181562000000/strict_pair_metrics.json').read_text())
    new13 = [by_name['parameter.' + row['name']] if row['name'] not in ('input_v', 'input_image')
             else by_name['input.' + ('v' if row['name']=='input_v' else 'image')] for row in old]
    old_matches = [dict(name=a['name'], scalar_metrics_exact=all(
        a[key] == b[key] for key in ('max_abs', 'l2_relative', 'reference_norm', 'passed')))
                   for a, b in zip(old, new13)]
    return dict(metrics=rows, original_13_metrics=new13,
                first_forward_bit_difference=first(forward_order, lambda row: row.get('exact') is False),
                first_forward_threshold_failure=first(forward_order, lambda row: row['passed'] is False),
                first_backward_adjoint_bit_difference=first(backward_order, lambda row: row.get('exact') is False),
                first_backward_adjoint_threshold_failure=first(backward_order, lambda row: row['passed'] is False),
                first_parameter_failure_by_backward_dependency=first(
                    ['parameter.'+name+'.'+part for name in ('head_coarse','head_v','tf','pos','val')
                     for part in ('weight','bias')] + ['parameter.mask_tok'], lambda row: row['passed'] is False),
                failed_metrics=[row for row in rows if not row['passed']],
                failed_weight_operands=operands, old_ddp_scalar_metric_comparison=old_matches,
                float64_eligible=all(all(value.values()) for value in operands.values())
                   and any(not row['passed'] for row in new13))


def run_model(args, torch):
    graph_module = load_module('r1_frozen_graph', OLD / 'candidate/training_graph.py')
    torch.manual_seed(7)
    encoder = original_tiny(torch)()
    graph = graph_module.pretraining_model(torch, encoder)
    init = hashlib.sha256()
    for name, parameter in encoder.named_parameters():
        init.update(name.encode()); init.update(parameter.detach().numpy().tobytes())
    metadata = dict(mode=args.mode, rank=args.rank, initialization_sha256=init.hexdigest(),
                    post_init_rng_sha256=digest(torch.get_rng_state()), environment=environment(torch),
                    parameters=sum(p.numel() for p in encoder.parameters()), seed=7, optimizer_updates=0,
                    pid=os.getpid())
    prepared_values = data(torch,32) if args.mode=='ddp' else None
    if prepared_values is not None:
        metadata['prepared_inputs_sha256']={key:digest(value) for key,value in zip(
            ('v','image','angles','belt'),prepared_values)}
    write_json(ROOT / 'evidence' / (args.mode + (str(args.rank) if args.rank is not None else '') + '_initial.json'), metadata)
    observed, order = capture(encoder)
    encoder.zero_grad(set_to_none=True)
    parts, loss_sums = [], []
    mask64 = global_mask(torch)
    if args.mode == 'ddp':
        from datetime import timedelta
        import torch.distributed as dist
        from torch.nn.parallel import DistributedDataParallel
        config = json.loads((OLD / 'training_config.json').read_text())['ddp']
        print('before_pg', args.rank, flush=True)
        dist.init_process_group('gloo', init_method=args.init_method, rank=args.rank,
                                world_size=2, timeout=timedelta(seconds=10))
        print('after_pg', args.rank, flush=True)
        graph = DistributedDataParallel(graph, **config)
        batches = [(args.rank * 32, (args.rank+1)*32)]
    else:
        batches = [(0, 64)] if args.mode == 'full' else [(0, 32), (32, 64)]
    for start, stop in batches:
        values = prepared_values if prepared_values is not None else data(torch, stop-start)
        mask = mask64[start:stop].clone()
        result = graph(*values, mask)
        counts = [int(mask.sum()), (stop-start)*256]
        if args.mode == 'ddp':
            count_tensor = torch.tensor(counts, dtype=torch.int64)
            dist.all_reduce(count_tensor)
            global_counts = count_tensor.tolist()
            loss = graph_module.backward_loss(result, global_counts)
        else:
            global_counts = [4, 16384]
            loss = result['voltage_sum']/4 + result['coarse_sum']/16384
        if global_counts != [4, 16384]:
            raise ValueError('wrong global denominators')
        loss.backward()
        parts.append(dict(input_grads={key: values[i].grad.detach().clone() for i,key in enumerate(('v','image'))},
                          inputs_sha256={key:digest(value) for key,value in zip(('v','image','angles','belt'), values)},
                          shards=[dict(inputs_sha256={key:digest(value[offset:offset+32]) for key,value in zip(
                                      ('v','image','angles','belt'),values)},
                                       mask_sha256=digest(mask[offset:offset+32])) for offset in range(0,stop-start,32)],
                          mask_sha256=digest(mask), local_counts=counts, start=start, stop=stop))
        loss_sums.append(torch.stack([result['voltage_sum'].detach(), result['coarse_sum'].detach()]))
    parameters = {name: p.grad.detach().clone() for name,p in encoder.named_parameters()}
    if args.mode == 'ddp':
        for parameter in encoder.parameters():
            pair = [torch.empty_like(parameter.grad) for _ in range(2)]
            dist.all_gather(pair, parameter.grad)
            if not torch.equal(pair[0], pair[1]):
                raise AssertionError('rank gradient bytes differ')
        # Keep the original input-gradient gather; extra observations only write local files.
        for key in ('v','image'):
            tensor = parts[0]['input_grads'][key]
            pair = [torch.empty_like(tensor) for _ in range(2)] if args.rank==0 else None
            dist.gather(tensor, gather_list=pair, dst=0)
    scale = 2 if args.mode=='ddp' else 1
    tensors = {key: torch.cat(values, dim=0)/scale if key.startswith('adjoint.') else torch.cat(values,dim=0)
               for key,values in observed.items() if not key.startswith('local_parameter_vjp.')}
    sums = torch.stack(loss_sums).sum(0)
    if args.mode == 'ddp':
        dist.all_reduce(sums)
    snapshot = dict(metadata=metadata, tensors=tensors, parameter_grads=parameters,
                    local_parameter_vjps={key.split('.',1)[1]:values for key,values in observed.items()
                                          if key.startswith('local_parameter_vjp.')},
                    input_grads={key:torch.cat([part['input_grads'][key] for part in parts],dim=0)/scale
                                 for key in ('v','image')}, parts=parts,
                    losses=dict(voltage=sums[0]/4,coarse=sums[1]/16384,total=sums[0]/4+sums[1]/16384),
                    global_counts=[4,16384], backward_multiplier=scale, hook_order=order)
    label = args.mode + (str(args.rank) if args.rank is not None else '')
    torch.save(snapshot, ROOT / 'raw' / (label+'.pt'))
    write_json(ROOT/'evidence'/(label+'_complete.json'), dict(metadata=metadata,
                global_counts=[4,16384], local_counts=[part['local_counts'] for part in parts],
                backward_multiplier=scale, parameter_grad_divisor=1, input_grad_divisor=scale,
                tensor_indices={key:dict(shape=list(value.shape),dtype=str(value.dtype),sha256=digest(value))
                                for key,value in tensors.items()},
                losses={key:float(value) for key,value in snapshot['losses'].items()}))
    if args.mode=='sequence':
        full = torch.load(ROOT/'raw/full.pt',weights_only=True)
        if full['metadata']['initialization_sha256'] != metadata['initialization_sha256']:
            raise ValueError('initialization changed across paths')
        if full['metadata']['environment'] != metadata['environment']:
            raise ValueError('environment/thread configuration changed')
        if [part['shards'][0] for part in parts] != full['parts'][0]['shards']:
            raise ValueError('input or mask bytes changed across full/sequential paths')
        write_json(ROOT/'evidence/FULL_VS_SEQUENCE.json', compare_snapshots(torch,full,snapshot))
    if args.mode=='ddp':
        dist.destroy_process_group()
    print('path_complete', label, flush=True)


def fp64_control(torch):
    # No new model path: same recorded float32 operands, only contraction accumulation changes.
    full = torch.load(ROOT/'raw/full.pt',weights_only=True)
    seq = torch.load(ROOT/'raw/sequence.pt',weights_only=True)
    rows = []
    for name in ('val','pos','tf'):
        x = full['tensors']['activation.'+name+'.input']
        g = full['tensors']['adjoint.'+name+'.output']
        if not (torch.equal(x,seq['tensors']['activation.'+name+'.input'])
                and torch.equal(g,seq['tensors']['adjoint.'+name+'.output'])):
            raise ValueError('float64 control precondition failed')
        x, g = x.reshape(64*208,-1).double(), g.reshape(64*208,-1).double()
        total = g.T @ x
        split = g[:32*208].T @ x[:32*208] + g[32*208:].T @ x[32*208:]
        native_full = full['parameter_grads'][name+'.weight'].double()
        native_seq = seq['parameter_grads'][name+'.weight'].double()
        norm = total.norm().item()
        def error(value):
            d=value-total
            return dict(max_abs=d.abs().max().item(),l2_relative=d.norm().item()/max(norm,1e-12))
        rows.append(dict(name=name+'.weight',same_recorded_operands=True,
                         float64_full_vs_split=error(split),
                         fp32_full_vs_float64_contraction=error(native_full),
                         fp32_sequence_vs_float64_contraction=error(native_seq),
                         float64_values=total.tolist()))
    write_json(ROOT/'evidence/FLOAT64_CONTROL.json',dict(scope='ONE_RECORDED_OPERAND_CONTRACTION_CONTROL_NO_MODEL_RERUN',
               purpose='Different grouping of identical captured operands; not fp32 acceptance',metrics=rows))


def merge_ddp(torch):
    full=torch.load(ROOT/'raw/full.pt',weights_only=True)
    sequence=torch.load(ROOT/'raw/sequence.pt',weights_only=True)
    ranks=[torch.load(ROOT/'raw'/('ddp'+str(rank)+'.pt'),weights_only=True) for rank in range(2)]
    for rank,value in enumerate(ranks):
        if value['metadata']['initialization_sha256']!=full['metadata']['initialization_sha256']:
            raise ValueError('DDP initial weights differ')
        if value['metadata']['environment']!=full['metadata']['environment']:
            raise ValueError('DDP environment/threads differ')
        if value['parts'][0]['shards'][0]!=full['parts'][0]['shards'][rank]:
            raise ValueError('DDP inputs/mask differ')
    for name in full['parameter_grads']:
        if not torch.equal(ranks[0]['parameter_grads'][name],ranks[1]['parameter_grads'][name]):
            raise ValueError('DDP rank final parameter gradients differ')
    merged=dict(tensors={key:torch.cat([value['tensors'][key] for value in ranks],dim=0)
                         for key in full['tensors']},
                parameter_grads=ranks[0]['parameter_grads'],
                input_grads={key:torch.cat([value['input_grads'][key] for value in ranks],dim=0)
                             for key in ('v','image')},losses=ranks[0]['losses'])
    accepted=load_module('r1_merge_compare',REFERENCE/'tests/check_equivalence.py')
    average=[]
    for name in full['parameter_grads']:
        expected=(ranks[0]['local_parameter_vjps'][name][0]/2
                  +ranks[1]['local_parameter_vjps'][name][0]/2)
        average.append(metric(torch,accepted,name,expected,merged['parameter_grads'][name]))
    write_json(ROOT/'evidence/DDP_COMPARISONS.json',dict(full_vs_ddp=compare_snapshots(torch,full,merged),
               sequence_vs_ddp=compare_snapshots(torch,sequence,merged),reducer_average_metrics=average,
               input_gradient_divisor=2,parameter_gradient_divisor=1))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode',choices=('full','sequence','fp64','ddp','merge'),required=True)
    parser.add_argument('--rank',type=int,choices=(0,1))
    parser.add_argument('--init-method')
    args=parser.parse_args()
    verify_inputs()
    import torch
    if str(torch.__version__)!='2.7.1+cpu':
        raise ValueError('original local Torch2.7.1+cpu required')
    if args.mode=='fp64':fp64_control(torch)
    elif args.mode=='merge':merge_ddp(torch)
    else:run_model(args,torch)
