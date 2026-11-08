"""Verify a returned HBM job and compare matched CKPT0 DDR/HBM observations."""
import argparse
from datetime import datetime
import json
from pathlib import Path
import re
from statistics import median
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from analyze_evidence import numa_resident, verify_archive


MIB = 2**20


def load(path):
    return json.loads(path.read_bytes())


def step_records(path):
    return [json.loads(line) for line in path.read_bytes().splitlines()]


def distribution(values):
    return dict(min=min(values), median=median(values), max=max(values))


def percent_change(baseline, candidate):
    return 100 * (candidate / baseline - 1)


def performance(evidence, roles, domains):
    ranks, rows = {}, {}
    for role in roles:
        phase = evidence / f"perf_{role}"
        ranks[role], rows[role] = [], []
        for domain in domains:
            path = phase / domain
            result = load(path / "result.json")
            steps = step_records(path / "steps.jsonl")
            assert result["status"] == "PASS_PERF25" and result["completed_updates"] == len(steps) == 25
            assert [row["step"] for row in steps] == list(range(1, 26))
            assert all(row["sampled"] == (row["step"] >= 6) and row["batch_size"] == 64
                       and row["role"] == role and row["kml_calls"] == 149 for row in steps)
            assert sorted(i for row in steps for i in row["frame_indices"]) == list(range(1600))
            assert len({json.dumps(f, sort_keys=True) for row in steps for f in row["frame_ids"]}) == 1600
            assert all(row["peak_reset"]["available"] and
                       row["training_start"]["rss_bytes"] == row["training_start"]["peak_rss_bytes"]
                       for row in steps)
            samples = steps[5:]
            huge = [row["rss_after"]["hugetlb_bytes"] / MIB for row in samples]
            allocator = result["hbm_allocator"]
            start = numa_resident(path / "observe_start.numa_maps")
            end = numa_resident(path / "observe_end.numa_maps")
            arena = None
            if role == "candidate":
                node = str(allocator["node"])
                assert all(0 < n <= allocator["cap_MiB"] for n in huge)
                for snapshot in (start, end):
                    assert set(snapshot["hugetlb_bytes"]) == {node}
                    assert 0 < snapshot["hugetlb_bytes"][node] <= allocator["cap_MiB"] * MIB
                    assert node not in snapshot["ordinary_bytes"]
                log = (phase / f"{domain}.log").read_text(errors="replace")
                match = re.search(r"hbm allocs (\d+) \(([\d.]+) GB, (\d+) reused\), ddr large allocs "
                                  r"(\d+) \(([\d.]+) GB\), arena high-water ([\d.]+) GB", log)
                assert match is not None
                arena = dict(allocations=int(match[1]), cumulative_hbm_GB=float(match[2]),
                             reused=int(match[3]), ddr_large_allocations=int(match[4]),
                             cumulative_ddr_large_GB=float(match[5]), bump_high_water_GB=float(match[6]))
            else:
                assert max(huge) == 0 and not allocator and not start["hugetlb_bytes"] and not end["hugetlb_bytes"]
            rank = dict(domain=domain, role=role, samples=20, allocator=allocator, arena=arena,
                        seconds=distribution([r["step_seconds"] for r in samples]),
                        ordinary_peak_rss_MiB=distribution([r["rss_after"]["peak_rss_MiB"] for r in samples]),
                        hbm_resident_at_step_end_MiB=distribution(huge),
                        simultaneous_step_end_rss_plus_hugetlb_MiB=distribution([
                            (r["rss_after"]["rss_bytes"] + r["rss_after"]["hugetlb_bytes"]) / MIB
                            for r in samples]),
                        numa_observe_start=start, numa_observe_end=end)
            ranks[role].append(rank)
            rows[role].append(steps)
    keys = ("frame_ids", "frame_indices", "mask_sha256", "step")
    reference = [[row[k] for k in keys] for row in rows["baseline"][0]]
    assert all([[row[k] for k in keys] for row in steps] == reference
               for ranks_rows in rows.values() for steps in ranks_rows)
    spans = {role: distribution([
        (max(r[i]["end_ns"] for r in rows[role]) - min(r[i]["start_ns"] for r in rows[role])) / 1e9
        for i in range(5, 25)]) for role in roles}
    return dict(ranks=ranks, step_span_seconds=spans,
                step_span_change_percent=percent_change(spans["baseline"]["median"], spans["candidate"]["median"]),
                throughput_change_percent=percent_change(spans["candidate"]["median"], spans["baseline"]["median"]))


def analyze(root):
    final = load(root / "djob_final.json")["data"]["successData"][0]
    binding = load(root / "M23_RUN_BINDING.json")
    evidence = root / "job_evidence"
    summary_path = evidence / "SUMMARY.json"
    cleanup_path = evidence / "cleanup.json"
    summary = load(summary_path) if summary_path.is_file() else None
    c_gate = root / "s03/linux_evidence/SUMMARY.json"
    receipt_paths = sorted(evidence.glob("real_hbm_node*/RECEIPT.json"))
    def ts(key):
        return datetime.fromisoformat(final[key].replace("Z", "+00:00"))
    started = final["startTime"] != "-"
    report = dict(job_id=str(final["jobId"]), scheduler_state=final["state"], host=final.get("taskExecNodes"),
                  domain_count=binding["domain_count"], exit_code=final.get("jobExitCode"),
                  queue_seconds=(ts("startTime" if started else "endTime") - ts("createTime")).total_seconds(),
                  allocation_seconds=(ts("endTime") - ts("startTime")).total_seconds() if started else 0,
                  cleanup=load(cleanup_path) if cleanup_path.is_file() else None,
                  native_pid_cleared=all(row.get("pids") == "-" for g in final.get("resGroups", [])
                                         for row in g.get("nodeResUsages", [])),
                  candidate_sha256=binding["candidate_sha256"],
                  c_gate=load(c_gate) if c_gate.is_file() else None,
                  hbm_safety=[load(p) for p in receipt_paths], summary=summary,
                  logged_update_rows=sum(len(step_records(p)) for p in evidence.glob("*/*/steps.jsonl")))
    if not summary or summary["status"] != "PASS_HBM_AB":
        return report
    assert final["state"] == "SUCCEEDED" and report["cleanup"]["all_reaped"] and report["native_pid_cleared"]
    assert report["host"] not in binding["excluded_hosts"] and summary["hbm_pool_restored"]
    assert len(report["hbm_safety"]) == binding["domain_count"]
    domains = sorted(p.name for p in (evidence / "strict_baseline").glob("node*") if p.is_dir())
    assert len(domains) == binding["domain_count"]
    roles = ("baseline", "candidate")
    strict = {}
    for domain in domains:
        left, right = [load(evidence / f"strict_{role}" / domain / "result.json") for role in roles]
        assert left["status"] == "PASS_STRICT_REFERENCE5" and right["status"] == "PASS_STRICT_ENCODER5"
        assert left["completed_updates"] == right["completed_updates"] == 5
        assert len(left["reference_snapshots"]) == 5 and len(left["metrics"]) == 15
        metrics = left["metrics"] + right["metrics"]
        assert len(metrics) == 3895 and all(m["passed"] for m in metrics)
        strict[domain] = dict(metric_count=len(metrics), exact_adamw_step_count=765,
                              tensor_max_abs=max(m["max_abs"] for m in metrics if ".state." not in m["name"]),
                              state_max_abs=max(m["max_abs"] for m in metrics if ".state." in m["name"]),
                              max_applicable_rel_l2=max(m["l2_relative"] for m in metrics if m["reference_norm"] > 1e-8))
    report.update(strict=strict, performance=performance(evidence, roles, domains))
    assert report["logged_update_rows"] == binding["domain_count"] * 60
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run", type=Path)
    args = parser.parse_args()
    run = args.run.resolve()
    receipt = load(run / "bundle_receipt.json")
    received = run / "received"
    verify_archive(run / receipt["file"], receipt, received)
    report = analyze(received)
    (run / "REVIEW.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k not in {"c_gate", "hbm_safety", "cleanup"}}, indent=2))
