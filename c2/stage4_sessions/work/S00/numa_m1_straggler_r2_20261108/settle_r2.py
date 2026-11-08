"""Charge one collected terminal attempt before any further submission."""
from datetime import datetime
import math
from pathlib import Path
import sys

from freeze_r2 import HERE, identify, read, write


def native_time(value):
    if "/" in value:
        return datetime.strptime(value, "%Y/%m/%d %H:%M:%S")
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def main(folder):
    raw = folder/"received"
    binding = read(folder/"NUMA_RUN_BINDING.json")
    receipt = read(folder/"bundle_receipt.json")
    job, = read(raw/"djob_final.json")["data"]["successData"]
    assert job["jobId"] == receipt["job_id"] and job["state"] == receipt["state"]
    assert job["state"] in {"FAILED", "SUCCEEDED", "CANCELLED"}
    native_nodes = [n for g in job["resGroups"] for n in g.get("nodeResUsages") or []]
    evidence = raw/"job_evidence"
    if job["startTime"] == "-":
        clean = read(raw/"UNALLOCATED_CLEANUP.json")
        assert not native_nodes and not receipt["pids"] and clean["job_id"] == job["jobId"]
        assert clean["job_evidence_exists"] is False and clean["allocated_nodes"] == []
        host, allocation, updates, micro = None, 0, 0, 0
        queue_end = native_time(job["endTime"])
        cleanup = raw/"UNALLOCATED_CLEANUP.json"
    else:
        node, = native_nodes
        host = node["execNode"]
        assert host in binding["eligible_hosts"] and [node["pids"]] == receipt["pids"] == ["-"]
        queue_end = native_time(job["startTime"])
        allocation = max(node["wallclockDuration"], int((native_time(job["endTime"])-queue_end).total_seconds()))
        cleanup = evidence/"cleanup.json"
        clean = read(cleanup)
        assert clean["all_reaped"] and not clean["remaining_live"] and not clean["remaining_processes"]
        app = read(evidence/"SUMMARY.json")
        assert app["job_id"] == job["jobId"]
        updates = 0
        for stage in ("strict", "perf", "perf_rotated"):
            for log in (evidence/stage).glob("node*/steps.jsonl"):
                updates += len(log.read_bytes().splitlines())
        assert 0 <= updates <= binding["diagnostic"]["full_updates_max"]
        elapsed = app.get("probe_seconds_before_cleanup", 0)
        if elapsed and app.get("probe") != "PASS_TARGET_MICROPROBE":
            elapsed += min(30, max(0, clean["finished"] - clean["started"]))
        micro = min(120, math.ceil(elapsed))
    queue = int((queue_end-native_time(job["createTime"])).total_seconds())
    assert allocation >= 0 and queue >= 0
    path = HERE/"BUDGET_LEDGER.json"
    ledger = read(path)
    attempts = ledger["attempts"]
    assert job["jobId"] not in {a["job_id"] for a in attempts}
    assert binding["submission_ordinal"] == len(attempts)+1
    record = dict(job_id=job["jobId"],ordinal=binding["submission_ordinal"],version=binding["version"],
        host=host,native_state=job["state"],native_exit_code=job.get("exitCode"),
        queue_seconds=queue,allocation_seconds_charged=allocation,microprobe_charged_seconds=micro,
        confirmed_logged_updates=updates,confirmed_training_frame_exposures=64*updates,
        possible_updates_upper_bound=updates if job["state"]=="SUCCEEDED" else
            (binding["diagnostic"]["full_updates_max"] if allocation else 0),
        terminal_confirmed=True,cleanup_confirmed=True,
        package=identify(folder/"NUMA_M1.zip"),binding=identify(folder/"NUMA_RUN_BINDING.json"),
        native=identify(raw/"djob_final.json"),cleanup=identify(cleanup),transfer=identify(folder/f"JOB_{job['jobId']}_TRANSFER.tgz"))
    attempts.append(record)
    write(path,ledger)
    print(record["job_id"],record["native_state"],host,queue,allocation,updates,micro)


if __name__=="__main__":
    main(Path(sys.argv[1]).resolve())
