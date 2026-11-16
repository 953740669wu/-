"""Check returned archive bytes, deployment identities and measured results."""
from datetime import datetime
from hashlib import sha256
import json
from pathlib import Path
import statistics
import sys
from zipfile import ZipFile

HERE = Path(__file__).resolve().parent


def read(path):
    return json.loads(path.read_bytes())


def main(version, job, expected_sha):
    root = HERE / version
    bundle = root / f'JOB_{job}_evidence.zip'
    assert sha256(bundle.read_bytes()).hexdigest() == expected_sha
    dest = root / 'received'
    dest.mkdir(exist_ok=False)
    with ZipFile(bundle) as z:
        assert len(set(z.namelist())) == len(z.namelist())
        index = json.loads(z.read('COLLECTION_INDEX.json'))
        expected = {name for name, meta in index['files'].items() if meta['archive']}
        assert set(z.namelist()) == expected | {'COLLECTION_INDEX.json'}
        for name in z.namelist():
            path = (dest / name).resolve()
            assert dest.resolve() in path.parents
            raw = z.read(name)
            if name in expected:
                assert len(raw) == index['files'][name]['bytes']
                assert sha256(raw).hexdigest() == index['files'][name]['sha256']
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(raw)
    assert (root / 'RUN_BINDING.json').read_bytes() == (dest / 'RUN_BINDING.json').read_bytes()
    assert (root / 'SOURCE_SHA256.json').read_bytes() == (dest / 'SOURCE_SHA256.json').read_bytes()
    for name, digest in read(root / 'SOURCE_SHA256.json').items():
        assert sha256((dest / name).read_bytes()).hexdigest() == digest
    summary = read(dest / 'job_evidence/SUMMARY.json')
    native, = read(dest / 'djob_final.json')['data']['successData']
    assert str(native['jobId']) == job and native['state'] in ('SUCCEEDED','FAILED','CANCELLED')
    assert all(p in ('-', '', None) for p in index['pids'])
    cleanup = read(dest / 'job_evidence/cleanup.json')
    assert cleanup['all_reaped'] and summary.get('hbm_pool_restored') is True
    results = {}
    for path in sorted((dest / 'job_evidence').glob('*/node*/result.json')):
        value = read(path)
        steps = path.with_name('steps.jsonl')
        rows = [json.loads(line) for line in steps.read_bytes().splitlines()] if steps.exists() else []
        sample = [r for r in rows if r['sampled']]
        metrics = value.get('metrics', [])
        results[path.parent.parent.name + '/' + path.parent.name] = dict(
            status=value.get('status'), completed_updates=value.get('completed_updates',0),
            recorded_updates=len(rows), error=value.get('error'), metrics=len(metrics),
            failed_metrics=[m for m in metrics if not m['passed']],
            final_model_sha256=value.get('final_model_sha256'),
            checkpoint_scope=value.get('checkpoint_scope'),
            sample_count=len(sample),
            sample_median_s=statistics.median(r['step_seconds'] for r in sample) if sample else None,
            sample_total_s=sum(r['step_seconds'] for r in sample),
            all_steps_total_s=sum(r['step_seconds'] for r in rows),
            observed_peak_estimate_MiB=max(((r['rss_after']['peak_rss_bytes']+r['rss_after']['hugetlb_bytes'])/2**20 for r in rows),default=None),
            kml_counts=sorted(set(r['kml_calls'] for r in rows)))
    report = dict(version=version, job_id=job, native_state=native['state'],
                  archive_sha256=expected_sha, verified_members=len(expected)+1,
                  summary=summary, results=results, cleanup=cleanup,
                  queue_seconds=native.get('pendingDuration'),
                  native_times={k:v for k,v in native.items() if any(w in k.lower() for w in ('time','duration'))})
    paired = [v for k,v in results.items() if k.startswith('perf_')]
    if len(paired) == 2 and all(v['status']=='PASS_PERF25' and v['sample_count']==20 for v in paired):
        base, cand = [next(v for k,v in results.items() if k.startswith('perf_'+s)) for s in ('baseline','candidate')]
        report['comparison'] = {key: dict(baseline=base[key],candidate=cand[key],
                                candidate_change_pct=100*(cand[key]/base[key]-1))
                                for key in ('sample_median_s','sample_total_s','all_steps_total_s','observed_peak_estimate_MiB')}
    (root / 'REVIEW.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,indent=2))


if __name__ == '__main__':
    main(*sys.argv[1:])
