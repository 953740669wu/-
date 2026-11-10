"""Verify and count independently completed updates in two fixed windows."""
from statistics import mean, median
import sys

from freeze_ab import HERE, R1, read, sha, write

sys.path.insert(0,str(R1))
from analyze_run import allocator_stats, native_time, resident_hbm, rows, unpack
from verify_dependency import check_metrics, identity

WINDOW = 600
NS = 10**9
BATCH = 32


def arm_metrics(e, arm, topo, pairing, binding, job):
    path=e/arm; w=read(path/'WINDOW.json'); receipt=read(path/'phase_receipt.json')
    start,end=w['open_ns'],w['close_ns']
    assert end-start==WINDOW*NS and receipt['status']=='PASS_FIXED_WINDOW' and receipt['job_id']==job
    assert receipt['window']==w and set(receipt['domains'])==set(topo['contracts'])
    bar=path/'barriers'
    release={int(p.stem):read(p) for p in bar.glob('*.release')}
    assert set(range(1,7))<=set(release) and release[6]['release_at_ns']==start
    if arm=='B':
        assert set(release)==set(range(1,7))
        assert all(int(p.name.split('.')[0])<=6 for p in bar.glob('*.ready'))
    domains={}
    for n,contract in topo['contracts'].items():
        d=path/f'node{n}'; r=read(d/'result.json'); seq=rows(d/'steps.jsonl')
        assert r['job_id']==job and r['host']==topo['context']['host'] and r['window']==w
        assert r['status']=='PASS_FIXED_WINDOW' and len(seq)==r['completed_updates']==receipt['domains'][n]
        assert len(seq)>=5 and [x['step'] for x in seq]==list(range(1,len(seq)+1))
        assert r['cpu36']['errors']==[] and r['cpu36']['receipt']==contract and r['checkpoint_layers']==12
        for check in r['cpu36']['checkpoints']:
            assert check['snapshot']['complete'] and check.get('torch_intraop',36)==36
            assert all(t['affinity'] and set(t['affinity'])<=set(contract['selected']) for t in check['snapshot']['threads'])
        warm_gate=check_metrics(r['metrics']); assert warm_gate['rows']==15
        h=r['hbm_allocator']; assert h['node']==topo['hbm_pairs'][n] and h['sha256']==binding['allocator_sha256'] and h['cap_MiB']==3800
        resident=resident_hbm(d/'observe_end.numa_maps',h['node']); assert 0<resident<=3800
        xledger=read(d/'EXPOSURE_LEDGER.json'); assert not xledger['in_flight'] and len(xledger['confirmed_updates'])==len(seq)
        for x in seq:
            k=x['step']; slot=(k-1)%25
            assert x['sequence_slot']==slot+1 and x['sequence_cycle']==(k-1)//25
            assert x['frame_indices']==pairing['order'][slot*BATCH:(slot+1)*BATCH] and x['mask_sha256']==pairing['mask_sha256'][slot]
            assert x['batch_size']==BATCH and x['native_sgemm_calls']==197
            assert x['start_ns']<x['end_ns'] and abs(x['step_seconds']-(x['end_ns']-x['start_ns'])/NS)<1e-9
            assert 0<x['rss_after']['hugetlb_bytes']<=3800*2**20
            if k<=6 or arm=='A':
                t=release[k]; assert t['step']==k and str(t['arrivals'][n]['pid'])==str(r['pid'])
                assert x['release_ns']==t['release_at_ns'] and x['start_ns']>=x['release_ns']
            else:
                assert x['release_ns'] is None
        assert all(x['end_ns']<=start for x in seq[:5])
        assert all(start<=x['start_ns']<end for x in seq[5:])
        inside=[x for x in seq[5:] if x['end_ns']<=end]
        cross=[x for x in seq[5:] if x['end_ns']>end]
        assert len(cross)<=1
        waits=r['barrier_waits']; steps=[x['step'] for x in waits]
        assert steps==list(range(1,len(steps)+1)) and len(steps)>=6
        assert all(x['start_ns']<=x['end_ns'] for x in waits)
        assert len(steps)==6 if arm=='B' else len(steps) in (len(seq),len(seq)+1)
        obs_waits=[max(0,min(x['end_ns'],end)-max(x['start_ns'],start))/NS for x in waits if x['step']>6]
        durations=[x['step_seconds'] for x in inside]
        all_durations=[x['step_seconds'] for x in seq[5:]]
        warm_seen={i for x in seq[:5] for i in x['frame_indices']}; seen=warm_seen.copy(); repeat=0
        for x in inside:
            repeat+=sum(i in seen for i in x['frame_indices']); seen.update(x['frame_indices'])
        domains[n]=dict(completed_in_window=len(inside),frame_visits=len(inside)*BATCH,frame_visits_per_second=len(inside)*BATCH/WINDOW,
             warmup_step_seconds=[x['step_seconds'] for x in seq[:5]],
             pure_train_median_seconds=median(durations) if durations else None,
             pure_train_mean_seconds=mean(durations) if durations else None,pure_train_total_seconds=sum(durations),
             pure_train_median_including_cross_seconds=median(all_durations) if all_durations else None,
             per_step_barrier_wait_seconds=sum(obs_waits),per_step_barrier_wait_events=len(obs_waits),
             opening_wait_seconds=(waits[5]['end_ns']-waits[5]['start_ns'])/NS,
             cross_window_steps=[dict(step=x['step'],start_ns=x['start_ns'],end_ns=x['end_ns'],after_close_seconds=(x['end_ns']-end)/NS) for x in cross],
             repeated_frame_visits_since_warmup=repeat,unique_frames_in_window=len({i for x in inside for i in x['frame_indices']}),
             warmup_check=warm_gate,hbm_end_MiB=resident,allocator=allocator_stats(path/f'node{n}.log'),
             steps=identity(d/'steps.jsonl'),worker=identity(d/'result.json'))
    spent=sum(receipt['domains'].values()); assert spent<=receipt['updates_reserved']<=2000
    frame_visits=sum(d['frame_visits'] for d in domains.values())
    slow=max(domains,key=lambda n:domains[n]['pure_train_median_including_cross_seconds'] or -1)
    least=min(domains,key=lambda n:(domains[n]['completed_in_window'],-(domains[n]['pure_train_median_including_cross_seconds'] or 0)))
    return dict(window=w,domain_count=16,domains=domains,frame_visits=frame_visits,frame_visits_per_second=frame_visits/WINDOW,
        cross_window_updates=sum(len(d['cross_window_steps']) for d in domains.values()),
        repeated_frame_visits_since_warmup=sum(d['repeated_frame_visits_since_warmup'] for d in domains.values()),
        slowest_by_pure_median=slow,least_window_output_domain=least,updates_started=spent,updates_reserved=receipt['updates_reserved'])


def compare(a,b,host):
    delta=b['frame_visits']-a['frame_visits']
    per={n:b['domains'][n]['frame_visits']-v['frame_visits'] for n,v in a['domains'].items()}
    ids={a['slowest_by_pure_median'],b['slowest_by_pure_median']}
    if host=='cn22035':ids.add('12')
    impact={}
    for n in sorted(ids,key=int):
        arms={}
        for label,v in (('A',a),('B',b)):
            d=v['domains'][n]; others=[x for k,x in v['domains'].items() if k!=n]; other=mean(x['frame_visits'] for x in others)
            arms[label]=dict(frame_visits=d['frame_visits'],frame_visits_per_second=d['frame_visits_per_second'],
                mean_other_domain_visits=other,deficit_vs_mean_other_frames=other-d['frame_visits'],
                deficit_vs_mean_other_frames_per_second=(other-d['frame_visits'])/WINDOW,
                deficit_vs_mean_other_pct=100*(other-d['frame_visits'])/other if other else None,
                pure_train_median_seconds=d['pure_train_median_including_cross_seconds'],
                median_other_domain_pure_train_seconds=median(x['pure_train_median_including_cross_seconds'] for x in others
                                                              if x['pure_train_median_including_cross_seconds'] is not None))
        impact[n]=dict(**arms,delta_frames=per[n],other_15_delta_frames=delta-per[n],
                       delta_frames_per_second=per[n]/WINDOW,other_15_delta_frames_per_second=(delta-per[n])/WINDOW)
    return dict(delta_frame_visits=delta,delta_frame_visits_per_second=delta/WINDOW,
        B_vs_A_pct=100*delta/a['frame_visits'] if a['frame_visits'] else None,
        per_domain_delta_frame_visits=per,slow_domain_and_other_contributions=impact,
        historical_cn22035_node12_pure_slowest={k:v['slowest_by_pure_median']=='12' for k,v in (('A',a),('B',b))} if host=='cn22035' else None)


def settle(job,digest):
    folder=HERE/'AB_D16'; raw,bundle=unpack(folder,job,digest); e=raw/'job_evidence'
    b=read(folder/'RUN_BINDING.json'); assert (raw/'RUN_BINDING.json').read_bytes()==(folder/'RUN_BINDING.json').read_bytes()
    assert sha((raw/'FULL16_PAYLOAD.zip').read_bytes())==b['package_sha256']
    assert sha((raw/'SOURCE_SHA256.json').read_bytes())==b['source_manifest_sha256']
    for name,h in (read(raw/'SOURCE_SHA256.json')|b['frozen_sidecars']).items():
        assert sha((raw/name).read_bytes())==h,name
    assert read(raw/'FIXED_INPUTS_BEFORE.json')==read(raw/'FIXED_INPUTS_AFTER.json')
    n,=read(raw/'djob_final.json')['data']['successData']; g,=n['resGroups']
    assert n['jobId']==job and n['user']=='wujunyi' and n['queue']=='q_hpcai' and n['execPath']==b['remote_root']
    assert n['state']==bundle['state'] and n['state'] in ('SUCCEEDED','FAILED','CANCELLED') and n['exclusive'] is True
    assert n['jobWallClockLimit']==7200 and g['resReq']['cpu']==608 and g['resReq']['mem']==g['resLimit']['mem']==393216
    out=dict(job_id=job,state=n['state'],arms={},status='INCOMPLETE_PAIR')
    updates=0
    if n['startTime']=='-':
        assert not g['nodeResUsages'] and bundle['pids']==[]
        c=raw/'UNALLOCATED_CLEANUP.json'; assert read(c)['job_id']==job
        end_queue=native_time(n['endTime']); allocation=0
    else:
        node,=g['nodeResUsages']; assert node['execNode']=='cn22035' and bundle['pids']==[node['pids']]==['-']
        assert g['resAlloc']['cpu']==608 and g['resAlloc']['mem']==393216
        end_queue=native_time(n['startTime'])
        allocation=max(node['wallclockDuration'],int((native_time(n['endTime'])-end_queue).total_seconds()))
        c=e/'cleanup.json'; clean=read(c); assert clean['all_reaped'] and not clean['remaining_live'] and not clean['remaining_processes']
        app=read(e/'SUMMARY.json'); assert app['job_id']==job
        out.update(host=node['execNode'],application=app)
        if (e/'domain_map.json').is_file():
            topo=read(e/'domain_map.json'); assert len(topo['contracts'])==16 and len(topo['context']['allowed'])==608
            assert all(len(d['allocated'])==38 and len(d['selected'])==36 and len(d['reserved'])==2 for d in topo['contracts'].values())
            out['resources']=dict(actual_domains=16,allocated_cpus=608,compute_cpus=576,reserved_cpus=32,
                DDR_requested_MB=393216,DDR_allocated_MB=393216,DDR_limit_MB=393216,exclusive=True,
                HBM_cap_MiB_per_domain=b['hbm_cap_MiB'],HBM_cpu_domain_mapping=topo['hbm_pairs'])
            capacity=e/'hbm_capacity_before.json'
            if capacity.is_file():out['resources']['HBM_before']=read(capacity)
            p=read(raw/'PRIOR_PAIRING.json')
            for arm in ('A','B'):
                if (e/arm/'phase_receipt.json').is_file():out['arms'][arm]=arm_metrics(e,arm,topo,p,b,job)
        counts=e/'update_budget_cleanup.json'
        if counts.is_file():
            counter=read(counts); assert counter['removed'] and all(0<=v<=2000 for v in counter['reservations'].values())
            updates=sum(counter['reservations'].values())
        observed=sum(len(rows(p)) for p in e.glob('*/node*/steps.jsonl'))
        if not counts.is_file() and observed:
            updates=4000
        assert observed<=updates<=4000
        out['logged_updates']=observed
        out['partial_step_rows']={arm:{q.parent.name:len(rows(q)) for q in (e/arm).glob('node*/steps.jsonl')}
                                  for arm in ('A','B') if (e/arm).is_dir() and arm not in out['arms']}
        if n['state']=='SUCCEEDED':
            assert app['status']=='PASS_FULL_NODE_COMPLETED_PHASES' and app['completed_arms']==['A','B']
            assert app['hbm_safety']=='PASS' and app['hbm_pool_restored'] and set(out['arms'])=={'A','B'}
            assert all(read(e/f'pool_return_{arm}.json')['passed'] for arm in ('A','B','terminal'))
            a,z=(out['arms'][arm] for arm in ('A','B'))
            assert a['window']['close_ns']<z['window']['open_ns'] and a['updates_started']+z['updates_started']==observed
            for i in range(16):
                for aa,bb in zip(rows(e/f'A/node{i}/steps.jsonl'),rows(e/f'B/node{i}/steps.jsonl')):
                    assert all(aa[k]==bb[k] for k in ('step','frame_indices','frame_ids','mask_sha256','native_shapes'))
            out.update(status='COMPLETE_ONE_PAIRED_ENGINEERING_RUN',comparison=compare(a,z,node['execNode']))
    queue=int((end_queue-native_time(n['createTime'])).total_seconds())
    assert 0<=allocation<=7200 and queue>=0
    ledger=read(HERE/'BUDGET_LEDGER.json'); assert not ledger['attempts']
    item=dict(job_id=job,state=n['state'],host=out.get('host'),terminal=True,cleanup=True,allocation_seconds=allocation,
              queue_seconds=queue,updates_reserved=updates,archive=identity(folder/f'JOB_{job}_TRANSFER.tgz'),
              native=identity(raw/'djob_final.json'),cleanup_source=identity(c))
    ledger.update(status='CLOSED',attempts=[item],allocation_seconds=allocation,queue_seconds=queue,updates=updates)
    write(HERE/'BUDGET_LEDGER.json',ledger)
    write(HERE/'ACTIVE_JOB.json',dict(active_job=None,status='NO_ACTIVE_JOB',last_terminal=item))
    write(folder/'ANALYSIS.json',out)
    print(job,out['status'],allocation,updates,[(k,v['frame_visits']) for k,v in out['arms'].items()])


if __name__=='__main__': settle(*sys.argv[1:])
