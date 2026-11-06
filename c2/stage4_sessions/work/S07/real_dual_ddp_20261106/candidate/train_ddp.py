"""One authorized real two-domain Encoder DDP run; never submits a job."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import secrets
import sys
import time
import traceback

import cpu36_contract as cpu36
from loss_contract import validate_shards
from runtime_guard import (await_peer_ready, load_allocation, publish_json, record_event,
                           validate_current_job, write_rank_report)
from supervisor import check_deadline, supervise
from training_graph import backward_loss, pretraining_model
from training_support import (checkpoint, gather_tensor, load_reference, save_and_restore,
                              state_identity, validate_ddp_api, verify_sources)

ROOT = Path(__file__).resolve().parents[1]
IDENTITY_KEYS = ('job_id', 'run_id', 'ready_token', 'config_sha256',
                 'reference_ready_sha256', 'source_manifest_sha256', 'descriptor_sha256')


def append_json(path, value):
    with path.open('a', encoding='utf-8') as stream:
        stream.write(json.dumps(value, allow_nan=False) + '\n')
        stream.flush()
        os.fsync(stream.fileno())


def validate_reports(reports, spec, pids):
    if len(reports) != 2 or len(pids) != 2:
        raise ValueError('two complete current-run rank reports required')
    for rank, report in enumerate(reports):
        expected = {key: spec[key] for key in IDENTITY_KEYS}
        expected.update(status='PASS', rank=rank, pid=pids[rank], world_size=2,
                        completed_updates=25, strict_gates_passed=5, local_consumed_frames=800,
                        global_cursor=1600, reference_updates=5 if rank == 0 else 0)
        if any(report.get(key) != value for key, value in expected.items()):
            raise ValueError(f'rank{rank}: stale/incomplete training report')
        recovery = report.get('recovery', {})
        if (recovery.get('status') != 'PASS_NO_EXTRA_UPDATE' or recovery.get('extra_updates') != 0
                or any(recovery.get(key) is not True for key in ('model_exact', 'optimizer_exact',
                           'rng_exact', 'mask_rng_exact', 'cursor_exact', 'identity_exact'))):
            raise ValueError(f'rank{rank}: zero-update recovery not verified')
        if [row['step'] for row in report.get('steps', [])] != list(range(1, 26)):
            raise ValueError('missing or duplicate training step evidence')
    exposed = []
    for left, right in zip(reports[0]['steps'], reports[1]['steps']):
        validate_shards(left['global_indices'], [left['local_indices'], right['local_indices']])
        if (left['global_indices'] != right['global_indices']
                or left['global_mask_sha256'] != right['global_mask_sha256']
                or left['state_identity'] != right['state_identity']):
            raise ValueError('rank sharding/mask/canonical state evidence differs')
        exposed.extend(left['global_indices'])
    if len(exposed) != 1600 or len(set(exposed)) != 1600:
        raise ValueError('training epoch duplicates/misses frames')


def read_reports(directory, spec, pids):
    reports = [json.loads((directory / f'rank{rank}.json').read_text(encoding='utf-8'))
               for rank in range(2)]
    validate_reports(reports, spec, pids)
    for rank, report in enumerate(reports):
        rows = [json.loads(line) for line in (directory / f'rank{rank}.steps.jsonl').read_text(
                encoding='utf-8').splitlines()]
        if rows != report['steps']:
            raise ValueError('rank step log/report mismatch')
    return reports


def validate_training_allocation(allocation):
    if (len(allocation['ranks']) != 2
            or any(len(row['allocated']) != 38 or len(row['selected']) != 36
                   or len(row['reserved']) != 2 for row in allocation['ranks'])):
        raise ValueError('real training requires 76 allocated/72 selected/4 reserved')


def worker(directory, rank):
    spec = json.loads((directory / 'manifest.json').read_text(encoding='utf-8'))
    validate_current_job(spec.get('job_id'))
    validate_current_job(spec['allocation'].get('job_id'))
    validate_training_allocation(spec['allocation'])
    receipt = spec['allocation']['ranks'][rank]
    cpu36.validate_receipt(receipt)
    if not set(receipt['selected']) <= set(os.sched_getaffinity(0)):
        raise ValueError('worker exceeds inherited CPU authority')
    os.sched_setaffinity(0, receipt['selected'])
    deadline = spec['deadline_ns']
    events = directory / f'rank{rank}.events.jsonl'
    record = dict({key: spec[key] for key in IDENTITY_KEYS}, status='FAIL', rank=rank,
                  pid=os.getpid(), world_size=2, cpu_receipt=receipt, cpu_checkpoints=[],
                  completed_updates=0, reference_updates=0, strict_gates_passed=0,
                  reference_updates_attempted=0, local_consumed_frames=0, global_cursor=0,
                  steps=[], recovery={'status': 'NOT_RUN'},
                  phases=dict(first5='NOT_RUN', continuation='NOT_RUN', checkpoint_restore='NOT_RUN'))
    reference = None
    try:
        check_deadline(deadline)
        checkpoint(record, directory, 'before_framework', receipt)
        if verify_sources() != spec['source_manifest_sha256']:
            raise ValueError('training source identity changed')
        ref, binding = load_reference(spec['reference_root'], spec['reference_ready'])
        # Identity and CPU binding above must precede both framework imports.
        validate_current_job(spec['job_id'])
        import torch
        import numpy
        import torch.distributed as dist
        from datetime import timedelta
        from torch.nn.parallel import DistributedDataParallel
        record['ddp_api'] = validate_ddp_api(torch, spec['config']['ddp'])
        runtime, expected_cpus = ref.configure_backend(torch, 'kml', receipt['selected'])
        record['runtime'] = runtime
        record['module_identity'] = {m: dict(path=sys.modules[m].__file__,
                    sha256=cpu36.sha(sys.modules[m].__file__)) for m in ('torch', 'numpy', 'kml_ops')}
        checkpoint(record, directory, 'after_framework', receipt, torch)
        metadata, loaded, normalization, ledger = ref.load_data(
            spec['descriptor'], spec['descriptor_sha256'], directory / f'rank{rank}.exposure.json')
        record['normalization'] = normalization
        record['data_identity'] = metadata['identity']
        encoder, opt, angles, post_init, initialization = ref.initialize(torch)
        masks = ref.new_mask_stream(torch, post_init)
        record['initialization'] = initialization
        checkpoint(record, directory, 'prepared', receipt, torch)
        await_peer_ready(directory, spec, rank, events)
        check_deadline(deadline)
        record_event(events, 'init_process_group_begin', pg_timeout_seconds=120)
        dist.init_process_group('gloo', init_method=(directory / 'rendezvous').as_uri(),
                                rank=rank, world_size=2, timeout=timedelta(seconds=120))
        record_event(events, 'init_process_group_end')
        if dist.get_rank() != rank or dist.get_world_size() != 2 or str(dist.get_backend()) != 'gloo':
            raise ValueError('actual rank/world/backend mismatch')
        ddp = DistributedDataParallel(pretraining_model(torch, encoder), **spec['config']['ddp'])
        canonical = dict(encoder.named_parameters())
        if {id(p) for p in ddp.parameters()} != {id(p) for p in canonical.values()}:
            raise ValueError('DDP does not cover every original Encoder/head parameter')
        if sum(p.numel() for p in ddp.parameters()) != 37995777:
            raise ValueError('DDP full model size mismatch')
        initial_pair = [None, None]
        dist.all_gather_object(initial_pair, dict(initialization,
                       post_init_rng_sha256=hashlib.sha256(post_init.numpy().tobytes()).hexdigest()))
        if initial_pair[0] != initial_pair[1]:
            raise ValueError('rank initialization/mask RNG differs')
        reference_ledger = None
        if rank == 0:
            reference = ref.B64Reference(torch)
            reference_ledger = ref.data.Exposure(directory / 'reference.exposure.json', metadata['description'])
        checkpoint(record, directory, 'ddp_initialized', receipt, torch)
        for step in range(1, 26):
            check_deadline(deadline)
            record['phases']['first5' if step <= 5 else 'continuation'] = 'IN_PROGRESS'
            diagnostic_start = time.perf_counter()
            plan = ref.plan(step)
            validate_shards(plan['global_indices'], plan['rank_indices'])
            frame_ids = [loaded['train']['frame_ids'][i] for i in plan['global_indices']]
            full_mask = masks.next(step)
            ref.check_identity(step, frame_ids, full_mask)
            global_values = ref.training.batch(torch, loaded['train'], plan['global_indices'], angles)
            values, mask = ref.shard(torch, global_values, full_mask, rank)
            for value in values[:2]:
                value.requires_grad_()
            local_indices = plan['rank_indices'][rank]
            local_ids = frame_ids[rank * 32:(rank + 1) * 32]
            ledger.attempt(step, local_indices, local_ids)
            checkpoint(record, directory, f'before_train_{step}', receipt, torch)
            # All collective denominators/log values are detached; only local sums carry gradients.
            counts = torch.tensor([int(mask.sum()), int(values[1].shape[0] * 256)], dtype=torch.int64)
            wait_start = time.perf_counter()
            dist.all_reduce(counts, op=dist.ReduceOp.SUM)
            count_wait = time.perf_counter() - wait_start
            global_counts = [int(x) for x in counts.tolist()]
            if min(global_counts) <= 0:
                raise ValueError('zero global denominator')
            pre_diagnostic = time.perf_counter() - diagnostic_start
            calls = runtime['kml_gemm_calls']
            opt.zero_grad(set_to_none=True)
            train_start = time.perf_counter()
            result = ddp(*values, mask)
            forward_end = time.perf_counter()
            loss = backward_loss(result, global_counts)
            if not torch.isfinite(loss):
                raise ValueError('nonfinite backward loss')
            loss.backward()
            backward_end = time.perf_counter()
            opt.step()
            train_end = time.perf_counter()
            record_event(events, 'optimizer_step_committed', step=step, global_cursor=step*64)
            record.update(completed_updates=step, local_consumed_frames=step * 32, global_cursor=step * 64)
            # Persist committed optimizer count before strict checks can fail.
            write_rank_report(directory / f'rank{rank}.json', record)
            diagnostic_start = time.perf_counter()
            ref.training.validate_update(torch, encoder, opt, values, step)
            training_calls = runtime['kml_gemm_calls'] - calls
            if training_calls <= 0:
                raise ValueError('no actual KML training call observed')
            wait_start = time.perf_counter()
            sums = torch.stack([result['voltage_sum'].detach(), result['coarse_sum'].detach()])
            dist.all_reduce(sums, op=dist.ReduceOp.SUM)
            voltage, coarse = sums[0] / global_counts[0], sums[1] / global_counts[1]
            losses = dict(total=voltage + coarse, voltage=voltage, coarse=coarse)
            state = state_identity(torch, encoder, opt, step, step * 64)
            pair = [None, None]
            dist.all_gather_object(pair, state)
            if pair[0] != pair[1]:
                raise ValueError('rank parameter/AdamW tensor-byte state differs')
            state_wait = time.perf_counter() - wait_start
            ledger.confirm(step)
            gate_wait = reference_seconds = 0.
            reference_calls = 0
            if step <= 5:
                wait_start = time.perf_counter()
                got = dict(outputs={key: gather_tensor(torch, dist, result['outputs'][key], rank)
                                    for key in ('h', 'v', 'coarse')}, losses=losses,
                           input_grads=[gather_tensor(torch, dist, v.grad, rank) for v in values[:2]])
                if rank == 0:
                    metrics = []
                    reference_ledger.attempt(step, plan['global_indices'], frame_ids)
                    record['reference_updates_attempted'] = step
                    write_rank_report(directory / f'rank{rank}.json', record)
                    record_event(events, 'reference_step_attempt', step=step)
                    reference_start = time.perf_counter()
                    reference_calls_start = runtime['kml_gemm_calls']
                    try:
                        reference.advance(step, global_values, full_mask, metrics)
                        record['reference_updates'] = step
                        record_event(events, 'reference_step_completed', step=step)
                        reference_ledger.confirm(step)
                        reference.compare(step, encoder, opt, got, metrics)
                    finally:
                        append_json(directory / 'gate_metrics.jsonl', dict(step=step, metrics=metrics))
                    reference_seconds = time.perf_counter() - reference_start
                    reference_calls = runtime['kml_gemm_calls'] - reference_calls_start
                    if reference_calls <= 0:
                        raise ValueError('no actual KML reference call observed')
                gate = torch.tensor([1 if rank == 0 else 0], dtype=torch.int64)
                # Rank1 cannot begin the next update before rank0's strict gate succeeds.
                dist.broadcast(gate, src=0)
                if gate.item() != 1:
                    raise ValueError('strict B64 reference gate failed')
                gate_wait = time.perf_counter() - wait_start
                record['strict_gates_passed'] = step
                del got
                if step == 5 and reference is not None:
                    reference.close()
                    reference = None
                if step == 5:
                    record['phases']['first5'] = 'PASS'
            import resource
            rss_pages = int(Path('/proc/self/statm').read_text().split()[1])
            row = dict(step=step, global_batch=64, local_batch=32, global_indices=plan['global_indices'],
                       local_indices=local_indices, frame_ids=local_ids,
                       global_frame_ids_sha256=plan['expected_frame_ids_sha256'],
                       global_mask_sha256=plan['expected_mask_sha256'], local_masked=int(mask.sum()),
                       global_counts=global_counts, losses={k: float(v) for k, v in losses.items()},
                       state_identity=state, train_step_seconds=train_end-train_start,
                       forward_seconds=forward_end-train_start, backward_including_ddp_seconds=backward_end-forward_end,
                       optimizer_seconds=train_end-backward_end, denominator_collective_seconds=count_wait,
                       log_and_state_sync_seconds=state_wait, reference_gate_wait_seconds=gate_wait,
                       reference_seconds=reference_seconds, training_kml_calls=training_calls,
                       reference_kml_calls=reference_calls,
                       diagnostic_seconds=pre_diagnostic+time.perf_counter()-diagnostic_start,
                       rss_bytes=rss_pages*os.sysconf('SC_PAGE_SIZE'),
                       process_lifetime_hwm_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                       hwm_scope='includes_reference_coexistence' if rank == 0 else 'rank_process_lifetime',
                       ddp_reducer_timing_raw=ddp._get_ddp_logging_data(),
                       timing_note='backward includes installed reducer synchronization; raw DDP timers are sampled/averaged, not isolated network latency')
            append_json(directory / f'rank{rank}.steps.jsonl', row)
            record['steps'].append(row)
            checkpoint(record, directory, f'after_train_{step}', receipt, torch)
            del result, global_values, values, full_mask, mask
        check_deadline(deadline)
        record['phases']['continuation'] = 'PASS'
        # Probe a training shard already exposed; it adds no optimizer update or new unique frame.
        last = ref.plan(25)['rank_indices'][rank]
        probe_values = ref.training.batch(torch, loaded['train'], last, angles)
        progress = dict(completed_updates=25, global_cursor=1600, local_consumed_frames=800,
                        epoch_order=[i for s in range(1, 26) for i in ref.plan(s)['global_indices']])
        identity = {key: spec[key] for key in IDENTITY_KEYS}
        identity.update(rank=rank, source=record['module_identity'], data=metadata['identity'])
        checkpoint(record, directory, 'before_save_restore', receipt, torch)
        record['phases']['checkpoint_restore'] = 'IN_PROGRESS'
        restore_calls = runtime['kml_gemm_calls']
        record['recovery'] = save_and_restore(torch, ref, encoder, opt, masks, post_init, probe_values,
                    directory, rank, identity, progress, normalization, deadline)
        record['recovery']['kml_calls'] = runtime['kml_gemm_calls'] - restore_calls
        if record['recovery']['kml_calls'] <= 0:
            raise ValueError('no actual KML recovery probe call observed')
        record['phases']['checkpoint_restore'] = 'PASS'
        ref.finish_backend(runtime, expected_cpus)
        ref.data.load_descriptor(spec['descriptor'], spec['descriptor_sha256'])
        load_reference(spec['reference_root'], spec['reference_ready'])
        if verify_sources() != spec['source_manifest_sha256']:
            raise ValueError('training sources changed during run')
        checkpoint(record, directory, 'finished', receipt, torch)
        check_deadline(deadline)
        record.update(status='PASS', training='REAL_ENCODER_DDP_25_UPDATES_STRICT_FIRST5',
                      reference_observation_frames=320 if rank == 0 else 0,
                      recovery_probe_frames=2*32, job_elapsed_seconds=(time.monotonic_ns()-spec['job_start_ns'])/1e9,
                      speedup='NOT_MEASURED_NO_SAME_JOB_SINGLE_DOMAIN_CONTROL')
        write_rank_report(directory / f'rank{rank}.json', record)
        # No unbounded shutdown collective; owned process exit is followed by parent session cleanup.
        record_event(events, 'worker_exit', exit_code=0)
        return 0
    except Exception as exc:
        record.update(error=f'{type(exc).__name__}: {exc}', status='FAIL')
        record['phases'] = {key: 'FAIL_OR_INCOMPLETE' if value == 'IN_PROGRESS' else value
                            for key, value in record['phases'].items()}
        record_event(events, 'worker_error', stage=record.get('stage'), error=record['error'])
        write_rank_report(directory / f'rank{rank}.json', record)
        traceback.print_exc()
        return 1
    finally:
        if reference is not None:
            reference.close()


def run(args):
    validate_current_job(json.loads(args.allocation.read_text(encoding='utf-8')).get('job_id'))
    allocation = load_allocation(args.allocation)
    validate_training_allocation(allocation)
    source_sha = verify_sources()
    if cpu36.sha(args.config) != cpu36.sha(ROOT / 'training_config.json'):
        raise ValueError('only the frozen training configuration is authorized')
    config = json.loads(args.config.read_text(encoding='utf-8'))
    if args.job_start_ns > time.monotonic_ns() or args.job_start_ns <= 0:
        raise ValueError('job common monotonic start is invalid')
    deadline, cleanup = args.job_start_ns + 840*10**9, args.job_start_ns + 870*10**9
    check_deadline(deadline)
    binding = json.loads((ROOT / 'reference_binding.json').read_text(encoding='utf-8'))
    if cpu36.sha(args.reference_ready) != binding['ready_sha256']:
        raise ValueError('wrong frozen S02 reference READY')
    if cpu36.sha(args.descriptor) != config['data']['descriptor_sha256']:
        raise ValueError('wrong original engineering descriptor')
    directory = args.output.resolve()
    directory.mkdir(parents=True, exist_ok=False)
    spec = dict(job_id=allocation['job_id'], run_id=directory.name, ready_token=secrets.token_hex(16),
                config=config, config_sha256=cpu36.sha(args.config), source_manifest_sha256=source_sha,
                reference_root=str(args.reference_root.resolve()), reference_ready=str(args.reference_ready.resolve()),
                reference_ready_sha256=binding['ready_sha256'], descriptor=str(args.descriptor.resolve()),
                descriptor_sha256=config['data']['descriptor_sha256'], allocation=allocation,
                job_start_ns=args.job_start_ns, deadline_ns=deadline, cleanup_deadline_ns=cleanup)
    publish_json(directory / 'manifest.json', spec)
    commands = [[sys.executable, '-B', str(Path(__file__).resolve()), 'worker', '--output', str(directory),
                 '--rank', str(rank)] for rank in range(2)]
    # Native environment and authority are validated again by each worker before Torch import.
    environment = dict(os.environ, **cpu36.ENVIRONMENT, S07_CASE_DEADLINE_NS=str(deadline))
    context = {key: spec[key] for key in ('job_id', 'run_id', 'ready_token')}
    state = supervise(commands, directory, deadline, cleanup, environment, ready_context=context)
    summary = dict(status='FAIL', supervisor=state, job_id=spec['job_id'], run_id=spec['run_id'],
                   job_elapsed_seconds=(time.monotonic_ns()-spec['job_start_ns'])/1e9,
                   subsequent_stages='NOT_RUN_UNLESS_EXPLICITLY_VERIFIED_IN_RANK_REPORTS')
    try:
        if state['reason'] != 'complete' or not state['all_reaped'] or state['exit_codes'] != [0, 0]:
            raise ValueError('both workers did not complete within shared budget')
        reports = read_reports(directory, spec, state['pids'])
        summary.update(status='PASS_REAL_DUAL_DDP_ENGINEERING_ONLY', global_updates=25,
                       physical_rank_updates=50, reference_updates=5, unique_training_frames=1600,
                       reference_observation_frames=320, restore_extra_optimizer_updates=0,
                       speedup='NOT_MEASURED', formal_split_status='UNKNOWN')
    except Exception as exc:
        summary['error'] = f'{type(exc).__name__}: {exc}'
    write_rank_report(directory / 'summary.json', summary)
    return 0 if summary['status'] == 'PASS_REAL_DUAL_DDP_ENGINEERING_ONLY' else (124 if state['reason']=='deadline' else 1)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_subparsers(dest='mode', required=True)
    runner = modes.add_parser('run')
    for name in ('config', 'allocation', 'reference-root', 'reference-ready', 'descriptor', 'output'):
        runner.add_argument('--'+name, required=True, type=Path)
    runner.add_argument('--job-start-ns', required=True, type=int)
    child = modes.add_parser('worker')
    child.add_argument('--output', required=True, type=Path)
    child.add_argument('--rank', required=True, type=int, choices=(0, 1))
    args = parser.parse_args()
    return worker(args.output.resolve(), args.rank) if args.mode == 'worker' else run(args)


if __name__ == '__main__':
    try:
        sys.exit(main())
    except Exception:
        traceback.print_exc()
        sys.exit(1)
