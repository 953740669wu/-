"""Review the original, adopted and candidate paths without changing R1's frozen reviewer."""
import json
from pathlib import Path
import sys
import review_job


def main(version, job, digest):
    review_job.main(version,job,digest)
    root=Path(__file__).resolve().parent/version
    report=json.loads((root/'REVIEW.json').read_bytes())
    arms={}
    for role in ('baseline','ckpt_hbm','candidate'):
        key=next(k for k in report['results'] if k.startswith('perf_'+role))
        result=report['results'][key]
        assert result['status']=='PASS_PERF25' and result['sample_count']==20
        path=root/'received/job_evidence'/key/'steps.jsonl'
        rows=[json.loads(x) for x in path.read_bytes().splitlines()]
        sampled=[x for x in rows if x['sampled']]
        frames=sum(x['batch_size'] for x in sampled)
        span=(sampled[-1]['end_ns']-sampled[0]['start_ns'])/1e9
        result.update(pure_training_frames_s=frames/result['sample_total_s'],
                      sample_span_with_checks_s=span,frames_s_with_interstep_checks=frames/span)
        arms[role]=result
    report['threeway']={}
    for before,after in (('baseline','ckpt_hbm'),('baseline','candidate'),('ckpt_hbm','candidate')):
        a,b=arms[before],arms[after]
        report['threeway'][before+'_to_'+after]={key:dict(before=a[key],after=b[key],change_pct=100*(b[key]/a[key]-1))
            for key in ('sample_total_s','sample_median_s','all_steps_total_s','observed_peak_estimate_MiB',
                        'pure_training_frames_s','frames_s_with_interstep_checks')}
    report['strict_final_weights_equal']=len({next(iter(v['final_model_sha256'].values())) for k,v in report['results'].items() if k.startswith('strict_')})==1
    report['perf_final_weights_equal']=len({next(iter(v['final_model_sha256'].values())) for k,v in report['results'].items() if k.startswith('perf_')})==1
    (root/'REVIEW.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report['threeway'],indent=2))


if __name__=='__main__':main(*sys.argv[1:])
