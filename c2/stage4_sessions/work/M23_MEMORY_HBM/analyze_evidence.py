"""Verify one returned M23 evidence ZIP and summarize the paired DDR run."""
import argparse
from collections import defaultdict
from datetime import datetime
import hashlib
import json
from pathlib import Path
import re
from statistics import median
import zipfile


MIB = 2**20


def read(path):
    return json.loads(path.read_bytes())


def verify_archive(archive, receipt, output):
    assert hashlib.sha256(archive.read_bytes()).hexdigest() == receipt["sha256"]
    assert archive.stat().st_size == receipt["bytes"]
    with zipfile.ZipFile(archive) as bundle:
        names = bundle.namelist()
        assert bundle.testzip() is None and len(names) == len(set(names))
        index = json.loads(bundle.read("COLLECTION.json"))
        assert set(names) == {"COLLECTION.json", *index}
        assert len(index) == receipt["files"]
        for name, item in index.items():
            assert not Path(name).is_absolute() and ".." not in Path(name).parts
            data = bundle.read(name)
            assert len(data) == item["bytes"]
            assert hashlib.sha256(data).hexdigest() == item["sha256"]
        if output.exists():
            for name in names:
                assert (output / name).read_bytes() == bundle.read(name)
        else:
            output.mkdir()
            bundle.extractall(output)


def numa_resident(path):
    by_node = defaultdict(int)
    huge = defaultdict(int)
    for line in path.read_text().splitlines():
        size = re.search(r"\bkernelpagesize_kB=(\d+)\b", line)
        nodes = re.findall(r"\bN(\d+)=(\d+)\b", line)
        if not nodes:
            continue
        assert size is not None
        target = huge if "huge" in line.split() else by_node
        for node, count in nodes:
            target[node] += int(count) * int(size[1]) * 1024
    return dict(ordinary_bytes=dict(by_node), hugetlb_bytes=dict(huge))


def summarize_rank(path):
    result = read(path / "result.json")
    rows = [json.loads(row) for row in (path / "steps.jsonl").read_text().splitlines()]
    assert result["status"] == "PASS_PERF25" and result["completed_updates"] == len(rows) == 25
    assert [r["step"] for r in rows] == list(range(1, 26))
    assert all(r["sampled"] == (r["step"] >= 6) and r["batch_size"] == 64 for r in rows)
    assert sorted(i for r in rows for i in r["frame_indices"]) == list(range(1600))
    assert len({json.dumps(fid, sort_keys=True) for r in rows for fid in r["frame_ids"]}) == 1600
    assert all(r["peak_reset"]["available"]
               and r["training_start"]["rss_bytes"] == r["training_start"]["peak_rss_bytes"]
               and r["rss_after"]["hugetlb_bytes"] == 0 for r in rows)
    observed = rows[5:]
    peak = [r["rss_after"]["peak_rss_bytes"] / MIB for r in observed]
    seconds = [r["step_seconds"] for r in observed]
    evidence = dict(
        rank=path.name,
        variant=result["variant"],
        host=result["host"],
        peak_rss_MiB=dict(min=min(peak), median=median(peak), max=max(peak)),
        step_seconds=dict(min=min(seconds), median=median(seconds), max=max(seconds)),
        hugetlb_bytes=0,
        numa_observe_start=numa_resident(path / "observe_start.numa_maps"),
        numa_observe_end=numa_resident(path / "observe_end.numa_maps"),
        kml_calls_per_step=sorted({r["kml_calls"] for r in rows}),
        samples=len(observed),
    )
    return evidence, rows


def phase_span(ranks):
    return [max(r[i]["end_ns"] for r in ranks) - min(r[i]["start_ns"] for r in ranks)
            for i in range(5, 25)]


def percentage(baseline, candidate):
    return 100 * (candidate / baseline - 1)


def analyze(root):
    job = read(root / "djob_final.json")["data"]["successData"][0]
    binding = read(root / "M23_RUN_BINDING.json")
    summary_path = root / "job_evidence/SUMMARY.json"
    summary = read(summary_path) if summary_path.is_file() else None
    stamp = lambda key: datetime.fromisoformat(job[key].replace("Z", "+00:00"))
    report = dict(job_id=str(job["jobId"]), state=job["state"], host=job.get("taskExecNodes"),
                  domain_count=binding["domain_count"], job_exit_code=job.get("jobExitCode"),
                  queue_seconds=(stamp("startTime") - stamp("createTime")).total_seconds() if job["startTime"] != "-" else None,
                  allocation_seconds=(stamp("endTime") - stamp("startTime")).total_seconds() if job["startTime"] != "-" else 0,
                  candidate_sha256=binding["candidate_sha256"], job_summary=summary)
    if not summary or summary["status"] != "PASS_DDR_AB":
        report["status"] = "NO_ACCEPTED_COMPARISON"
        return report

    assert job["state"] == "SUCCEEDED" and report["host"] not in binding["excluded_hosts"]
    assert read(root / "job_evidence/cleanup.json")["all_reaped"]
    strict = []
    strict_paths = sorted((root / "job_evidence/strict").glob("node*/result.json"))
    assert len(strict_paths) == binding["domain_count"]
    for path in strict_paths:
        result = read(path)
        metrics = result["metrics"]
        assert result["status"] == "PASS_STRICT_ENCODER5" and result["completed_updates"] == 5
        assert len(metrics) == 3895 and all(m["passed"] for m in metrics)
        strict.append(dict(rank=path.parent.name, updates=5, numeric_metrics=len(metrics),
                           tensor_max_abs=max(m["max_abs"] for m in metrics if ".state." not in m["name"]),
                           adamw_moment_max_abs=max(m["max_abs"] for m in metrics if ".state." in m["name"]),
                           applicable_max_rel_l2=max(m["l2_relative"] for m in metrics if m["reference_norm"] > 1e-8),
                           exact_adamw_step_checks=5 * 153,
                           strict_step1_storage=result["strict_step1_storage"]))
    report["strict"] = strict

    evidence, rows = {}, {}
    for variant in ("baseline", "candidate"):
        paths = sorted((root / ("job_evidence/perf_" + variant)).glob("node*/result.json"))
        assert [p.parent.name for p in paths] == [s["rank"] for s in strict]
        evidence[variant], rows[variant] = [], []
        for path in paths:
            rank, steps = summarize_rank(path.parent)
            assert rank["variant"] == variant and rank["host"] == report["host"]
            evidence[variant].append(rank)
            rows[variant].append(steps)
    keys = ("frame_indices", "frame_ids", "mask_sha256", "step")
    signatures = [[row[k] for k in keys] for row in rows["baseline"][0]]
    assert all([[row[k] for k in keys] for row in steps] == signatures
               for ranks in rows.values() for steps in ranks)
    baseline_span, candidate_span = [median(phase_span(rows[k])) / 1e9 for k in ("baseline", "candidate")]
    report["status"] = "PASS_DDR_AB"
    report["performance"] = dict(
        ranks=evidence,
        median_synchronized_step_span_seconds=dict(baseline=baseline_span, candidate=candidate_span),
        step_span_change_percent=percentage(baseline_span, candidate_span),
        per_rank_change=[dict(rank=b["rank"],
                              median_rss_change_percent=percentage(b["peak_rss_MiB"]["median"], c["peak_rss_MiB"]["median"]),
                              max_rss_change_percent=percentage(b["peak_rss_MiB"]["max"], c["peak_rss_MiB"]["max"]),
                              median_step_time_change_percent=percentage(b["step_seconds"]["median"], c["step_seconds"]["median"]))
                         for b, c in zip(evidence["baseline"], evidence["candidate"])],
    )
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run", type=Path)
    args = parser.parse_args()
    run = args.run.resolve()
    receipt = read(run / "bundle_receipt.json")
    received = run / "received"
    verify_archive(run / receipt["file"], receipt, received)
    report = analyze(received)
    (run / "REVIEW.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k not in {"strict", "performance"}}, indent=2))
