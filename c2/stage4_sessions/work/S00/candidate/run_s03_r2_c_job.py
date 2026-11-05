"""One clean CPU36 round2 C/UBSan bounds job. No real HBM or model."""
from pathlib import Path
import hashlib
import json
import os
import shutil
import signal
import socket
import subprocess
import sys
import time
from cpu36_contract import discover_contracts

root = Path(sys.argv[1]).resolve()
assert root.parent.name.startswith('S03_R2_C_') and root.name == 'payload'
assert sys.platform == 'linux' and not socket.gethostname().startswith('login')
assert os.environ.get('CCS_JOB_ID')
assert all(not os.environ.get(key) for key in ('LD_PRELOAD', 'LD_LIBRARY_PATH', 'PYTHONPATH', 'KML_BLAS_LIB', 'HBM_NODE'))
out = root / 'linux_evidence'
out.mkdir()
(root / 'build').mkdir()
os.chdir(root)
receipt = discover_contracts(sorted(os.sched_getaffinity(0)), 1)
assert len(receipt) == 1
node, contract = next(iter(receipt.items()))
os.sched_setaffinity(0, contract['selected'])
(out / 'cpu_receipt.json').write_text(json.dumps(dict(job_id=os.environ['CCS_JOB_ID'], host=socket.gethostname(), node=node, contract=contract, actual_affinity=sorted(os.sched_getaffinity(0)), clean_environment=True), indent=2) + '\n')
steps = []
summary = dict(status='STARTED', real_HBM=False, real_mempolicy=False, preload_probe=False, model=False)
os.environ['UBSAN_OPTIONS'] = 'halt_on_error=1:print_stacktrace=1'
deadline = time.monotonic() + 270


def run(label, command, allowed=(0,), limit=75):
    record = dict(label=label, command=command, started=time.time(), affinity=sorted(os.sched_getaffinity(0)))
    with (out / (label + '.txt')).open('wb') as stream:
        proc = subprocess.Popen(command, stdout=stream, stderr=subprocess.STDOUT, start_new_session=True)
        record['pid'] = proc.pid
        try:
            code = proc.wait(timeout=max(0.1, min(limit, deadline - time.monotonic())))
        except subprocess.TimeoutExpired:
            record['timed_out'] = True
            os.killpg(proc.pid, signal.SIGTERM)
            try:
                proc.wait(timeout=1)
            except subprocess.TimeoutExpired:
                os.killpg(proc.pid, signal.SIGKILL)
            code = proc.wait(timeout=3)
        record.update(exit_code=code, finished=time.time())
    steps.append(record)
    (out / 'steps.json').write_text(json.dumps(steps, indent=2) + '\n')
    assert code in allowed and not record.get('timed_out'), record
    return code


try:
    cc = shutil.which('cc') or shutil.which('gcc')
    assert cc, 'existing C compiler unavailable'
    run('compiler', [cc, '--version'])
    run('uname', ['uname', '-a'])
    run('glibc', ['getconf', 'GNU_LIBC_VERSION'])
    run('source_sha', ['sha256sum', '-c', 'ARTIFACT_SHA256.txt'])
    run('package_integrity', ['/usr/bin/python3', '-B', 'tests/verify_delivery.py', '--json', str(out / 'package_integrity.json')])
    flags = ['-std=gnu11', '-O1', '-g', '-Wall', '-Wextra', '-pthread', '-fsanitize=undefined', '-fno-sanitize-recover=all']
    (out / 'harness_flags.txt').write_text(' '.join(flags) + '\n')
    run('build_previous', [cc, *flags, '-DS03_SOURCE="../frozen/hbm_alloc.c"', 'tests/bounds_harness.c', '-o', 'build/bounds_previous'])
    run('previous_harness_ldd', ['ldd', 'build/bounds_previous'])
    assert 'libubsan' in (out / 'previous_harness_ldd.txt').read_text() and 'not found' not in (out / 'previous_harness_ldd.txt').read_text()
    run('previous_cases', ['/usr/bin/python3', '-B', 'tests/run_cases.py', 'build/bounds_previous', '--source', 'frozen/hbm_alloc.c', '--version', 'previous', '--json', str(out / 'previous_cases.json')])
    previous = json.loads((out / 'previous_cases.json').read_text())
    rows = previous['cases']
    assert len(rows) == previous['expectations_met'] == 50 and all(x['expectation_met'] for x in rows)
    assert sum(x['expected_failure'] for x in rows) == 21
    assert sum(x['passed'] for x in rows) == 29
    summary.update(previous_expected_failures=21, previous_controls_passed=29, previous_expectations_met=50)
    run('build_candidate', [cc, *flags, 'tests/bounds_harness.c', '-o', 'build/bounds_candidate'])
    run('candidate_harness_ldd', ['ldd', 'build/bounds_candidate'])
    assert 'libubsan' in (out / 'candidate_harness_ldd.txt').read_text() and 'not found' not in (out / 'candidate_harness_ldd.txt').read_text()
    run('candidate_cases', ['/usr/bin/python3', '-B', 'tests/run_cases.py', 'build/bounds_candidate', '--source', 'candidate/hbm_alloc.c', '--version', 'candidate', '--json', str(out / 'candidate_cases.json')])
    candidate = json.loads((out / 'candidate_cases.json').read_text())
    assert len(candidate['cases']) == candidate['expectations_met'] == 50
    assert all(x['passed'] and x['expectation_met'] and 'runtime error:' not in x['stderr'] for x in candidate['cases'])
    summary['candidate_passed'] = 50
    lib = root / 'build/libhbm_alloc_s03_round2.so'
    run('build_library', [cc, '-std=gnu11', '-O2', '-fPIC', '-shared', '-pthread', '-Wall', '-Wextra', 'candidate/hbm_alloc.c', '-o', str(lib)])
    run('elf_header', ['readelf', '-h', str(lib)])
    run('elf_symbols', ['readelf', '-Ws', str(lib)])
    run('ldd', ['ldd', str(lib)])
    assert 'DYN' in (out / 'elf_header.txt').read_text() and 'not found' not in (out / 'ldd.txt').read_text()
    built = {str(p.relative_to(root)): dict(bytes=p.stat().st_size, sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in (root / 'build').iterdir() if p.is_file()}
    (out / 'built_sha256.json').write_text(json.dumps(built, indent=2) + '\n')
    summary.update(status='PASS_NEW_50_C_UBSAN_CASES_AND_ISOLATED_LIBRARY_ONLY', library_sha256=built['build/libhbm_alloc_s03_round2.so']['sha256'])
except Exception as exc:
    summary.update(status='FAIL_C_OR_INFRASTRUCTURE', error=repr(exc))
finally:
    summary['steps'] = steps
    (out / 'SUMMARY.json').write_text(json.dumps(summary, indent=2) + '\n')
print(json.dumps({k: v for k, v in summary.items() if k != 'steps'}))
raise SystemExit(0 if summary['status'].startswith('PASS_') else 1)
