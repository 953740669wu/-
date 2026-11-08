"""Verify returned ZIP bytes and compare physical-domain/rank assignments."""
from collections import Counter
import hashlib
import json
from pathlib import Path, PurePosixPath
from statistics import median
import sys
import tarfile
import zipfile

from read_baseline import analyze, affinity, jsonl, locality, read


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def unpack(folder, job, transfer_sha):
    transfer = folder / f"JOB_{job}_TRANSFER.tgz"
    bundle = folder / f"JOB_{job}_evidence.zip"
    assert sha(transfer.read_bytes()) == transfer_sha
    with tarfile.open(transfer) as tar:
        assert set(tar.getnames()) == {bundle.name,"bundle_receipt.json"}
        for name in (bundle.name,"bundle_receipt.json"):
            member = tar.getmember(name)
            assert member.isfile()
            with tar.extractfile(member) as stream:
                (folder/name).write_bytes(stream.read())
    receipt = read(folder/"bundle_receipt.json")
    assert receipt["job_id"] == job and bundle.stat().st_size == receipt["bytes"]
    assert sha(bundle.read_bytes()) == receipt["sha256"]
    target = folder/"received"
    assert not target.exists()
    with zipfile.ZipFile(bundle) as z:
        names = z.namelist()
        assert len(set(names)) == len(names) == receipt["members"]
        assert all(not PurePosixPath(n).is_absolute() and ".." not in PurePosixPath(n).parts and chr(92) not in n and ":" not in n for n in names)
        index = json.loads(z.read("COLLECTION_INDEX.json"))
        assert set(names) == {n for n,r in index["files"].items() if r["archive"]}|{"COLLECTION_INDEX.json"}
        for n,row in index["files"].items():
            if row["archive"]:
                raw = z.read(n)
                assert len(raw)==row["bytes"] and sha(raw)==row["sha256"], n
        z.extractall(target)
    return target


def collect_probe(evidence, topology):
    probe = evidence/"probe"
    if not (probe/"phase_receipt.json").is_file():
        return dict(status="NOT_RUN_OR_INCOMPLETE",domains={})
    samples = {}
    for node, receipt in topology["contracts"].items():
        worker = probe/f"node{node}"
        value = read(worker/"result.json")
        assert value["status"] == "PASS_TARGET_MICROPROBE" and value["completed_updates"] == 0
        assert value["copy_bytes_per_side"] == 128*2**20 and list(value["probe_native_shapes"].values()) == [4]
        assert len(value["probe"]) == 8
        samples[node] = dict(affinity=affinity(probe,topology,node,receipt),output_sha256=value["probe_output_sha256"],
            kernel_seconds=median(x["seconds"] for x in value["probe"] if not x["warmup"] and x["kind"]=="KML_DW"),
            copy_seconds=median(x["seconds"] for x in value["probe"] if not x["warmup"] and x["kind"]=="LOCAL_COPY"),
            memory_placement=locality(worker/"probe_finished.numa_maps",node),raw_samples=value["probe"])
    return dict(status="PASS",domains=samples,
                same_output_sha=len({x["output_sha256"] for x in samples.values()})==1)


def phase_data(raw, name):
    evidence = raw/"job_evidence"/name
    value = analyze(raw,int((raw/"login_clock_ticks.txt").read_text()),name)
    ranks = read(evidence/"rank_map.json")
    actual = {r["logical_rank"]:int(node) for node in value["domains"]
              for r in [read(evidence/f"node{node}/result.json")]}
    assert {int(k):v for k,v in ranks["logical_to_physical"].items()} == actual
    assert ranks["spawn_order"] == [actual[n] for n in sorted(actual)]
    value["rank_map"] = ranks
    value["slowest_logical_rank"] = next(rank for rank,node in actual.items() if node==int(value["slowest_domain"]))
    value["sync_rate_share_pct"] = 100*value["measured_common_window_frames_s"]/value["sum_domain_frames_s"]
    samples = jsonl(evidence/"cpu_samples.jsonl")
    freq = {cpu:Counter() for row in samples for cpu in row.get("scaling_cur_freq_kHz",{})}
    for row in samples:
        for cpu,val in row.get("scaling_cur_freq_kHz",{}).items():
            freq[cpu][str(val)] += 1
    value["frequency_sysfs_kHz_observed"] = {cpu:dict(c) for cpu,c in freq.items()}
    for node, summary in value["domains"].items():
        rows = [r for r in jsonl(evidence/f"node{node}/steps.jsonl") if r["sampled"]]
        if "native_sgemm_ns_by_shape" not in rows[0]:
            continue
        timing = [r["native_sgemm_ns_by_shape"] for r in rows]
        assert all(set(t) == set(r["native_shapes"]) and 0 < sum(t.values()) <= r["end_ns"]-r["start_ns"]
                   for r,t in zip(rows,timing))
        summary["native_sgemm_seconds_median"] = median(sum(t.values()) for t in timing)/1e9
        summary["remaining_step_seconds_median"] = median(r["step_seconds"]-sum(t.values())/1e9
                                                         for r,t in zip(rows,timing))
        summary["native_sgemm_seconds_median_by_shape"] = {
            shape:median(t[shape] for t in timing)/1e9 for shape in timing[0]}
    return value


def main(folder,job,transfer_sha):
    raw = unpack(folder,job,transfer_sha)
    native, = read(raw/"djob_final.json")["data"]["successData"]
    assert native["jobId"] == job
    result = dict(job_id=job,native_state=native["state"])
    evidence = raw/"job_evidence"
    if not (evidence/"SUMMARY.json").is_file():
        result["status"] = "NO_MODEL_START"
    else:
        app = read(evidence/"SUMMARY.json")
        result["status"] = app["status"]
        result["summary"] = app
        if (evidence/"domain_map.json").is_file():
            topology = read(evidence/"domain_map.json")
            result["host"] = topology["context"]["host"]
            result["stages"] = {name:phase_data(raw,name) for name in ("perf","perf_rotated")
                                if (evidence/name/"phase_receipt.json").is_file()}
            result["probe"] = collect_probe(evidence,topology)
            if len(result["stages"])==2:
                first,second = result["stages"].values()
                assert first["rank_map"]["rotation"] == 0 and second["rank_map"]["rotation"] == 1
                assert set(first["domains"]) == set(second["domains"])
                assert all(first["domains"][n]["final_model_sha256"] == second["domains"][n]["final_model_sha256"] for n in first["domains"])
                result["actual_pair_workload"] = dict(strict_updates=40,perf_updates=200,training_frame_exposures=15360)
    (folder/"ANALYSIS.json").write_bytes((json.dumps(result,indent=2,ensure_ascii=False)+"\n").encode())
    print(result["status"],result.get("host"))
    for name,x in result.get("stages",{}).items():
        print(name,x["rank_map"]["logical_to_physical"],x["slowest_domain"],x["slowest_logical_rank"],
              [round(r["sampled_seconds"]["median"],3) for r in x["domains"].values()],
              round(x["measured_common_window_frames_s"],3))
    for n,x in result.get("probe",{}).get("domains",{}).items():
        print("probe",n,x["kernel_seconds"],x["copy_seconds"])


if __name__=="__main__":
    main(Path(sys.argv[1]).resolve(),sys.argv[2],sys.argv[3])
