"""Validate and settle one native attention run from its returned evidence."""
import re
from statistics import mean, median
import sys

from freeze_attn import HERE, R1, read, write

sys.path.insert(0,str(R1))
from analyze_run import allocator_stats, native_time, resident_hbm, rows, unpack
from verify_dependency import COMPARE_SHA, KML_SHA, check_metrics, identity


def phase(raw, name, topo, bound):
    p=raw/'job_evidence'/name
    strict=name.startswith('strict_')
    candidate='candidate' in name
    expected='PASS_STRICT_ENCODER5' if strict and candidate else 'PASS_STRICT_REFERENCE5' if strict else 'PASS_PERF25'
    count=bound['domain_count']
    steps=5 if strict else 25
    receipt=read(p/'phase_receipt.json')
    assert receipt['status']==expected and receipt['job_id']==topo['context']['job_id']
    assert len(topo['contracts'])==len(receipt['domains'])==count
    build=read(raw/'job_evidence/ATTN_BUILD.json')
    reports, all_rows={},[]
    for n,c in topo['contracts'].items():
        home=p/f'node{n}'; r=read(home/'result.json'); seq=rows(home/'steps.jsonl')
        assert r['status']==expected and r['completed_updates']==steps and r['job_id']==receipt['job_id']
        assert r['host']==topo['context']['host'] and r['checkpoint_layers']==12
        assert [s['step'] for s in seq]==list(range(1,steps+1))
        assert r['cpu36']['errors']==[] and r['cpu36']['receipt']==c
        for k in r['cpu36']['checkpoints']:
            assert k['snapshot']['complete'] and k.get('torch_intraop',36)==36
            assert all(t['affinity'] and set(t['affinity'])<=set(c['selected']) for t in k['snapshot']['threads'])
        a=r['hbm_allocator']
        assert a['sha256']==bound['allocator_sha256'] and a['node']==topo['hbm_pairs'][n]
        assert a['cap_MiB']==bound['hbm_cap_MiB']
        assert all(s['batch_size']==32 and s['native_sgemm_calls']==197 and 0<s['rss_after']['hugetlb_bytes']<=a['cap_MiB']*2**20 for s in seq)
        exposure=read(home/'EXPOSURE_LEDGER.json')
        assert exposure['in_flight'] is None and len(exposure['confirmed_updates'])==steps
        if candidate:
            assert r['attention']['build']==build and r['attention']['bf16']==0 and r['attention']['bq']==64
            assert r['attention']['fallback']=='prohibited'
            assert all(s['fused_attention']['forward']>=12 and s['fused_attention']['backward']==12 for s in seq)
            assert all(sum(s['fused_attention'][k] for s in seq)==r['attention']['counts'][k] for k in ('forward','backward'))
        else:
            assert 'attention' not in r and all(s['fused_attention'] is None for s in seq)
        observed=seq if strict else seq[5:]
        rss_hbm=[(s['rss_after']['rss_bytes']+s['rss_after']['hugetlb_bytes'])/2**20 for s in observed]
        peak_est=[(s['rss_after']['peak_rss_bytes']+s['rss_after']['hugetlb_bytes'])/2**20 for s in observed]
        end_hbm=resident_hbm(home/('strict_end.numa_maps' if strict else 'observe_end.numa_maps'),a['node'])
        assert 0<end_hbm<=a['cap_MiB']
        reports[n]=dict(pure_update_total_seconds=sum(s['step_seconds'] for s in observed),
            pure_update_median_seconds=median(s['step_seconds'] for s in observed),
            step_end_rss_plus_hbm_MiB=rss_hbm,max_domain_peak_estimate_MiB=max(peak_est),
            end_resident_hbm_MiB=end_hbm,allocator_stats=allocator_stats(p/f'node{n}.log'),
            dispatch=r.get('attention'),strict_gate=check_metrics(r['metrics']) if strict and candidate else None)
        all_rows.append(seq)
    for batch in zip(*all_rows):
        assert all(all(r[k]==batch[0][k] for k in ('frame_ids','frame_indices','mask_sha256','release_ns','native_shapes')) for r in batch)
    out=dict(status=expected,domains=reports,domain_count=count)
    if not strict:
        seen=[s[5:] for s in all_rows]
        spans=[(max(s['end_ns'] for s in k)-min(s['start_ns'] for s in k))/1e9 for k in zip(*seen)]
        window=(max(s[-1]['end_ns'] for s in seen)-min(s[0]['start_ns'] for s in seen))/1e9
        slow=max(reports,key=lambda n:reports[n]['pure_update_total_seconds'])
        totals=[r['pure_update_total_seconds'] for r in reports.values()]
        out.update(synchronized_median_seconds=median(spans),synchronized_window_seconds=window,
            synchronized_visits_per_second=count*20*32/window,slowest_domain=slow,
            slowest_vs_median_pct=100*(reports[slow]['pure_update_total_seconds']/median(totals)-1),
            per_domain_visits_per_second={n:20*32/r['pure_update_total_seconds'] for n,r in reports.items()},
            max_sum_of_step_end_samples_MiB=max(map(sum,zip(*(r['step_end_rss_plus_hbm_MiB'] for r in reports.values())))),
            max_domain_peak_estimate_MiB=max(r['max_domain_peak_estimate_MiB'] for r in reports.values()))
    return out


def settle(version, job, digest):
    folder=HERE/version; raw,bundle=unpack(folder,job,digest)
    b=read(folder/'RUN_BINDING.json'); count=b['domain_count']
    for name,sha in {'RUN_BINDING.json':identity(folder/'RUN_BINDING.json')['sha256'],
            'FULL16_PAYLOAD.zip':b['package_sha256'],'SOURCE_SHA256.json':b['source_manifest_sha256'],
            'payload/tests/check_equivalence.py':COMPARE_SHA,'payload/baseline/kml_ops.py':KML_SHA,
            'kml_attn.c':b['kernel_source_sha256'],'payload/attn_dispatch.py':b['dispatch_sha256'],**b['frozen_sidecars']}.items():
        assert identity(raw/name)['sha256']==sha, name
    assert read(raw/'FIXED_INPUTS_BEFORE.json')==read(raw/'FIXED_INPUTS_AFTER.json')
    n,=read(raw/'djob_final.json')['data']['successData']; g,=n['resGroups']
    assert n['jobId']==job and n['user']==b['scheduler_user']=='wujunyi' and n['queue']=='q_hpcai'
    assert n['execPath']==b['remote_root'] and n['state']==bundle['state'] and n['state'] in {'SUCCEEDED','FAILED','CANCELLED'}
    assert n['exclusive'] is True and n['jobWallClockLimit']==b['wall_seconds']
    assert g['resReq']['cpu']==38*count and g['resReq']['mem']==g['resLimit']['mem']==24576*count
    e=raw/'job_evidence'
    out=dict(job_id=job,version=version,requested_domains=count,phases={},partial_worker_results={},gate='NOT_RUN')
    if n['startTime']=='-':
        assert not g['nodeResUsages'] and bundle['pids']==[]
        cleanup=raw/'UNALLOCATED_CLEANUP.json'; assert read(cleanup)['job_id']==job
        qe=native_time(n['endTime']); allocated=updates=charged=0
    else:
        node,=g['nodeResUsages']; assert node['execNode'] in b['eligible_hosts'] and bundle['pids']==[node['pids']]==['-']
        assert g['resAlloc']['cpu']==38*count and g['resAlloc']['mem']==24576*count
        qe=native_time(n['startTime']); allocated=max(node['wallclockDuration'],int((native_time(n['endTime'])-qe).total_seconds()))
        cleanup=e/'cleanup.json'; c=read(cleanup)
        assert c['all_reaped'] and not c['remaining_live'] and not c['remaining_processes']
        app=read(e/'SUMMARY.json'); assert app['job_id']==job
        out.update(application=app,host=node['execNode'])
        updates=sum(len(rows(p)) for p in e.glob('*/node*/steps.jsonl'))
        charged=updates if n['state']=='SUCCEEDED' else count*sum(5 if p.name.startswith('strict_') else 25
                for p in e.iterdir() if p.is_dir() and p.name.startswith(('strict_','perf_')))
        if (e/'ATTN_BUILD.json').is_file():
            build=out['build']=read(e/'ATTN_BUILD.json')
            assert build['source_sha256']==b['kernel_source_sha256']
            assert build['library']['sha256']==identity(e/'libfp32_attn.so')['sha256'] and build['bf16']==0 and build['bq']==64
        if (e/'domain_map.json').is_file():
            topo=read(e/'domain_map.json'); assert len(topo['contracts'])==count
            out['actual_domains']=len(topo['contracts'])
            for p in sorted(e.glob('*/phase_receipt.json')):
                out['phases'][p.parent.name]=phase(raw,p.parent.name,topo,b)
        for p in sorted(e.glob('*/node*/result.json')):
            r=read(p)
            if r['status']!='FAIL_STOP': continue
            failures=[m for m in r['metrics'] if not m['passed']]
            out['partial_worker_results'][str(p.relative_to(e))]=dict(error=r.get('error'),rows=len(r['metrics']),
                failed_metrics=failures,completed_updates=r['completed_updates'],dispatch=r.get('attention'),source=identity(p))
        codes=[x for p in e.glob('*/exit_codes.json') for x in read(p).values()]
        out['SIGBUS_detected']=-7 in codes
        out['OOM_explicit']=bool(re.search(r'out of memory|\bOOM\b',str(n.get('exitMessage'))+str(app.get('error')),re.I))
        if n['state']=='SUCCEEDED':
            assert app['status']=='PASS_FULL_NODE_COMPLETED_PHASES' and app['hbm_pool_restored'] is True
            assert app['hbm_safety']=='CAPACITY_AND_ALLOCATOR_IDENTITY_PASS'
            assert all(read(p)['passed'] for p in e.glob('pool_return_*.json'))
            assert updates==b['max_model_updates'] and app['completed_pairs']==list(range(1,b['pairs']+1))
            assert not out['SIGBUS_detected'] and not out['OOM_explicit']
            out['gate']='PASS'
            if count>1:
                pairs=[]
                for i in app['completed_pairs']:
                    a,c=[out['phases'][f'perf_{role}_r{i}'] for role in ('baseline','candidate')]
                    pairs.append(dict(round=i,improvement_pct=100*(c['synchronized_visits_per_second']/a['synchronized_visits_per_second']-1)))
                medians=[out['phases'][f'perf_candidate_r{i}']['synchronized_median_seconds'] for i in app['completed_pairs']]
                spread=100*(max(medians)-min(medians))/mean(medians)
                out.update(paired_throughput=pairs,candidate_spread_pct=spread)
                if spread>5 or any(p['improvement_pct']<=0 for p in pairs):
                    out['gate']='REJECTED_PERFORMANCE'
        elif any(v['failed_metrics'] for v in out['partial_worker_results'].values()):
            out['gate']='REJECTED_NUMERICAL'
        else:
            out['gate']='FAILED_EXECUTION'
    queued=int((qe-native_time(n['createTime'])).total_seconds())
    assert 0<=updates<=charged<=b['max_model_updates'] and queued>=0
    ledger=read(HERE/'BUDGET_LEDGER.json'); assert b['submission_ordinal']==len(ledger['attempts'])+1
    item=dict(job_id=job,version=version,state=n['state'],host=out.get('host'),domains=count,
        queue_seconds=queued,allocated_seconds=allocated,confirmed_updates=updates,charged_updates=charged,
        terminal=True,cleanup=True,artifact=identity(folder/f'JOB_{job}_TRANSFER.tgz'),native=identity(raw/'djob_final.json'),
        cleanup_source=identity(cleanup),binding=identity(folder/'RUN_BINDING.json'))
    out['budget_charge']=item
    write(folder/'ANALYSIS.json',out)
    ledger['attempts'].append(item)
    ledger['queue_seconds']+=queued; ledger['allocation_seconds']+=allocated; ledger['model_updates']+=charged
    write(HERE/'BUDGET_LEDGER.json',ledger)
    write(HERE/'ACTIVE_JOB.json',dict(active_job=None,status='NO_ACTIVE_JOB',last_terminal=item))
    if out['gate']=='PASS':
        write(HERE/f'{count}DOMAIN_GATE.json',dict(status='PASS',job_id=job,analysis=identity(folder/'ANALYSIS.json'),
            kernel_source_sha256=b['kernel_source_sha256'],dispatch_sha256=b['dispatch_sha256'],locking_kml=out['build']['locking_kml']))
    print(job,n['state'],out['gate'],queued,allocated,updates,[(k,v['error']) for k,v in out['partial_worker_results'].items()])


if __name__=='__main__':
    settle(*sys.argv[1:])
