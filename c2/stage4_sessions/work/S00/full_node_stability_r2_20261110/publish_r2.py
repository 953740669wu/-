"""Publish the R2 decision with returned native and per-domain evidence."""
from settle_r2 import HERE, identity, read, save


def publish():
    ledger=read(HERE/'BUDGET_LEDGER.json')
    assert read(HERE/'ACTIVE_JOB.json')['active_job'] is None
    assert all(a['terminal'] and a['cleanup'] for a in ledger['attempts'])
    outcomes={}
    for batch in (32,64):
        file=HERE/f'B{batch}_ACCEPTANCE.json'
        outcomes[f'B{batch}']=read(file) if file.is_file() else dict(status='NOT_RUN')
    jobs=[]
    evidence=[HERE/name for name in ('ACTUAL_COMMANDS.md','SESSION_STATUS.md','ROUND_DELTA.md','R1_TIMING_RECHECK.json',
        'BUDGET_LEDGER.json','ACTIVE_JOB.json','DIAGNOSIS.md','freeze_r2.py','settle_r2.py','publish_r2.py','R2_PREFLIGHT_EVIDENCE.tgz',
        'preflight/NUMA_STABILITY_BLOCKED_RESULT.json','preflight/BUDGET_LEDGER_BLOCKED.json')]
    lines=['# R2 全节点速度稳定性','',
           '原 R1 cn21762 的 B32 波动为 15.37%。本批用同节点、同分配的两臂比较验证延后有限性扫描，原数值、工作量和计时定义保持。','']
    for a in ledger['attempts']:
        folder=HERE/a['version']
        run=read(folder/'ANALYSIS.json')
        binding=read(folder/'RUN_BINDING.json')
        strict=[d['strict_gate'] for name,p in run['phases'].items() if name.startswith('strict_candidate')
                for d in p['domains'].values()]
        receipt=dict(**a,status=run['status'],numeric_rows=sum(d['rows'] for d in strict),
                     max_abs=max((d['max_abs'] for d in strict),default=None),
                     max_rel_L2=max((d['max_rel_L2'] for d in strict),default=None),
                     hbm_safety=run.get('application',{}).get('hbm_safety'),
                     hbm_pool_restored=run.get('application',{}).get('hbm_pool_restored'),
                     faults={k:run.get(k) for k in ('SIGBUS_detected','SIGKILL_detected','OOM_explicit')},
                     candidate_worker_sha256=binding['candidate_worker_sha256'],analysis=identity(folder/'ANALYSIS.json'))
        jobs.append(receipt)
        evidence.extend(folder/name for name in ('RUN_BINDING.json','MINIMAL.diff','SOURCE_SHA256.json',
            'FULL16_PAYLOAD.zip','FROZEN_HBM_ALLOCATOR.so','ANALYSIS.json'))
        evidence.extend((folder/f'JOB_{a["job_id"]}_TRANSFER.tgz',folder/'received/djob_final.json'))
        lines.append(f'- {a["job_id"]}，B{a["batch"]}，{a["host"] or "未获配"}，{a["state"]}。严格检查 {receipt["numeric_rows"]} 项，最大绝对差 {receipt["max_abs"]}，清理已核。')
    for name,outcome in outcomes.items():
        lines.extend(['',f'## {name}','',outcome['status']])
        if outcome.get('pairs'):
            for i,p in sorted(outcome['pairs'].items()):
                a,b=p['original'],p['deferred']
                lines.append(f'- 第 {i} 对，{p["host"]}。同步中位步时 {a["median_synchronized_step_seconds"]:.3f} → {b["median_synchronized_step_seconds"]:.3f} 秒，吞吐 {a["synchronized_window_visits_per_second"]:.3f} → {b["synchronized_window_visits_per_second"]:.3f} 帧次/秒。扫描与其他域更新重叠的中位数 {a["median_overlap_domain_seconds"]:.3f} → {b["median_overlap_domain_seconds"]:.3f} 域秒。最慢域 {a["slowest_domain"]} → {b["slowest_domain"]}，各域步末合计采样最高 {a["max_sum_of_step_end_samples_MiB"]:.1f} → {b["max_sum_of_step_end_samples_MiB"]:.1f} MiB。')
        if 'spread_pct' in outcome:
            s=outcome['spread_pct']
            lines.append(f'三轮波动 {s["original"]:.2f}% → {s["deferred"]:.2f}%，三对观测窗合并吞吐变化 {outcome["paired_gain_pct"]:+.2f}%。')
    extra=[HERE/name for name in ('CN22036_SLOW_DOMAIN.json','CN22044_ALLOCATION_MISMATCH.json',
                                 'B32_C1_W2/CN22044_NATIVE_TOPOLOGY_AFTER.json')]
    if all(p.is_file() for p in extra):
        evidence.extend(extra)
        lines.extend(['','cn22036 原版 HBM 严格阶段的域 4 连续三步耗时 265.06、266.77、273.76 秒，相邻域约 10–11 秒。由原生调度器有序停止，候选和性能阶段尚未进入。相同分配内的进程 CPU 时间显示域 4 在慢步中仍有约 33.6 个核的 CPU 活动当量，原因未定位。',
                      'cn22044 注册拓扑有 16 域，但实际原生作业 CPU 集为 0–569。核 570–607 所属的第 16 域未进入该作业，门禁在启动 worker 前停止。两台实际主机上限已用，当前无法交完整同节点 A/B。'])
    lines.extend(['','各域步末内存采样时刻可不同，联合内存峰值未测。跨节点历史表现用于定位，软件效果只看本批同分配配对。','',
                  f'累计 {len(ledger["attempts"])}/6 次提交、排队 {ledger["queue_seconds"]} 秒、分配 {ledger["allocation_seconds"]} 秒、记账 {ledger["model_updates"]} 次更新。当前无活动作业。'])
    summary=HERE/'SUMMARY.md'
    summary.write_bytes(('\n'.join(lines)+'\n').encode())
    evidence.append(summary)
    evidence.extend(HERE/f'B{b}_ACCEPTANCE.json' for b in (32,64) if (HERE/f'B{b}_ACCEPTANCE.json').is_file())
    b32_status=outcomes['B32']['status']
    decision=('UNRESOLVED_NO_COMPLETE_PAIRED_AB' if b32_status=='INCOMPLETE_PAIRS' else b32_status)
    report=dict(status='TERMINAL',decision=decision,active_job=None,scheduler_user='wujunyi',outcomes=outcomes,jobs=jobs,
                budget=ledger,r1_failure_retained=True,node_avoidance_separated=True,
                evidence_index=[identity(p) for p in evidence])
    save(HERE/'NUMA_STABILITY_RESULT.json',report)
    print(HERE/'NUMA_STABILITY_RESULT.json')


if __name__=='__main__':
    publish()
