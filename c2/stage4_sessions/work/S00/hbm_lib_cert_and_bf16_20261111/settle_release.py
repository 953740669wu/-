"""Verify returned raw evidence before opening the conditional stage."""
from collections import Counter
import math
from pathlib import Path
from statistics import median
import sys

from freeze_release import HERE

sys.path.insert(0, str(HERE.parent / "full_node_16domain_hbm_ckpt_r1_20261108"))
from analyze_run import allocator_stats, native_time, resident_hbm, rows, unpack
from verify_dependency import COMPARE_SHA, KML_SHA, LIBRARY_SHA, check_metrics, identity, read, save, sha


def phase(evidence, label, binding, topo, job):
    stage = evidence / label
    published = read(stage / "phase_receipt.json")
    steps = 5 if label.startswith("strict_") else 25
    side = "baseline" if "baseline" in label else "candidate"
    selection = binding["hbm_selections"][side]
    assert read(evidence / f"pool_return_{label}.json")["passed"]
    assert published["job_id"] == job
    result, sequences = {}, {}
    for n, cpus in topo["contracts"].items():
        name = f"node{n}"
        home = stage / name
        worker = read(home / "result.json")
        assert worker["status"] == published["status"] and worker["completed_updates"] == steps
        assert worker["checkpoint_layers"] == 12 and worker["job_id"] == job
        assert worker["variant"] == side and worker["host"] == topo["context"]["host"]
        receipt = read(home / "before_torch_affinity.json")
        assert receipt["after_numactl"] == cpus["allocated"] and receipt["selected"] == cpus["selected"]
        assert receipt["reserved"] == cpus["reserved"] and receipt["job_id"] == job
        guard = worker["cpu36"]
        assert not guard["errors"] and guard["checkpoints"][-1]["name"] == "publish"
        assert all(c["torch_intraop"] == 36 for c in guard["checkpoints"][1:])
        log = sequences[n] = rows(home / "steps.jsonl")
        assert [r["step"] for r in log] == list(range(1, steps + 1))
        assert all(r["batch_size"] == 32 and r["native_sgemm_calls"] == r["kml_calls"] > 0 for r in log)
        a = worker["hbm_allocator"]
        assert a["sha256"] == LIBRARY_SHA and a["cap_MiB"] == 3800 and a["node"] == topo["hbm_pairs"][n]
        assert a["requested"] == selection["HBM_LIB"]
        copy_label = side if binding["mode"] == "hbm_lib_cert" else "candidate"
        origin = read(evidence / f"allocator_identity_{copy_label}.json")
        assert origin["source"] == selection["allocator_origin"] and origin["final_preload"] == a["path"]
        assert origin["requested"] == a["requested"] and origin["sha256"] == LIBRARY_SHA
        actual = evidence.parent / Path(a["path"].removeprefix(binding["remote_root"] + "/"))
        assert identity(actual)["sha256"] == LIBRARY_SHA
        maps = []
        for marker in ("after_framework", "publish"):
            f = home / f"{marker}.maps"
            assert {line.split()[-1] for line in f.read_text().splitlines() if "libhbm_alloc" in line} == {a["path"]}
            maps.append(identity(f))
        info = read(stage / f"{name}.hbm_residency.json")
        resident = resident_hbm(evidence / info["source"], a["node"])
        assert info["page_kB"] == 2048 and resident == info["resident_MiB"] and 0 < resident <= a["cap_MiB"]
        measured = log if steps == 5 else log[5:]
        rss = [r["rss_after"] for r in measured]
        assert all(0 < r["hugetlb_bytes"] <= 3800*2**20 for r in rss)
        d = result[n] = dict(updates=steps, worker=identity(home / "result.json"), steps=identity(home / "steps.jsonl"),
            pairing_sha256=worker["pairing_sha256"], allocator=origin, maps=maps,
            allocator_stats=allocator_stats(stage / f"{name}.log"), hbm_resident_MiB=resident,
            ordinary_rss_peak_MiB=max(r["peak_rss_MiB"] for r in rss),
            rss_peak_plus_step_end_hbm_estimate_MiB=max(r["peak_rss_MiB"]+r["hugetlb_bytes"]/2**20 for r in rss),
            step_seconds=[r["step_seconds"] for r in measured])
        if steps == 5 and side == "candidate":
            d["strict"] = check_metrics(worker["metrics"])
            assert d["strict"]["rows"] == 3880 and len({r["name"] for r in worker["metrics"]}) == 3880
            parameters = Counter(int(r["name"].split(".",1)[0]) for r in worker["metrics"] if ".param." in r["name"])
            assert parameters == {i:153 for i in range(1,6)}
            d["strict"].update(exact_optimizer_step_items=sum(parameters.values()), exact_items_passed=True,
                  exact_evidence="original pinned strict comparator checks one exact AdamW step tensor per parameter per update")
        if binding["mode"] == "bf16_bq16" and side == "candidate":
            d["dispatch"] = worker["attention"]
            assert d["dispatch"]["bf16"] == 1 and d["dispatch"]["bq"] == 16
            assert d["dispatch"]["locking_namespace"]["symbol"] == "cblas_sbgemm"
            assert all(r["fused_attention"]["backward"] == 12 and r["fused_attention"]["forward"] >= 12 and
                       r["fused_attention"]["forward_tiles"] > 0 and r["fused_attention"]["backward_tiles"] > 0 for r in log)
        else:
            assert all(r["fused_attention"] is None for r in log) and "attention" not in worker
    details = dict(domain_count=len(result), domains=result)
    if steps == 25:
        width = (max(v[-1]["end_ns"] for v in sequences.values()) - min(v[5]["start_ns"] for v in sequences.values()))/1e9
        details.update(window_seconds=width, visits_per_second=32*20*len(result)/width,
            slowest_domain=max(result,key=lambda n:sum(result[n]["step_seconds"])),
            over_4GiB_estimate_domains=[n for n,d in result.items() if d["rss_peak_plus_step_end_hbm_estimate_MiB"] > 4096])
    return details, sequences


def same_input(a, b):
    assert a.keys() == b.keys()
    for n in a:
        assert len(a[n]) == len(b[n])
        for x, y in zip(a[n], b[n]):
            assert all(x[k] == y[k] for k in ("frame_indices", "frame_ids", "mask_sha256", "native_shapes"))


def settle(version, job, digest):
    folder = HERE / version
    raw, bundle = unpack(folder, job, digest)
    e = raw / "job_evidence"
    b = read(folder / "RUN_BINDING.json")
    pin = identity(folder / "RUN_BINDING.json")["sha256"]
    assert identity(raw / "RUN_BINDING.json")["sha256"] == pin
    assert identity(raw / "FULL16_PAYLOAD.zip")["sha256"] == b["package_sha256"]
    assert identity(raw / "SOURCE_SHA256.json")["sha256"] == b["source_manifest_sha256"]
    sources = read(raw / "SOURCE_SHA256.json")
    assert sources["payload/tests/check_equivalence.py"] == COMPARE_SHA and sources["payload/baseline/kml_ops.py"] == KML_SHA
    for name, h in (sources | b["frozen_sidecars"]).items():
        assert identity(raw / name)["sha256"] == h, name
    assert read(raw / "FIXED_INPUTS_BEFORE.json") == read(raw / "FIXED_INPUTS_AFTER.json")
    assert read(raw / "post_job_queue.json")["data"] == []
    n, = read(raw / "djob_final.json")["data"]["successData"]
    g, = n["resGroups"]
    assert n["jobId"] == job and n["user"] == "wujunyi" and n["queue"] == "q_hpcai" and n["execPath"] == b["remote_root"]
    assert n["state"] == bundle["state"] and n["exclusive"] is True
    assert n["jobWallClockLimit"] == b["wall_seconds"] and g["resReq"]["cpu"] == 38*b["domain_count"]
    assert g["resReq"]["mem"] == g["resLimit"]["mem"] == 24576*b["domain_count"] and g["resReq"]["gpu"]["amount"] == 0
    cert = b["mode"] == "hbm_lib_cert"
    report = dict(job_id=job, status="FAIL_STOP", state=n["state"], native_exit=n["jobExitCode"], mode=b["mode"],
          run_binding=identity(folder/"RUN_BINDING.json"), sources=identity(folder/"SOURCE_SHA256.json"),
          diff=identity(folder/"MINIMAL.diff"), input_descriptor=identity(folder/"ENGINEERING_DESCRIPTOR.json"),
          pairing=identity(folder/"PRIOR_PAIRING.json"), archive=identity(folder/f"JOB_{job}_TRANSFER.tgz"),
          numerical=b["numerical"], phases={}, active_job=None)
    timings = native_time(n["createTime"]), native_time(n["endTime"])
    updates = allocation = 0
    if n["startTime"] == "-":
        assert not g["nodeResUsages"] and bundle["pids"] == []
        queue = math.ceil((timings[1]-timings[0]).total_seconds())
    else:
        node, = g["nodeResUsages"]
        assert node["execNode"] in b["eligible_hosts"] and bundle["pids"] == [node["pids"]] == ["-"]
        assert g["resAlloc"]["cpu"] == g["resReq"]["cpu"] and g["resAlloc"]["mem"] == g["resReq"]["mem"]
        start = native_time(n["startTime"])
        queue = math.ceil((start-timings[0]).total_seconds())
        allocation = max(node["wallclockDuration"], math.ceil((timings[1]-start).total_seconds()))
        clean = read(e / "cleanup.json")
        assert clean["all_reaped"] and not clean["remaining_live"] and not clean["remaining_processes"]
        app = report["application"] = read(e / "SUMMARY.json")
        assert app["job_id"] == job
        report.update(host=node["execNode"], cleanup=identity(e / "cleanup.json"), resources=b["allocation_contract"])
        if (e / "domain_map.json").is_file():
            topo = read(e / "domain_map.json")
            assert len(topo["contracts"]) == b["domain_count"] and len(topo["context"]["allowed"]) == 38*b["domain_count"]
            assert all(len(c["allocated"]) == 38 and len(c["selected"]) == 36 and len(c["reserved"]) == 2
                       for c in topo["contracts"].values())
            report["resources"]["HBM_cpu_domain_mapping"] = topo["hbm_pairs"]
            seqs = {}
            for receipt in sorted(e.glob("*/phase_receipt.json")):
                label = receipt.parent.name
                report["phases"][label], seqs[label] = phase(e,label,b,topo,job)
            if "strict_candidate" in seqs:
                same_input(seqs["strict_baseline"],seqs["strict_candidate"])
        neg = {p.stem.removeprefix("HBM_LIB_rejection_"):read(p) for p in sorted(e.glob("HBM_LIB_rejection_*.json"))}
        if cert:
            report["negative_cases"] = neg
        elif (e / "ATTN_BUILD.json").is_file():
            report["build"] = read(e / "ATTN_BUILD.json")
            assert report["build"]["source_sha256"] == b["kernel_source_sha256"]
            assert identity(e / "libbf16_attn.so")["sha256"] == report["build"]["library"]["sha256"]
        if (e / "pool_return_terminal.json").is_file():
            report["terminal_pool"] = read(e / "pool_return_terminal.json")
        for p in sorted(e.glob("*/node*/EXPOSURE_LEDGER.json")):
            ledger = read(p)
            updates += len(ledger["confirmed_updates"]) + (ledger["in_flight"] is not None)
        failures = []
        for p in sorted(e.glob("*/node*/result.json")):
            w = read(p)
            if w["status"] == "FAIL_STOP":
                files = {f.name:identity(f) for f in p.parent.iterdir() if f.is_file() and f.suffix in {".jsonl", ".maps", ".numa_maps", ".status"}}
                failures.append(dict(file=identity(p),error=w["error"],completed_updates=w["completed_updates"], raw=files,
                    first_numeric_failure=next((r for r in w["metrics"] if not r["passed"]),None),attention=w.get("attention")))
        report["failures"] = failures
        if n["state"] == "SUCCEEDED":
            assert app["status"] == "PASS_FULL_NODE_COMPLETED_PHASES" and app["hbm_pool_restored"] is True
            assert read(e / "pool_return_terminal.json")["passed"] and updates == b["max_model_updates"]
            assert {"strict_baseline","strict_candidate"} <= report["phases"].keys()
            if cert:
                assert set(neg) == {"missing","wrong_sha","outside"} and all(x["passed"] and x["before_any_worker"] for x in neg.values())
                report["status"] = "PASS_HBM_LIB_CERT"
            elif not b["pairs"]:
                report["status"] = "PASS_BF16_STRICT5"
            else:
                rates = {side:[] for side in ("baseline","candidate")}
                for run in range(1,4):
                    a, z = (f"perf_{side}_r{run}" for side in rates)
                    same_input(seqs[a],seqs[z])
                    for side, label in zip(rates,(a,z)):
                        rates[side].append(report["phases"][label]["visits_per_second"])
                spread = {side:100*(max(v)-min(v))/median(v) for side,v in rates.items()}
                gains = [100*(v/u-1) for u,v in zip(rates["baseline"],rates["candidate"])]
                report["paired_performance"] = dict(rates=rates,spread_pct=spread,gain_pct=gains)
                report["status"] = "BF16_FOUR_DOMAIN_CANDIDATE" if spread["candidate"] <= 5 and min(gains)>0 else "BF16_FOUR_DOMAIN_REJECTED"
        elif any(f["first_numeric_failure"] or "unchanged/exact" in f["error"] for f in failures):
            report["status"] = "HBM_LIB_NUMERICAL_FAIL" if cert else "BF16_REJECTED_NUMERICAL_FAIL"
    assert 0 <= updates <= b["max_model_updates"] and 0 <= allocation <= b["wall_seconds"] and queue >= 0
    book = read(HERE/"BUDGET_LEDGER.json")
    assert len(book["attempts"]) == b["submission_ordinal"]-1
    attempt = dict(job_id=job, version=version, state=n["state"], outcome=report["status"], host=report.get("host"),
          allocation_seconds=allocation, queue_seconds=queue, updates=updates, terminal=True,
          cleanup="ALL_REAPED" if allocation else "NO_ALLOCATION", native=identity(raw/"djob_final.json"), archive=report["archive"])
    book["attempts"].append(attempt)
    for key in ("allocation_seconds", "queue_seconds", "updates"):
        book[key] += attempt[key]
    book["actual_hosts"] = sorted({x["host"] for x in book["attempts"] if x["host"]})
    assert book["allocation_seconds"] <= 14400 and book["queue_seconds"] <= 86400 and book["updates"] <= 4000
    assert len(book["actual_hosts"]) <= 2 and len(book["attempts"]) <= 4
    save(HERE/"BUDGET_LEDGER.json",book)
    save(folder/"ANALYSIS.json",report)
    if cert:
        save(HERE/"HBM_LIB_CERT_RESULT.json",report)
    save(HERE/"ACTIVE_JOB.json",dict(active_job=None,last_terminal=attempt))
    print(job, report["status"], allocation, queue, updates)


if __name__ == "__main__":
    settle(*sys.argv[1:])
