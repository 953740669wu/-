"""Three sequential calls to the unchanged R6 memory entry; no model changes."""
import json
import os
from pathlib import Path
import runpy
import shutil
import signal
import socket
import sys
import time
import traceback
from bounded_round_step import run_step, save, sha


def validate_pair(payload, job, strict):
    out = payload / 'evidence' / ('memory_' + job + '_ckpt64')
    gate = json.loads((out / 'strict_gate.json').read_text())
    assert gate['sha256'] == sha(strict) and gate['status'] == 'STRICT_CANDIDATE_PASS_REFERENCE_ONLY'
    identity = json.loads(strict.read_text())
    policy = runpy.run_path(str(payload / 'cpu36_contract.py'))
    pair = []
    for ckpt in (0, 1):
        folder = out / ('ckpt' + str(ckpt))
        assert (folder / 'exit_code.txt').read_text().strip() == '0'
        d = json.loads((folder / 'result.json').read_text())
        assert d['status'] == 'DDR_ONE_STEP_DIAGNOSTIC_ONLY_NOT_BENEFIT_ACCEPTANCE'
        assert d['config'] == dict(belt='16_adjacent', part='pre', effective_batch=64, microbatch=64,
            checkpoint=bool(ckpt), history='fresh', precision='fp32', threads=36, loss='original_mean',
            hbm=False, training_steps=1, warmup_steps=0)
        assert d['case_identity'] == identity['case_identity'] and d['case_file_sha256'] == identity['case_file_sha256']
        assert d['case_file_bytes'] == 271979513 and d['optimizer_steps'] == 1
        assert d['checkpoint_wrapped_layers'] == 12 * ckpt and not d['comparison_snapshots_retained']
        assert d['initial_weights_released_before_training']
        assert all(sha(payload / name) == digest for name, digest in d['source_sha256'].items())
        state = d['cpu36']
        assert state['job_id'] == job and state['host'] == socket.gethostname() and state['errors'] == []
        assert [c['name'] for c in state['checkpoints']] == ['before_framework', 'after_framework',
            'after_backend', 'initialized', 'before_training', 'after_training', 'publish']
        policy['validate_receipt'](state['receipt'])
        assert len(state['receipt']['allocated']) == 38
        for c in state['checkpoints']:
            assert c['pid'] == state['pid']
            policy['validate_checkpoint'](c, state['receipt'])
        assert d['runtime']['backend'] == 'kml' and d['runtime']['kml_gemm_calls'] > 0
        assert d['peak_reset']['available'] is True
        assert d['training_start']['peak_rss_bytes'] == d['training_start']['rss_bytes']
        assert d['training_start']['peak_rss_bytes'] <= d['initialization']['peak_rss_bytes']
        for name in ('initialization', 'training_start', 'training'):
            row = d[name]
            assert row['hugetlb_bytes'] == 0 and row['peak_rss_bytes'] >= row['rss_bytes'] > 0
            assert row['rss_MiB'] == row['rss_bytes'] / 2**20 and row['peak_rss_MiB'] == row['peak_rss_bytes'] / 2**20
        pair.append(dict(checkpoint=ckpt, pid=state['pid'], config=d['config'], initialization=d['initialization'],
            training_start=d['training_start'], peak_reset=d['peak_reset'], training=d['training'],
            loss=d['loss'], kml_calls=d['runtime']['kml_gemm_calls'], cpu_checkpoints=7))
    assert pair[0]['pid'] != pair[1]['pid']
    return pair


def main(root):
    assert root.name.startswith('S02_R6_MEMORY3_') and os.environ.get('CCS_JOB_ID')
    assert not socket.gethostname().startswith('login')
    out = root / 'job_evidence'
    out.mkdir()
    deadline = time.monotonic() + 850
    summary = dict(status='STARTED', job_id=os.environ['CCS_JOB_ID'], host=socket.gethostname(),
        pairs=[], real_HBM=False, formal_training=False, UBSan_recovery=False, steps=[])
    try:
        for index in range(1, 4):
            payload = root / ('pair' + str(index)) / 'payload'
            pre = json.loads((root / 'pre_submit_checks.json').read_text())
            assert all(sha(root / name) == digest for name, digest in pre['payload_files'].items())
            command = ['bash', str(payload / 'run_s00_job.sh'), 'memory']
            summary['steps'].append(run_step(out, 'pair' + str(index), command, deadline))
            pair = validate_pair(payload, os.environ['CCS_JOB_ID'], Path(os.environ['S02_EQUIVALENCE_RESULT']))
            summary['pairs'].append(dict(pair=index, measurements=pair))
            save(out / 'SUMMARY.json', summary)
        pids = [m['pid'] for pair in summary['pairs'] for m in pair['measurements']]
        assert len(set(pids)) == 6
        # Optional read-only platform/package identity; each command has a 5s ceiling.
        commands = [('os_release', ['cat', '/etc/os-release']), ('uname', ['uname', '-a']),
                    ('glibc', ['getconf', 'GNU_LIBC_VERSION'])]
        cc = shutil.which('cc')
        if cc:
            compiler = Path(cc).resolve()
            save(out / 'compiler_identity.json', dict(path=str(compiler), sha256=sha(compiler),
                 bytes=compiler.stat().st_size, mtime_ns=compiler.stat().st_mtime_ns))
            commands += [('compiler_target', [cc, '-dumpmachine']), ('compiler_fullversion', [cc, '-dumpfullversion']),
                         ('compiler_search_dirs', [cc, '-print-search-dirs'])]
            if shutil.which('rpm'):
                commands += [('compiler_package', ['rpm', '-qf', str(compiler)]), ('libubsan_package', ['rpm', '-q', 'libubsan'])]
            elif shutil.which('dpkg-query'):
                commands += [('compiler_package', ['dpkg-query', '-S', str(compiler)]),
                             ('libubsan_package', ['dpkg-query', '-W', 'libubsan1'])]
        for label, command in commands:
            summary['steps'].append(run_step(out, label, command, deadline, limit=5, allowed=(0, 1)))
        summary.update(status='PASS_THREE_NEW_PAIRS_DDR_FIRST_STEP_DIAGNOSTIC_ONLY', distinct_model_pids=pids)
        return 0
    except BaseException as exc:
        summary.update(status='FAIL_STOP_NO_RETRY', error=repr(exc), traceback=traceback.format_exc())
        return 1
    finally:
        save(out / 'SUMMARY.json', summary)


if __name__ == '__main__':
    signal.signal(signal.SIGTERM, lambda *_: (_ for _ in ()).throw(InterruptedError('TERM')))
    raise SystemExit(main(Path(sys.argv[1]).resolve()))
