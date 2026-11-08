"""Read the returned original-model run; no framework or model execution."""
from collections import Counter
import json
import math
from pathlib import Path
import re
from statistics import mean, median


def read(path):
    return json.loads(path.read_bytes())


def jsonl(path):
    return [json.loads(line) for line in path.read_bytes().splitlines()]


def cpu_list(text):
    result = []
    for span in text.split(","):
        first, _, last = span.partition("-")
        result.extend(range(int(first), int(last or first) + 1))
    return result


def affinity(phase, topo, node, receipt):
    parent = read(phase / "parent_before_spawn.json")
    observer = read(phase / "parent_after_spawn.json")
    native = dict(line.split("=",1) for line in (phase / f"node{node}.before_numactl.txt").read_text().splitlines())
    before = read(phase / f"node{node}/before_torch_affinity.json")
    allowed = topo["context"]["allowed"]
    assert parent["allowed"] == cpu_list(parent["allowed_list"]) == cpu_list(native["inherited"]) == allowed
    assert cpu_list(native["allocated_domain"]) == before["after_numactl"] == receipt["allocated"]
    assert before["selected"] == receipt["selected"] and before["reserved"] == receipt["reserved"]
    assert native["job"] == before["job_id"] == parent["job_id"] == topo["context"]["job_id"]
    assert int(native["pid"]) == before["pid"] == observer["children"][node]
    assert observer["pid"] == parent["pid"] and observer["allowed"] == [next(iter(topo["contracts"].values()))["reserved"][0]]
    assert before["guard_before_framework"]["calling_affinity"] == receipt["selected"]
    return dict(parent_cpu_count=len(parent["allowed"]), inherited_cpu_count=len(cpu_list(native["inherited"])),
                after_numactl=before["after_numactl"], compute_before_torch=before["selected"],
                reserved=before["reserved"], worker_pid=before["pid"], observer=observer["allowed"])


def locality(path, node):
    kinds = {"anonymous": Counter(), "file_backed": Counter(), "other": Counter()}
    policies = Counter()
    for line in path.read_text().splitlines():
        fields = line.split()
        if len(fields) < 2:
            continue
        kind = ("file_backed" if any(x.startswith("file=") for x in fields) else
                "anonymous" if any(x.startswith("anon=") for x in fields) else "other")
        size = next((int(x.partition("=")[2]) for x in fields if x.startswith("kernelpagesize_kB=")), None)
        placements = [re.fullmatch(r"N([0-9]+)=([0-9]+)", x) for x in fields]
        for placement in filter(None, placements):
            assert size is not None
            resident = int(placement[2]) * size
            kinds[kind][placement[1]] += resident
            policies[fields[1]] += resident
    return {kind: dict(local_MiB=round(nodes[node]/1024,3),
                       remote_MiB=round(sum(value for n,value in nodes.items() if n != node)/1024,3),
                       per_node_kB=dict(nodes)) for kind,nodes in kinds.items()} | {"policies_kB":dict(policies)}


def load_window(samples, selected, node, left, right, clock_ticks):
    inside = [row for row in samples if left <= row["at_ns"] <= right and node in row["worker_ticks"]]
    if len(inside) < 2:
        return dict(status="NOT_OBTAINED")
    a,b = inside[0],inside[-1]
    busy = total = 0
    for cpu in selected:
        x,y = (row["per_cpu"][f"cpu{cpu}"] for row in (a,b))
        diff = [j-i for i,j in zip(x[:8],y[:8])]
        assert all(n >= 0 for n in diff)
        total += sum(diff)
        busy += sum(diff)-diff[3]-diff[4]
    u,v = (row["worker_ticks"][node] for row in (a,b))
    assert u["pid"] == v["pid"] and u["start_ticks"] == v["start_ticks"]
    observed_ticks = v["ticks"] - u["ticks"]
    return dict(status="OBSERVED", samples=len(inside), wall_seconds=(b["at_ns"]-a["at_ns"])/1e9,
                selected_cpu_busy_pct=100*busy/total, worker_cpu_ticks=observed_ticks, selected_cpu_busy_ticks=busy,
                residual_nonworker_busy_ticks=busy-observed_ticks, residual_nonworker_busy_pct_of_selected=100*(busy-observed_ticks)/total,
                worker_cpu_seconds=observed_ticks/clock_ticks,
                caveat="Residual includes system/interrupt activity and asynchronous tick sampling.")


def compare_rows(value):
    metrics = value["metrics"]
    assert metrics and all(row["passed"] is True and all(math.isfinite(row[k]) for k in
           ("max_abs","l2_relative","reference_norm")) for row in metrics)
    return dict(rows=len(metrics), maximum_abs=max(m["max_abs"] for m in metrics),
                maximum_relative_L2=max(m["l2_relative"] for m in metrics))


def analyze(root, clock_ticks, perf_name="perf"):
    evidence = root/"job_evidence"
    topo = read(evidence/"domain_map.json")
    strict, perf = (evidence/name for name in ("strict",perf_name))
    domains = topo["contracts"]
    assert len(domains) == 4
    series, results = {}, {}
    for node, receipt in domains.items():
        strict_data = read(strict/f"node{node}/result.json")
        perf_data = read(perf/f"node{node}/result.json")
        assert strict_data["status"] == "PASS_STRICT_ENCODER5" and strict_data["completed_updates"] == 5
        expected_status = "PASS_CANDIDATE25" if perf_name == "candidate" else "PASS_BASELINE25"
        assert perf_data["status"] == expected_status and perf_data["completed_updates"] == 25
        assert all(x["job_id"] == topo["context"]["job_id"] and x["host"] == topo["context"]["host"]
                   and not x["cpu36"]["errors"] for x in (strict_data,perf_data))
        assert perf_data["recovery"]["status"] == "PASS_NO_EXTRA_UPDATE" and perf_data["recovery"]["extra_updates"] == 0
        strict_steps = jsonl(strict/f"node{node}/steps.jsonl")
        perf_steps = jsonl(perf/f"node{node}/steps.jsonl")
        assert len(strict_steps) == 10 and [r["step"] for r in perf_steps] == list(range(1,26))
        assert all(row["native_sgemm_calls"] == 149 for row in strict_steps+perf_steps)
        samples = series[node] = [row for row in perf_steps if row["sampled"]]
        assert [row["step"] for row in samples] == list(range(6,26))
        step_seconds = [row["step_seconds"] for row in samples]
        hwm = max(row[k]["peak_rss_MiB"] for row in samples for k in ("rss_before","rss_after"))
        rates = [64/t for t in step_seconds]
        results[node] = dict(strict=compare_rows(strict_data), perf_first5=compare_rows(perf_data),
             affinity={phase.name:affinity(phase,topo,node,receipt) for phase in (strict,perf)},
             affinity_snapshots={stage:len(x["cpu36"]["checkpoints"]) for stage,x in (("strict",strict_data),("perf",perf_data))},
             effective_intraop={stage:sorted({c["torch_intraop"] for c in x["cpu36"]["checkpoints"] if "torch_intraop" in c})
                                for stage,x in (("strict",strict_data),("perf",perf_data))},
             sampled_seconds=dict(total=sum(step_seconds),median=median(step_seconds),min=min(step_seconds),max=max(step_seconds)),
             sampled_step_spread_pct=(max(step_seconds)-min(step_seconds))/mean(step_seconds)*100,
             throughput_frames_s=1280/sum(step_seconds), sample_hwm_MiB=hwm,
             load_seconds=(perf_data["load_ns"][1]-perf_data["load_ns"][0])/1e9,
             placement={label:locality(perf/f"node{node}/{label}.numa_maps",node)
                        for label in ("initialized","observe_start","observe_end")},
             final_model_sha256=perf_data["final_model_sha256"])
    ordered = list(series.values())
    sync = []
    for rows in zip(*ordered):
        first = rows[0]
        assert all(all(row[k] == first[k] for k in ("step","frame_ids","frame_indices","mask_sha256","release_ns")) for row in rows)
        starts, ends = ([r[k] for r in rows] for k in ("start_ns","end_ns"))
        sync.append(dict(step=first["step"],start_skew_ms=(max(starts)-min(starts))/1e6,
                         end_spread_ms=(max(ends)-min(ends))/1e6))
    left = max(rows[0]["start_ns"] for rows in ordered)
    right = min(rows[-1]["end_ns"] for rows in ordered)
    samples = jsonl(perf/"cpu_samples.jsonl")
    for node, receipt in domains.items():
        results[node]["cpu_load"] = load_window(samples,receipt["selected"],node,left,right,clock_ticks)
    rates = {n:r["throughput_frames_s"] for n,r in results.items()}
    slow = min(rates,key=rates.get)
    makespan = (max(rows[-1]["end_ns"] for rows in ordered)-min(rows[0]["start_ns"] for rows in ordered))/1e9
    return dict(domains=results,strict_domains=4,perf_domains=4,slowest_domain=slow,
         sum_domain_frames_s=sum(rates.values()),four_times_slowest_frames_s=4*rates[slow],
         measured_common_window_frames_s=5120/makespan,common_window_seconds=makespan,
         slowest_below_median_pct=(1-rates[slow]/median(rates.values()))*100,
         across_domain_rate_spread_pct=(max(rates.values())-min(rates.values()))/mean(rates.values())*100,
         synchronized_start=dict(median_skew_ms=median(r["start_skew_ms"] for r in sync),
                                 max_skew_ms=max(r["start_skew_ms"] for r in sync),per_step=sync),
         final_model_sha_matches=len({r["final_model_sha256"] for r in results.values()})==1)
