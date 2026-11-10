"""Check the returned R2 evidence and settle one native allocation."""
import re
from statistics import mean, median
import sys

from freeze_r2 import HERE, R1

sys.path.insert(0, str(R1))
from analyze_run import native_time, phase, rows, unpack
from verify_dependency import COMPARE_SHA, KML_SHA, identity, read, save


def timing(raw, label, domains):
    p = raw/'job_evidence'/label
    deferred = '_deferred' in label
    all_rows = {n:rows(p/f'node{n}'/'steps.jsonl') for n in domains}
    assert all(read(p/f'node{n}'/'result.json')['validation_after_all_updates'] is deferred for n in domains)
    observed = []
    for i, group in enumerate(zip(*all_rows.values()),1):
        group = dict(zip(domains,group))
        earliest = min(r['start_ns'] for r in group.values())
        latest = max(r['end_ns'] for r in group.values())
        assert all(r['release_ns'] <= r['start_ns'] <= r['end_ns'] <= r['validation_start_ns']
                   <= r['validation_end_ns'] for r in group.values())
        release = p/'barriers'/f'done-{i}.release'
        if deferred:
            done = read(release)
            assert done['step'] == f'done-{i}' and done['release_at_ns'] >= latest
            assert set(map(str,done['arrivals'])) == set(domains)
            assert all(r['end_ns'] <= done['arrivals'][n]['arrived'] <= done['release_at_ns'] <= r['validation_start_ns']
                       for n,r in group.items())
        else:
            assert not release.exists()
        if i < 6:
            continue
        overlap = sum(max(0,min(r['validation_end_ns'],latest)-r['validation_start_ns']) for r in group.values())
        if deferred:
            assert overlap == 0
        observed.append(dict(step=i, last_domain=max(group,key=lambda n:group[n]['end_ns']),
             start_skew_seconds=(max(r['start_ns'] for r in group.values())-earliest)/1e9,
             validation_overlap_domain_seconds=overlap/1e9,
             domain_timing={n:dict(update_seconds=r['step_seconds'],
                  end_to_validation_seconds=(r['validation_start_ns']-r['end_ns'])/1e9,
                  validation_seconds=(r['validation_end_ns']-r['validation_start_ns'])/1e9,
                  start_from_release_seconds=(r['start_ns']-r['release_ns'])/1e9)
                  for n,r in group.items()}))
    return dict(steps=observed,median_overlap_domain_seconds=median(r['validation_overlap_domain_seconds'] for r in observed))


def settle(version, job, transfer_sha):
    folder = HERE/version
    raw, transfer = unpack(folder,job,transfer_sha)
    binding = read(folder/'RUN_BINDING.json')
    for name, digest in {'RUN_BINDING.json':identity(folder/'RUN_BINDING.json')['sha256'],
                         'SOURCE_SHA256.json':binding['source_manifest_sha256'],
                         'FULL16_PAYLOAD.zip':binding['package_sha256'],
                         'payload/tests/check_equivalence.py':COMPARE_SHA,
                         'payload/baseline/kml_ops.py':KML_SHA,
                         **binding['frozen_sidecars']}.items():
        assert identity(raw/name)['sha256']==digest, name
    assert read(raw/'FIXED_INPUTS_BEFORE.json') == read(raw/'FIXED_INPUTS_AFTER.json')
    native, = read(raw/'djob_final.json')['data']['successData']
    assert native['jobId']==job and native['user']==binding['scheduler_user']=='wujunyi'
    assert native['state']==transfer['state'] and native['state'] in {'SUCCEEDED','FAILED','CANCELLED'}
    assert native['execPath']==binding['remote_root'] and native['queue']=='q_hpcai'
    assert native['exclusive'] is True and native['jobWallClockLimit']==binding['wall_seconds']
    group, = native['resGroups']
    assert group['resReq']['cpu']==608 and group['resReq']['mem']==group['resLimit']['mem']==393216
    evidence=raw/'job_evidence'
    report=dict(job_id=job,version=version,batch=binding['batch_size'],candidate=binding['candidate'],
                scheduler_state=native['state'],phases={},pairs={})
    if native['startTime']=='-':
        assert not group['nodeResUsages'] and transfer['pids']==[]
        cleanup=raw/'UNALLOCATED_CLEANUP.json'
        assert read(cleanup)['job_id']==job
        queue_end=native_time(native['endTime'])
        allocated=updates=0
        report['status']='NOT_ALLOCATED'
    else:
        node, = group['nodeResUsages']
        assert group['resAlloc']['cpu']==608 and group['resAlloc']['mem']==393216
        assert node['execNode'] in binding['eligible_hosts'] and transfer['pids']==[node['pids']]==['-']
        queue_end=native_time(native['startTime'])
        allocated=max(node['wallclockDuration'],int((native_time(native['endTime'])-queue_end).total_seconds()))
        cleanup=evidence/'cleanup.json'
        cleaned=read(cleanup)
        assert cleaned['all_reaped'] and not cleaned['remaining_live'] and not cleaned['remaining_processes']
        app=read(evidence/'SUMMARY.json')
        assert app['job_id']==job
        updates=sum(len(rows(p)) for p in evidence.glob('*/node*/steps.jsonl'))
        report.update(host=node['execNode'],status=app['status'],application=app,
                      native_peak_MiB=node.get('memMax'),native_swap_peak_MiB=node.get('swapMax'))
        codes=[read(p)['exit_code'] for p in evidence.glob('real_hbm_node*/real_probe.exit.json')]
        codes.extend(x for p in evidence.glob('*/exit_codes.json') for x in read(p).values())
        err=' '.join(str(v) for v in (native.get('exitMessage'),app.get('error'),app.get('cleanup_error')))
        report.update(SIGBUS_detected=-7 in codes,SIGKILL_detected=-9 in codes,
                      OOM_explicit=bool(re.search(r'out of memory|\bOOM\b',err,re.I)))
        if (evidence/'domain_map.json').is_file():
            topo=read(evidence/'domain_map.json')
            for receipt in sorted(evidence.glob('*/phase_receipt.json')):
                label=receipt.parent.name
                result=phase(raw,label,topo,binding)
                if label.startswith('perf_'):
                    result['validation_timing']=timing(raw,label,list(topo['contracts']))
                report['phases'][label]=result
        if app['status']=='PASS_FULL_NODE_COMPLETED_PHASES':
            assert native['state']=='SUCCEEDED' and app['hbm_safety']=='PASS' and app['hbm_pool_restored'] is True
            assert not any(report[k] for k in ('SIGBUS_detected','SIGKILL_detected','OOM_explicit'))
            assert len(list(evidence.glob('real_hbm_node*/RECEIPT.json')))==16
            assert all(read(p)['passed'] for p in evidence.glob('pool_return_*.json'))
            assert updates==16*(15+50*len(app['completed_pairs']))
            for n in app['completed_pairs']:
                report['pairs'][str(n)]={arm:f'perf_candidate_{arm}_r{n}' for arm in ('original','deferred')}
    queued=int((queue_end-native_time(native['createTime'])).total_seconds())
    if native['state']=='SUCCEEDED' or not allocated:
        charged=updates
    else:
        # An interrupted phase may have applied an update before publishing its row.
        # Charge all possible updates in directories reached by this frozen launcher.
        charged=16*sum(5 if p.name.startswith('strict_') else 25 for p in evidence.iterdir()
                       if p.is_dir() and p.name.startswith(('strict_','perf_')))
    assert 0<=updates<=charged<=binding['max_model_updates'] and queued>=0
    ledger=read(HERE/'BUDGET_LEDGER.json')
    assert binding['submission_ordinal']==len(ledger['attempts'])+1
    item=dict(job_id=job,host=report.get('host'),version=version,batch=binding['batch_size'],
              queue_seconds=queued,allocated_seconds=allocated,confirmed_updates=updates,charged_updates=charged,
              terminal=True,cleanup=True,state=native['state'],artifact=identity(folder/f'JOB_{job}_TRANSFER.tgz'),
              binding=identity(folder/'RUN_BINDING.json'),cleanup_source=identity(cleanup),native=identity(raw/'djob_final.json'))
    save(folder/'ANALYSIS.json',report)
    ledger['attempts'].append(item)
    ledger['allocation_seconds']+=allocated
    ledger['queue_seconds']+=queued
    ledger['model_updates']+=charged
    save(HERE/'BUDGET_LEDGER.json',ledger)
    save(HERE/'ACTIVE_JOB.json',dict(active_job=None,status='NO_ACTIVE_JOB',last_terminal=item))
    print(job,report['status'],report.get('host'),allocated,updates,report['pairs'])


def compare(batch):
    ledger=read(HERE/'BUDGET_LEDGER.json')
    pairs={}
    jobs=[]
    worker_shas=set()
    for item in ledger['attempts']:
        if item['batch']!=batch:
            continue
        path=HERE/item['version']/'ANALYSIS.json'
        report=read(path)
        jobs.append(identity(path))
        if report['pairs']:
            worker_shas.add(read(HERE/item['version']/'RUN_BINDING.json')['candidate_worker_sha256'])
        for i, labels in report['pairs'].items():
            assert i not in pairs
            pair=dict(job_id=item['job_id'],host=item['host'])
            for arm,label in labels.items():
                p=report['phases'][label]
                pair[arm]={k:p[k] for k in ('median_synchronized_step_seconds','synchronized_window_seconds',
                    'synchronized_window_visits_per_second','slowest_domain','slowest_pure_total_vs_median_pct',
                    'max_sum_of_step_end_samples_MiB','sum_per_domain_peak_estimates_MiB')}
                pair[arm]['median_overlap_domain_seconds']=p['validation_timing']['median_overlap_domain_seconds']
            pairs[i]=pair
    outcome=dict(batch=batch,pairs=pairs,jobs=jobs,status='INCOMPLETE_PAIRS')
    if set(pairs)=={'1','2','3'}:
        assert len({p['host'] for p in pairs.values()})==len(worker_shas)==1
        medians={arm:[pairs[str(i)][arm]['median_synchronized_step_seconds'] for i in range(1,4)] for arm in ('original','deferred')}
        spreads={arm:100*(max(v)-min(v))/mean(v) for arm,v in medians.items()}
        windows={arm:sum(p[arm]['synchronized_window_seconds'] for p in pairs.values()) for arm in medians}
        gain=100*(windows['original']/windows['deferred']-1)
        status='ACCEPTED_PAIRED_STABLE' if spreads['deferred']<=5 and gain>=0 else 'REJECTED_STABILITY_OR_THROUGHPUT'
        outcome.update(status=status,median_seconds=medians,spread_pct=spreads,window_seconds=windows,paired_gain_pct=gain)
    save(HERE/f'B{batch}_ACCEPTANCE.json',outcome)
    print(outcome['status'],outcome.get('spread_pct'),outcome.get('paired_gain_pct'))


if __name__=='__main__':
    if sys.argv[1]=='compare':
        compare(int(sys.argv[2]))
    else:
        settle(*sys.argv[1:])
