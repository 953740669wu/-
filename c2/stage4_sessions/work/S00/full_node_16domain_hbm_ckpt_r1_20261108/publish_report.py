"""Publish the terminal matrix and exact evidence references."""
from pathlib import Path
import sys

from summarize_batch import WORKLOADS, summarize
from verify_dependency import HERE, identity, read, save

LABELS={"32B32":"32 电极 B32/CKPT12","32B64":"32 电极 B64/CKPT12","16B64":"16 电极 B64/CKPT0"}


def publish(status):
    summarize(status)
    result_path=HERE/"FULL_NODE_16DOMAIN_RESULT.json"
    report=read(result_path)
    budget=report["budget"]
    planning=HERE/"B64_WALL_PLANNING.json"
    if planning.is_file():
        report["cn22035_B64_wall_planning"]=identity(planning)
    checks=[]
    anomalies=[]
    cells=[(host,cfg,report["coverage"][host][cfg]) for host in report["hosts"] for cfg in WORKLOADS]
    complete=[(host,cfg) for host,cfg,cell in cells if set(cell["rounds"])=={"1","2","3"}
                     and cell["functional_status"]=="PASS_16_OF_16"]
    stable=[(host,cfg) for host,cfg,cell in cells if cell["stability_status"]=="PASS"]
    across_hosts=[cfg for cfg in WORKLOADS if len(report["hosts"])==2
                  and all((host,cfg) in stable for host in report["hosts"])]
    if status=="COMPLETED_18_ROUNDS_STABILITY_PER_HOST":
        assert len(report["hosts"])==2 and len(complete)==6
    report["acceptance"]=dict(complete_host_config_pairs=complete,stable_host_config_pairs=stable,
        stable_workloads_across_both_hosts=across_hosts,
        hbm_rounds=sum(len(cell["rounds"]) for _,_,cell in cells))
    for info in report["job_results"].values():
        run=read(Path(info["path"]))
        anomalies.append(dict(job_id=run["job_id"],SIGBUS=run.get("SIGBUS_detected"),
                              OOM_explicit=run.get("OOM_explicit"),SIGKILL=run.get("SIGKILL_detected")))
    report["recorded_exit_diagnostics"]=anomalies
    lines=["# 16 域全节点验证", "",
      "两台主机串行执行 16 个独立 Encoder 副本。每域 38 核分配、36 核计算、2 核预留，DDR 393216 MB 同限，HBM 每域上限 3800 MiB。",
      "", "09 最终联合配置数值及安全合格。此前四域 CKPT12 波动 5.44% 超过 5%，原结论保留。",
      "", "| 实际主机 | 配置 | HBM 轮数 | 同步步时中位（秒） | 波动 | 16 域功能 | 稳定性 |",
      "| --- | --- | ---: | --- | ---: | --- | --- |"]
    for host in report["hosts"]:
        for cfg in WORKLOADS:
            cell=report["coverage"][host][cfg]
            checks.extend(cell["strict_jobs"])
            times=" / ".join(f"{x:.2f}" for x in cell.get("round_medians_seconds",[])) or "未测"
            spread=f"{cell['repeat_spread_pct']:.2f}%" if "repeat_spread_pct" in cell else "未验收"
            lines.append(f"| {host} | {LABELS[cfg]} | {len(cell['rounds'])}/3 | {times} | {spread} | {cell['functional_status']} | {cell['stability_status']} |")
    stable_label="、".join(f"{host} {LABELS[cfg]}" for host,cfg in stable) or "无"
    across_label="、".join(LABELS[cfg] for cfg in across_hosts) or "无"
    lines.extend(["",f"功能与三轮覆盖完成 {len(complete)}/6 组。达到 5% 稳定门的主机配置为 {stable_label}。两台主机均过稳定门的配置为 {across_label}。"])
    lines.extend(["", "## 速度、慢域及内存", ""])
    for host in report["hosts"]:
        for cfg in WORKLOADS:
            cell=report["coverage"][host][cfg]
            for c in cell["same_allocation_controls"]:
                a,b=c["ddr"],c["hbm"]
                lines.append(f"- {host} {LABELS[cfg]} 的同分配首对，DDR → HBM。同步步时 {a['median_synchronized_step_seconds']:.2f} → {b['median_synchronized_step_seconds']:.2f} 秒，同步吞吐 {a['synchronized_window_visits_per_second']:.2f} → {b['synchronized_window_visits_per_second']:.2f} 帧次/秒，各域步末合计采样最大 {a['max_sum_of_step_end_samples_MiB']:.1f} → {b['max_sum_of_step_end_samples_MiB']:.1f} MiB。")
            for key,r in sorted(cell["rounds"].items()):
                lines.append(f"- {host} {LABELS[cfg]} HBM 第 {key} 轮。最慢域 {r['slowest_domain']}，其纯训练总时长较各域中位高 {r['slowest_pure_total_vs_median_pct']:.2f}%。同步吞吐 {r['synchronized_window_visits_per_second']:.2f} 帧次/秒，单域 RSS 峰值加步末 HBM 估算最高 {r['max_domain_peak_estimate_MiB']:.1f} MiB，各域步末合计采样最大 {r['max_sum_of_step_end_samples_MiB']:.1f} MiB，HBM 实驻 {r['min_domain_hbm_end_MiB']}–{r['max_domain_hbm_end_MiB']} MiB/域。大块 DDR 回退计数 {r['ddr_large_fallback_allocations']}。")
    lines.extend(["","各域步末样本的时间可不同。单域 RSS 高水位加步末 HBM 是峰值估算。32 电极的 DDR/HBM 比较仅为每配置每主机一组同分配配对，三轮 HBM 只用于该侧稳定性。",""])
    if planning.is_file() and report["coverage"].get("cn22035",{}).get("32B64",{}).get("functional_status")=="NOT_RUN":
        plan=read(planning)
        lines.append(f"cn22035 的 32 电极 B64 未提交。根据 cn21762 的实际同机批量倍率和 cn22035 B32 实际阶段墙钟，严格与 25 步完整配对预估 {plan['projected_cn22035_32B64_perf_pair_seconds']+plan['projected_strict_seconds']:.0f} 秒，另需至少 120 秒收尾，超出单 job 7200 秒。此为计划估算。")
    lines.extend(["","## 原数值、故障与清理","",
                  f"通过作业的原严格比较共 {sum(c['metric_records'] for c in checks)} 项，记录最大绝对差 {max((c['max_abs'] for c in checks),default=0):g}，最大相对 L2 {max((c['max_relative_L2'] for c in checks),default=0):g}。原 exact 检查随冻结比较器执行。"])
    observed=[a for a in anomalies if a["SIGBUS"] is not None]
    lines.append(f"{len(observed)} 个实际获配作业的退出记录中，SIGBUS {sum(a['SIGBUS'] is True for a in observed)} 个，明确 OOM {sum(a['OOM_explicit'] is True for a in observed)} 个，SIGKILL {sum(a['SIGKILL'] is True for a in observed)} 个。")
    for a in budget["attempts"]:
        lines.append(f"- {a['job_id']}，{a.get('host') or '未获配'}，{a['workload']}，{a['state']}。排队 {a['queue_seconds']} 秒，分配 {a['allocated_seconds']} 秒，终态与清理已核。")
    lines.extend(["",f"累计 {len(budget['attempts'])}/10 次提交，{budget['queue_seconds']}/86400 秒排队，{budget['allocation_seconds']}/43200 秒计算分配，{budget['model_updates']}/16000 次更新，实际 {report['model_frame_visits']} 训练帧次。当前无活动作业。","",
       "配置与逐域值见 FULL_NODE_16DOMAIN_RESULT.json 及各 job ANALYSIS.json。原始计时、数值、容量、页池和进程清理随传输包及索引保存。"])
    (HERE/"SUMMARY.md").write_bytes(("\n".join(lines)+"\n").encode())
    report["summary"]=identity(HERE/"SUMMARY.md")
    save(result_path,report)
    paths=[result_path,HERE/"SUMMARY.md",HERE/"ACTUAL_COMMANDS.md",HERE/"DEPENDENCY_RECEIPT.json",HERE/"BUDGET_LEDGER.json"]
    for a in budget["attempts"]:
        run=HERE/a["version"]
        paths.extend(run/n for n in ("RUN_BINDING.json","MINIMAL.diff","ANALYSIS.json"))
        paths.extend(Path(a[key]["path"]) for key in ("artifact","native","cleanup_source"))
    save(HERE/"GIT_ARCHIVE_SUGGESTION.json",dict(scope="evidence suggestion only; no Git operations",
         paths=[identity(p) for p in paths if p.is_file()]))


if __name__=="__main__":
    publish(sys.argv[1])
