"""Review each independent domain, without hiding failure of any other domain."""
import json
from hashlib import sha256
from pathlib import Path
from statistics import median
import sys
import review_job


def main(job, digest):
    version='R15_INDEPENDENT_DOMAINS'
    root=Path(__file__).resolve().parent/version
    if not (root/'received').exists():
        review_job.main(version,job,digest)
    else:
        assert sha256((root/f'JOB_{job}_evidence.zip').read_bytes()).hexdigest()==digest
        index=json.loads((root/'received/COLLECTION_INDEX.json').read_bytes())
        for name, meta in index['files'].items():
            if meta['archive']:
                raw=(root/'received'/name).read_bytes()
                assert len(raw)==meta['bytes'] and sha256(raw).hexdigest()==meta['sha256']
    read=lambda p:json.loads(p.read_bytes())
    report=read(root/'REVIEW.json');rec=root/'received';ev=rec/'job_evidence'
    assert read(rec/'FIXED_INPUTS_BEFORE.json')==read(rec/'FIXED_INPUTS_AFTER.json')
    native=read(rec/'djob_final.json')['data']['successData'][0]
    assert {n['execNode'] for g in native['resGroups'] for n in g['nodeResUsages']}=={'cn22035'}
    group=native['resGroups'][0]
    assert group['resAlloc']['cpu']==152 and group['resAlloc']['mem']==98304
    domains={};recorded=charged=0
    for directory in sorted((ev/'domains').glob('node*')):
        node=directory.name
        summary=read(directory/'DOMAIN_SUMMARY.json') if (directory/'DOMAIN_SUMMARY.json').exists() else {}
        if (directory/'cleanup.json').exists():assert read(directory/'cleanup.json')['all_reaped']
        phases={}
        for phase in sorted(directory.glob('*')):
            out=phase/node
            if not out.is_dir():continue
            rows=[json.loads(s) for s in (out/'steps.jsonl').read_text().splitlines()] if (out/'steps.jsonl').exists() else []
            value=read(out/'result.json') if (out/'result.json').exists() else {}
            ledger=read(out/'EXPOSURE_LEDGER.json') if (out/'EXPOSURE_LEDGER.json').exists() else {}
            charge=len(ledger.get('confirmed_updates',[]))+int(bool(ledger.get('in_flight')))
            recorded+=len(rows);charged+=charge
            samples=[r for r in rows if r['sampled']]
            metrics=value.get('metrics',[])
            phases[phase.name]=dict(status=value.get('status'),error=value.get('error'),recorded_updates=len(rows),charged_updates=charge,
                metrics=len(metrics),failed_metrics=[x for x in metrics if not x['passed']],
                historical_model5_exact=value.get('historical_original_model5_exact'),
                final_model_sha256=value.get('final_model_sha256'),tail_counts=value.get('checkpoint_tail_counts'),
                sample_count=len(samples),sample_seconds=sum(r['step_seconds'] for r in samples),
                sample_median_s=median(r['step_seconds'] for r in samples) if samples else None,
                sample_frames_s=32*len(samples)/sum(r['step_seconds'] for r in samples) if samples else None,
                peak_estimate_MiB=max(((r['rss_after']['peak_rss_bytes']+r['rss_after']['hugetlb_bytes'])/2**20 for r in rows),default=None),
                kml_counts=sorted(set(r['kml_calls'] for r in rows)))
            if value.get('status','').startswith('PASS'):
                assert not value['cpu36']['errors']
                assert all(x['passed'] for x in metrics)
                assert all(r['kml_calls']==(185 if 'candidate' in phase.name else 197) for r in rows)
        base=phases.get('strict_baseline',{});cand=phases.get('strict_candidate',{})
        strict=(base.get('status')=='PASS_STRICT_REFERENCE5' and cand.get('status')=='PASS_STRICT_ENCODER5')
        if strict:
            assert base['recorded_updates']==cand['recorded_updates']==5
            assert base['historical_model5_exact'] and cand['historical_model5_exact']
            assert cand['metrics']==3880 and not cand['failed_metrics']
            assert cand['tail_counts']==dict(skipped=60,escaped=0)
        perf_base=phases.get('perf_baseline_r1',{});perf_cand=phases.get('perf_candidate_r1',{})
        paired=(strict and perf_base.get('status')==perf_cand.get('status')=='PASS_PERF15')
        comparison=None
        if paired:
            assert perf_base['recorded_updates']==perf_cand['recorded_updates']==15
            assert perf_base['sample_count']==perf_cand['sample_count']==12
            assert perf_cand['tail_counts']==dict(skipped=180,escaped=0)
            assert list(perf_base['final_model_sha256'].values())==list(perf_cand['final_model_sha256'].values())
            comparison={k:dict(baseline=perf_base[k],candidate=perf_cand[k],change_pct=100*(perf_cand[k]/perf_base[k]-1)) for k in ('sample_seconds','sample_median_s','sample_frames_s','peak_estimate_MiB')}
        domains[node]=dict(summary=summary,strict5_passed=strict,complete_perf_pair=paired,phases=phases,comparison=comparison)
    assert set(domains)=={'node0','node1','node2','node3'}
    report.update(domains=domains,recorded_updates=recorded,charged_updates=charged,
                  protocol='four independent lifecycles; strict5 then perf15 with3warm12samples; preserve failed domains',
                  all_four_domains_passed=all(x['complete_perf_pair'] for x in domains.values()))
    (root/'REVIEW.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(recorded_updates=recorded,charged_updates=charged,domains={n:{k:v[k] for k in ('strict5_passed','complete_perf_pair','comparison')} for n,v in domains.items()}),ensure_ascii=False,indent=2))


if __name__=='__main__':main(*sys.argv[1:])
