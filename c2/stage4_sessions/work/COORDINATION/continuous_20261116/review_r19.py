"""Audit the terminal archive and retain every domain, including incomplete ones."""
from contextlib import redirect_stdout
from datetime import datetime
from hashlib import sha256
import io
import json
from pathlib import Path
import shlex
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent/'aggressive_3h_20261111'))
import review_job


def read(path):
    return json.loads(path.read_bytes())


def main(job, digest):
    version = 'R19_FTZ_REFERENCE'
    root = HERE/version
    review_job.HERE = HERE
    with redirect_stdout(io.StringIO()):
        review_job.main(version, job, digest)
    rec = root/'received'
    ev = rec/'job_evidence'
    report = read(root/'REVIEW.json')
    binding = read(root/'RUN_BINDING.json')
    native, = read(rec/'djob_final.json')['data']['successData']
    pin = sha256((root/'RUN_BINDING.json').read_bytes()).hexdigest()
    argv = [pin if a == 'BINDING_SHA256' else a for a in binding['native_argv']]
    assert native['execPath'] == binding['remote_root'] and native['user'] == 'wujunyi'
    assert shlex.split(native['cmd']) == argv[argv.index('bash'):]
    group, = native['resGroups']
    assert group['resAlloc']['cpu'] == 608 and group['resAlloc']['mem'] == 393216
    assert {n['execNode'] for n in group['nodeResUsages']} == {'cn22035'}
    assert read(rec/'FIXED_INPUTS_BEFORE.json') == read(rec/'FIXED_INPUTS_AFTER.json')
    external = read(root/'EXTERNAL_REFERENCE.json')
    assert external['job_id'] == '2146931' and len(external['snapshots']) == 5
    assert sha256((root/'EXTERNAL_REFERENCE.json').read_bytes()).hexdigest() == binding['frozen_sidecars']['EXTERNAL_REFERENCE.json']
    domains = {}; recorded = charged = 0
    for node in range(16):
        directory = ev/'domains'/f'node{node}'
        summary = read(directory/'DOMAIN_SUMMARY.json') if (directory/'DOMAIN_SUMMARY.json').exists() else {}
        phases = {}
        for variant in ('candidate',):
            out = directory/f'strict_{variant}'/f'node{node}'
            value = read(out/'result.json') if (out/'result.json').exists() else {}
            rows = [json.loads(l) for l in (out/'steps.jsonl').read_text().splitlines()] if (out/'steps.jsonl').exists() else []
            ledger = read(out/'EXPOSURE_LEDGER.json') if (out/'EXPOSURE_LEDGER.json').exists() else {}
            charge = len(ledger.get('confirmed_updates',[])) + bool(ledger.get('in_flight'))
            recorded += len(rows); charged += charge
            expected = 'PASS_STRICT_REFERENCE5' if variant == 'baseline' else 'PASS_STRICT_ENCODER5'
            passed = value.get('status') == expected
            if passed:
                assert len(rows) == 5 and value['completed_updates'] == 5
                assert value['historical_original_model5_exact'] and not value['cpu36']['errors']
                assert set(value['final_model_sha256'].values()) == {'2e777d61801988322e0709d078b7364629fa01ebd83b8001d5d5f1acfcd12a05'}
                assert all(r['kml_calls'] == 197 for r in rows)
                assert value['flush_denormal_requested'] and value['denormal_probe']==dict(input_bits=1,elements=36*4096,nonzero_output_bits=0)
                if variant == 'candidate':
                    assert len(value['metrics']) == 3880 and all(m['passed'] for m in value['metrics'])
                    assert value.get('checkpoint_tail_counts') is None
            phases[variant] = dict(passed=passed,status=value.get('status'),error=value.get('error'),
                recorded_updates=len(rows),charged_updates=charge,metrics=len(value.get('metrics',[])),
                failed_metrics=[m for m in value.get('metrics',[]) if not m['passed']],
                step_seconds=[r['step_seconds'] for r in rows])
        domains[f'node{node}'] = dict(summary=summary,phases=phases,
            strict5_passed=all(v['passed'] for v in phases.values()))
    elapsed = lambda a,b: (datetime.fromisoformat(native[b].replace('Z','+00:00'))-datetime.fromisoformat(native[a].replace('Z','+00:00'))).total_seconds()
    report.update(domains=domains,all16_strict_passed=all(v['strict5_passed'] for v in domains.values()),
        reference_kind='cross-job exact completed original five-step snapshots from R16 node4; metadata and each snapshot hash verified',
        reference_job_id='2146931',
        cleanup_passed=report['cleanup']['all_reaped'] and report['summary']['hbm_pool_restored'],
        recorded_updates=recorded,charged_updates=charged,allocation_seconds=elapsed('startTime','endTime'),
        queue_seconds=elapsed('createTime','startTime'),fixed_inputs_before_after_equal=True)
    (root/'REVIEW.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:report[k] for k in ('all16_strict_passed','cleanup_passed','recorded_updates','charged_updates','allocation_seconds','queue_seconds')}))


if __name__ == '__main__':
    main(*sys.argv[1:])
