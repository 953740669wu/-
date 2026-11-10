"""Verify the one returned diagnostic, using the frozen namespace/terminal collector."""
import sys

from freeze_diagnostic import BASE, HERE, OLD, VERSION, read, sha, write

sys.path.insert(0,str(OLD))
from settle_ns import verify_unpack
from analyze_run import native_time, rows
from verify_dependency import identity


def settle(job,digest):
    folder=HERE/VERSION; raw,receipt=verify_unpack(folder,job,digest)
    binding=read(folder/'RUN_BINDING.json'); e=raw/'job_evidence'
    assert (raw/'RUN_BINDING.json').read_bytes()==(folder/'RUN_BINDING.json').read_bytes()
    assert sha((raw/'FULL16_PAYLOAD.zip').read_bytes())==binding['package_sha256']
    manifest=read(raw/'SOURCE_SHA256.json')
    assert sha((raw/'SOURCE_SHA256.json').read_bytes())==binding['source_manifest_sha256']
    for n,h in (manifest|binding['frozen_sidecars']).items():
        assert sha((raw/n).read_bytes())==h,n
    old=read(BASE/'SOURCE_SHA256.json')
    assert {n for n in old if old[n]!=manifest[n]}=={'payload/worker.py','launch.py'}
    assert set(manifest)-set(old)=={'payload/first_error_trace.py'}
    assert read(raw/'FIXED_INPUTS_BEFORE.json')==read(raw/'FIXED_INPUTS_AFTER.json')
    n,=read(raw/'djob_final.json')['data']['successData']; g,=n['resGroups']; node,=g['nodeResUsages']
    assert n['jobId']==job and n['user']=='wujunyi' and n['queue']=='q_hpcai' and n['state']==receipt['state']
    assert n['state'] in ('FAILED','SUCCEEDED','CANCELLED') and n['execPath']==binding['remote_root']
    assert n['jobWallClockLimit']==900 and n['exclusive'] and receipt['pids']==[node['pids']]==['-']
    assert g['resReq']['cpu']==g['resAlloc']['cpu']==38 and g['resReq']['mem']==g['resAlloc']['mem']==g['resLimit']['mem']==24576
    topo=read(e/'domain_map.json') if (e/'domain_map.json').is_file() else None
    c=read(e/'cleanup.json'); assert c['all_reaped'] and not c['remaining_live'] and not c['remaining_processes']
    app=read(e/'SUMMARY.json'); assert app['job_id']==job
    duration=app['compute_finished']-app['start']
    summary=dict(job_id=job,host=node['execNode'],state=n['state'],application=app,diagnostic_compute_seconds=duration,
                 compute_cap_pass=0<=duration<=300,source_binding=identity(folder/'RUN_BINDING.json'))
    baseline=sorted(e.glob('strict_baseline/node*/result.json')); candidate=sorted(e.glob('strict_candidate/node*/result.json'))
    observed=sum(len(rows(q)) for q in e.glob('strict_*/node*/steps.jsonl'))
    if baseline and candidate:
        ref,=baseline; got,=candidate; r,c=read(ref),read(got)
        summary.update(baseline_result=identity(ref),candidate_result=identity(got),metrics=c['metrics'])
        first=c.get('first_error_trace',{})
        if 'encoder_layer_output_samples' in first:
            assert len(topo['contracts'])==1 and r['pairing_sha256']==c['pairing_sha256'] and r['completed_updates']==1
            a,=rows(ref.parent/'steps.jsonl'); b,=rows(got.parent/'steps.jsonl')
            old_step,=rows(BASE/'received/job_evidence/strict_candidate'/got.parent.name/'steps.jsonl')
            for k in ('frame_indices','frame_ids','mask_sha256','native_shapes'):
                assert a[k]==b[k]==old_step[k]
            assert a['native_sgemm_calls']==b['native_sgemm_calls']==197 and observed==2
            assert c['attention']['counts']==dict(forward=24,backward=12)
            af=first['attention_layer0']; assert af['same_qkv'] and af['qkv_sha256']==r['first_error_trace']['attention_layer0']['qkv_sha256']
            assert [x['layer'] for x in first['encoder_layer_output_samples']]==list(range(12))
            if 'head_evidence' in af:
                head=got.parent/af['head_evidence']['path']; assert sha(head.read_bytes())==af['head_evidence']['sha256']
                summary['first_attention_head']=identity(head)
            old_result=read(BASE/'received/job_evidence/strict_candidate'/got.parent.name/'result.json')
            old_failure=[m for m in old_result['metrics'] if m['name']=='1.output.h'][0]
            this_failure=[m for m in c['metrics'] if m['name']=='1.output.h'][0]
            summary.update(first_error_trace=first,original_hidden_comparison=old_failure,replayed_hidden_comparison=this_failure,
                           same_hidden_metric=this_failure==old_failure,dispatch=c['attention'])
    if (e/'ATTN_BUILD.json').is_file():
        build=read(e/'ATTN_BUILD.json'); assert build['library']['sha256']==sha((e/'libfp32_attn.so').read_bytes())
        summary['build']=build
    if app.get('hbm_pool_restored'):
        assert read(e/'pool_return_terminal.json')['passed']
    assert not list(e.glob('perf_*')) and not list(e.rglob('*.pt'))
    charged=sum(1 for q in e.glob('strict_*') if q.is_dir())
    assert observed<=charged<=2
    q=int((native_time(n['startTime'])-native_time(n['createTime'])).total_seconds())
    a=max(node['wallclockDuration'],int((native_time(n['endTime'])-native_time(n['startTime'])).total_seconds()))
    assert 0<=a<=900 and q>=0
    ledger=read(HERE/'BUDGET_LEDGER.json'); assert len(ledger['attempts'])==3
    item=dict(job_id=job,version=VERSION,state=n['state'],host=node['execNode'],domains=1,queue_seconds=q,allocated_seconds=a,
        confirmed_updates=observed,charged_updates=charged,terminal=True,cleanup=True,
        artifact=identity(folder/f'JOB_{job}_TRANSFER.tgz'),native=identity(raw/'djob_final.json'),
        cleanup_source=identity(e/'cleanup.json'),binding=identity(folder/'RUN_BINDING.json'))
    summary['budget_charge']=item; write(folder/'ANALYSIS.json',summary)
    ledger['attempts'].append(item); ledger['allocation_seconds']+=a; ledger['queue_seconds']+=q
    ledger['model_updates']+=charged; ledger['confirmed_model_updates']=sum(x['confirmed_updates'] for x in ledger['attempts'])
    ledger['diagnostic'].update(job_id=job,actual_compute_seconds=duration,actual_allocation_seconds=a)
    write(HERE/'BUDGET_LEDGER.json',ledger)
    write(HERE/'ACTIVE_JOB.json',dict(active_job=None,status='NO_ACTIVE_JOB',last_terminal=item))
    print(job,n['state'],q,a,observed,duration,summary.get('same_hidden_metric'))


if __name__=='__main__':
    settle(*sys.argv[1:])
