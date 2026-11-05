"""Five bounded, single-variable comparisons. Execute only via an allocated compute job."""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import time

from cpu36_contract import atomic_json, cpu_list, select_cpus, snapshot_threads

root = Path(__file__).resolve().parent


def main():
    if sys.platform != 'linux' or not os.environ.get('CCS_JOB_ID') or socket.gethostname().startswith('login'):
        raise RuntimeError('allocated Linux compute job required; no login-node operator execution')
    source = json.loads((root / 'SOURCE_MANIFEST.json').read_text())
    for relative, digest in source.items():
        assert hashlib.sha256((root / relative).read_bytes()).hexdigest() == digest, relative
    allocated = sorted(os.sched_getaffinity(0))
    domains = []
    for path in Path('/sys/devices/system/node').glob('node[0-9]*'):
        domain = cpu_list((path / 'cpulist').read_text())
        if domain and set(allocated) <= set(domain):
            domains.append((int(path.name[4:]), domain))
    if len(domains) != 1:
        raise RuntimeError('allocation must be wholly within one NUMA domain')
    node, domain = domains[0]
    siblings = {cpu: cpu_list(Path(f'/sys/devices/system/cpu/cpu{cpu}/topology/thread_siblings_list').read_text())
                for cpu in domain}
    receipt = select_cpus(allocated, domain, siblings)
    receipt.update(node=node, host=socket.gethostname(), job_id=os.environ['CCS_JOB_ID'], python=sys.executable,
                   python_version=sys.version, physical_siblings=siblings,
                   scope='CPU36_SMALL_OPERATOR_DIAG_ONLY_NO_MODEL_OR_HBM')
    output = root / ('results_' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'))
    output.mkdir()
    atomic_json(output / 'cpu_receipt.json', receipt)
    # Only narrow the inherited allocation; neither observer nor worker may expand it.
    os.sched_setaffinity(0, receipt['selected'])
    cases = [
        ('A_mkl1_negative', '1', '1', 'close'),
        ('B_mkl_unset', None, '1', 'close'),
        ('C_mkl36', '36', '1', 'close'),
        ('D_bind_false', '36', '1', 'false'),
        ('E_openblas36', '36', '36', 'close'),
    ]
    results = []
    for name, mkl, openblas, bind in cases:
        directory = output / name
        directory.mkdir()
        env = os.environ.copy()
        env.update(OMP_NUM_THREADS='36', OPENBLAS_NUM_THREADS=openblas, OMP_PROC_BIND=bind,
                   OMP_PLACES='cores', PYTHONDONTWRITEBYTECODE='1', PYTHONFAULTHANDLER='1')
        if mkl is None:
            env.pop('MKL_NUM_THREADS', None)
        else:
            env['MKL_NUM_THREADS'] = mkl
        command = ['numactl', '--physcpubind=' + ','.join(map(str, receipt['selected'])),
                   f'--membind={node}', sys.executable, '-B', str(root / 'thread_worker.py'),
                   str(directory), str(output / 'cpu_receipt.json')]
        atomic_json(directory / 'command.json', dict(argv=command, comparison=dict(MKL_NUM_THREADS=mkl,
                    OPENBLAS_NUM_THREADS=openblas, OMP_PROC_BIND=bind), single_thread_negative=(name == 'A_mkl1_negative')))
        samples, violations, ticks = 0, [], {}
        reason = None
        proc = None
        with (directory / 'worker.log').open('wb') as log, (directory / 'samples.jsonl').open('w', encoding='utf-8') as stream:
            try:
                proc = subprocess.Popen(command, env=env, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
                deadline = time.monotonic() + 45
                previous = {}
                while proc.poll() is None:
                    snapshot = snapshot_threads(proc.pid)
                    phase_path = directory / 'phase.json'
                    phase = json.loads(phase_path.read_text())['name'] if phase_path.exists() else 'process_start'
                    stream.write(json.dumps(dict(time_ns=time.time_ns(), phase=phase, snapshot=snapshot)) + '\n')
                    samples += 1
                    for row in snapshot['threads']:
                        if not row['affinity'] or not set(row['affinity']) <= set(receipt['selected']):
                            violations.append(row)
                        key = (row['tid'], row['start_ticks'])
                        delta = row['ticks'] - previous.get(key, row['ticks'])
                        if delta > 0:
                            bucket = ticks.setdefault(phase, {})
                            bucket[str(row['tid'])] = bucket.get(str(row['tid']), 0) + delta
                        previous[key] = row['ticks']
                    if violations:
                        reason = 'TID escaped selected36; stop immediately'
                        break
                    if time.monotonic() >= deadline:
                        reason = 'case exceeded 45 seconds; stop without repeating'
                        break
                    time.sleep(0.02)
            finally:
                if proc is not None and proc.poll() is None:
                    os.killpg(proc.pid, signal.SIGTERM)
                    try:
                        proc.wait(timeout=1)
                    except subprocess.TimeoutExpired:
                        os.killpg(proc.pid, signal.SIGKILL)
                code = proc.wait(timeout=3) if proc is not None else 127
        worker_path = directory / 'worker.json'
        worker = json.loads(worker_path.read_text()) if worker_path.exists() else {}
        stages = worker.get('stages', [])
        for stage in stages:
            for row in stage['threads'].get('threads', []):
                if not row['affinity'] or not set(row['affinity']) <= set(receipt['selected']):
                    violations.append(dict(stage=stage['name'], **row))
        if violations and not reason:
            reason = 'worker stage evidence contains selected36 boundary violation'
        if not reason and any(stage['threads'].get('complete') is not True or not stage['threads'].get('threads') for stage in stages):
            reason = 'incomplete per-stage all-TID evidence; stop without declaring boundary acceptance'
        metadata = dict(case=name, exit_code=code, reason=reason, samples=samples, boundary_violations=violations,
                        activity={phase: dict(active_tids=len(values), ticks_by_tid=values) for phase, values in ticks.items()},
                        torch_reports=[dict(stage=stage['name'], intraop=stage.get('torch_intraop'), interop=stage.get('torch_interop'))
                                       for stage in stages], model_executed=False,
                        limitation='CPU tick activity and omp_max are observations, not exact in-region team membership or model acceptance')
        atomic_json(directory / 'assessment.json', metadata)
        results.append(metadata)
        if reason or code != 0:
            break
    summary = dict(status='DIAGNOSTIC_DATA_COMPLETE' if len(results) == 5 and all(x['exit_code'] == 0 and not x['reason'] for x in results)
                   else 'DIAGNOSTIC_STOPPED_FAILURE', cases=results, cpu_receipt=receipt,
                   formal_model_acceptance=False, production_config_accepted=False)
    atomic_json(output / 'SUMMARY.json', summary)
    collected = {}
    for path in sorted(root.rglob('*')):
        if path.is_file() and path.name != 'COLLECTION.json':
            before = path.stat()
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            after = path.stat()
            if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
                raise RuntimeError(f'file changed during collection: {path}')
            collected[path.relative_to(root).as_posix()] = dict(sha256=digest, bytes=after.st_size, mtime_ns=after.st_mtime_ns)
    atomic_json(output / 'COLLECTION.json', collected)
    print(output / 'SUMMARY.json')
    return 0 if summary['status'] == 'DIAGNOSTIC_DATA_COMPLETE' else 1


if __name__ == '__main__':
    def stop(signum, frame):
        raise KeyboardInterrupt(f'signal {signum}')
    signal.signal(signal.SIGTERM, stop)
    raise SystemExit(main())
