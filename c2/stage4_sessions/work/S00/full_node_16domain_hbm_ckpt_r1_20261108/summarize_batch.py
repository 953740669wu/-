"""Aggregate independently returned runs by workload and actual physical host."""
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
import sys

from verify_dependency import HERE, identity, read, save

WORKLOADS=("32B32","32B64","16B64")


def row_summary(phase):
    d=phase["domains"]
    measurements=[r["measurements"] for r in d.values()]
    return {k:phase[k] for k in (
        "median_synchronized_step_seconds","synchronized_window_seconds","synchronized_window_visits_per_second",
        "sum_independent_rates","slowest_domain","slowest_rate_reference_x16","slowest_pure_total_vs_median_pct",
        "max_sum_of_step_end_samples_MiB","sum_per_domain_peak_estimates_MiB")} | dict(
        domains=len(d),max_rss_peak_MiB=max(v["ordinary_rss_peak_MiB"] for v in measurements),
        max_domain_peak_estimate_MiB=max(v["rss_peak_plus_step_end_hbm_estimate_MiB"] for v in measurements),
        min_domain_hbm_end_MiB=min(v.get("observe_end_hbm_MiB",0) for v in measurements),
        max_domain_hbm_end_MiB=max(v.get("observe_end_hbm_MiB",0) for v in measurements),
        ddr_large_fallback_allocations=sum(r.get("allocator_stats",{}).get("ddr_large_fallback_allocations",0) for r in d.values()))


def summarize(terminal=None):
    ledger=read(HERE/"BUDGET_LEDGER.json")
    active=read(HERE/"ACTIVE_JOB.json")
    dependency=read(HERE/"DEPENDENCY_RECEIPT.json")
    all_hosts=sorted({a["host"] for a in ledger["attempts"] if a.get("host")})
    matrix={h:{c:dict(rounds={},same_allocation_controls=[],failures=[],strict_jobs=[]) for c in WORKLOADS} for h in all_hosts}
    job_results={}
    frame_visits=0
    for a in ledger["attempts"]:
        run=HERE/a["version"]
        bind=read(run/"RUN_BINDING.json")
        analysis=run/"ANALYSIS.json"
        if not analysis.is_file():
            continue
        value=read(analysis)
        job_results[a["job_id"]]=identity(analysis)
        frame_visits+=bind["batch_size"]*a["confirmed_updates"]
        if not a["host"]:
            continue
        cell=matrix[a["host"]][bind["workload"]]
        phases=value["phases"]
        if "strict_candidate" in phases:
            checks=[d["strict_gate"] for d in phases["strict_candidate"]["domains"].values()]
            cell["strict_jobs"].append(dict(job_id=a["job_id"],domains=len(checks),
                metric_records=sum(x["rows"] for x in checks),max_abs=max(x["max_abs"] for x in checks),
                max_relative_L2=max(x["max_rel_L2"] for x in checks)))
        if value["status"]!="PASS_FULL_NODE_COMPLETED_PHASES":
            cell["failures"].append(dict(job_id=a["job_id"],status=value["status"],raw=identity(analysis),
                completed_phases=sorted(phases)))
            continue
        for n in value["application"]["completed_hbm_rounds"]:
            key=str(n)
            assert key not in cell["rounds"]
            r=row_summary(phases[f"perf_candidate_r{n}"])
            cell["rounds"][key]=dict(job_id=a["job_id"],package_sha256=bind["package_sha256"],**r)
        if "perf_baseline" in phases and "perf_candidate_r1" in phases:
            ddr=row_summary(phases["perf_baseline"])
            hbm=row_summary(phases["perf_candidate_r1"])
            cell["same_allocation_controls"].append(dict(job_id=a["job_id"],ddr=ddr,hbm=hbm,
                synchronized_step_time_reduction_pct=100*(1-hbm["median_synchronized_step_seconds"]/ddr["median_synchronized_step_seconds"]),
                synchronized_window_time_reduction_pct=100*(1-hbm["synchronized_window_seconds"]/ddr["synchronized_window_seconds"])))
    for host,configs in matrix.items():
        for config,c in configs.items():
            values=list(c["rounds"].values())
            medians=[v["median_synchronized_step_seconds"] for v in values]
            same_source=len({v["package_sha256"] for v in values})==1
            controls_ok=config=="16B64" or bool(c["same_allocation_controls"])
            if not medians:
                state="STRICT_16_OF_16_ONLY" if c["strict_jobs"] else "FAIL" if c["failures"] else "NOT_RUN"
                c.update(functional_status=state,stability_status="NOT_RUN")
                continue
            c.update(functional_status="PASS_16_OF_16" if controls_ok else "PARTIAL_DDR_CONTROL_MISSING",
                     round_medians_seconds=medians)
            if len(medians)==3 and same_source and controls_ok:
                spread=100*(max(medians)-min(medians))/mean(medians)
                c.update(repeat_spread_pct=spread,stability_status="PASS" if spread<=5 else "FAIL_SPREAD_GT_5_PERCENT")
            else:
                c["stability_status"]="INSUFFICIENT_MATCHED_ROUNDS"
    status=terminal or "IN_PROGRESS"
    result=dict(status=status,generated_utc=datetime.now(timezone.utc).isoformat(),
        active_job=active.get("active_job"),hosts=all_hosts,coverage=matrix,job_results=job_results,
        dependency=identity(HERE/"DEPENDENCY_RECEIPT.json"),dependency_09_stability=dependency["ckpt12_stability"],
        model_frame_visits=frame_visits,budget=ledger,
        measurement_limits=["Per-domain ordinary RSS high-water plus step-end HBM is an estimate, not a synchronized joint peak.",
                            "Sum of step-end samples can have different timestamp per domain within a step.",
                            "One DDR pairing per configuration is a point comparison, not three-pair speed acceptance."])
    if terminal:
        assert not active.get("active_job") and all(a["terminal"] and a["cleanup"] for a in ledger["attempts"])
    path=HERE/("FULL_NODE_16DOMAIN_RESULT.json" if terminal else "BATCH_PROGRESS.json")
    save(path,result)
    print(path,[(h,k,len(c["rounds"]),c["stability_status"]) for h,x in matrix.items() for k,c in x.items()])


if __name__=="__main__":
    summarize(sys.argv[1] if len(sys.argv)>1 else None)
