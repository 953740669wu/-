"""Publish the verified pair and the sixteen physical-domain rows."""
from settle_ab import HERE, identity, read, write


def value(x):
    return '—' if x is None else f'{x:.2f}'


def publish():
    folder=HERE/'AB_D16'; raw=folder/'received'; e=raw/'job_evidence'
    report=read(folder/'ANALYSIS.json'); ledger=read(HERE/'BUDGET_LEDGER.json')
    assert len(ledger['attempts'])==1 and read(HERE/'ACTIVE_JOB.json')['active_job'] is None
    b=read(folder/'RUN_BINDING.json'); job=report['job_id']; arms=report['arms']; summary=HERE/'SUMMARY.md'
    lines=['# 16 域固定窗逐步屏障 A/B','',
           f'作业 {job}，cn22035，原 32 电极 B32、FP32 SDPA、CKPT12、HBM。A 后 B 串行，各共同预热 5 步，统一开窗后各 600 秒。',
           '在窗内开始且完成的更新逐域计 32 帧次。跨窗仅单列。固定样本和掩码每本域 25 步循环。','']
    if 'comparison' in report:
        a,z=arms['A'],arms['B']; cmp=report['comparison']
        lines.extend([f'A {a["frame_visits"]} 帧次、{a["frame_visits_per_second"]:.2f} 帧次/秒，B {z["frame_visits"]} 帧次、{z["frame_visits_per_second"]:.2f} 帧次/秒，B 相对 A {cmp["B_vs_A_pct"]:+.2f}%。',
            f'A/B 跨窗更新 {a["cross_window_updates"]}/{z["cross_window_updates"]}。相对本臂已访问样本的重复帧次 {a["repeated_frame_visits_since_warmup"]}/{z["repeated_frame_visits_since_warmup"]}。',
            f'A/B 按纯训练步中位数的最慢物理域为 {a["slowest_by_pure_median"]}/{z["slowest_by_pure_median"]}。',
            '', '| 物理域 | A 步 | A 帧次/秒 | A 纯训练中位秒 | A 逐步等待秒 | B 步 | B 帧次/秒 | B 纯训练中位秒 | B 逐步等待秒 |',
            '| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |'])
        for n in sorted(a['domains'],key=int):
            fields=[n]
            for d in (a['domains'][n],z['domains'][n]):
                fields.extend((str(d['completed_in_window']),value(d['frame_visits_per_second']),
                               value(d['pure_train_median_seconds']),value(d['per_step_barrier_wait_seconds'])))
            lines.append('| '+' | '.join(fields)+' |')
        lines.extend(['','表内纯训练中位数只用窗内完成的步。最慢域判定也纳入窗内开始但跨窗的步，以免忽略慢步。逐步等待只计第七步及以后与观测窗重叠的时间，包含 A 在截止处未获放行的等待。',''])
        for n,d in cmp['slow_domain_and_other_contributions'].items():
            lines.append(f'- 域 {n} 的 A→B 贡献 {d["delta_frames"]:+} 帧次，其余 15 域合计 {d["other_15_delta_frames"]:+} 帧次。B 中该域相对其余域平均的差值为 {-d["B"]["deficit_vs_mean_other_frames"]:+.1f} 帧次，折合 {-d["B"]["deficit_vs_mean_other_frames_per_second"]:+.2f} 帧次/秒。')
        slow=z['slowest_by_pure_median']
        lines.extend(['',f'域 {slow} 的第 5 个共同预热步在 A/B 分别为 {a["domains"][slow]["warmup_step_seconds"][4]:.2f} / {z["domains"][slow]["warmup_step_seconds"][4]:.2f} 秒，当时两组均使用逐步屏障。固定顺序单次配对的总增量包含运行状态变化，无法从本次数据分离屏障的纯因果贡献。',
                      f'历史慢域 12 在 A/B 窗内的纯训练中位步时为 {a["domains"]["12"]["pure_train_median_seconds"]:.2f} / {z["domains"]["12"]["pure_train_median_seconds"]:.2f} 秒。本次的重度长尾出现在域 {slow}，原三轮稳定性结果沿用。'])
        cmp['interpretation']='Observed fixed-order engineering contrast; arm B slow-domain recovery was already visible during synchronized warmup, so the throughput delta does not identify the isolated causal effect of removing the barrier.'
    else:
        lines.append(f'只核实完整窗口 {list(arms)}。本次未形成完整 A/B，未给出速度变化结论。')
    lines.extend(['',f'累计一次原生提交、排队 {ledger["queue_seconds"]} 秒、分配 {ledger["allocation_seconds"]} 秒、更新预算计数 {ledger["updates"]}/4000。当前无活动作业。'])
    summary.write_bytes(('\n'.join(lines)+'\n').encode())
    paths=[HERE/n for n in ('ACTUAL_COMMANDS.md','SESSION_STATUS.md','ROUND_DELTA.md','BUDGET_LEDGER.json','ACTIVE_JOB.json',
                            'freeze_ab.py','window_control.py','settle_ab.py','publish_ab.py','SUMMARY.md')]
    paths.extend(folder/n for n in ('RUN_BINDING.json','MINIMAL.diff','SOURCE_SHA256.json','FULL16_PAYLOAD.zip','ANALYSIS.json',
                   f'JOB_{job}_TRANSFER.tgz','received/COLLECTION_INDEX.json','received/djob_final.json',
                   'received/submission.command.json','received/FROZEN_REFERENCE/steps.jsonl','received/FROZEN_REFERENCE/PAIRING.json'))
    paths.extend(e/n for n in ('cleanup.json','pool_return_terminal.json','domain_map.json','hbm_capacity_before.json','update_budget_cleanup.json')
                 if (e/n).is_file())
    for arm in ('A','B'):
        paths.extend(e/arm/n for n in ('WINDOW.json','phase_receipt.json') if (e/arm/n).is_file())
        paths.extend(sorted((e/arm).glob('node*/steps.jsonl')))
        paths.extend(sorted((e/arm).glob('node*/result.json')))
    report.update(active_job=None,source=dict(package_sha256=b['package_sha256'],source_manifest_sha256=b['source_manifest_sha256'],
          diff_sha256=b['diff_sha256'],descriptor_sha256=b['descriptor_sha256'],allocator_sha256=b['allocator_sha256'],
          archived_reference_job=b['archived_reference_job'],archived_reference_bundle_sha256=b['archived_reference_bundle_sha256']),
          budget=ledger,prior_stability_preserved=True,GPU_4090='NOT_QUERIED_OR_CONNECTED',evidence_index=[identity(p) for p in paths])
    write(HERE/'STEP_BARRIER_AB_RESULT.json',report)
    print(HERE/'STEP_BARRIER_AB_RESULT.json')


if __name__=='__main__': publish()
