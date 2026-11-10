"""Login-only native dedup, once marker and live allocation publication."""
from datetime import datetime, timezone
import json
import os
import re
import shlex
import subprocess
import sys
import time

from prepare import ROOT, need, save, verify
from scheduler_handoff import publish


def query(argv, filename):
    p = subprocess.run(argv, capture_output=True, timeout=10)
    (ROOT / filename).write_bytes(p.stdout)
    (ROOT / (filename + ".stderr")).write_bytes(p.stderr)
    need(p.returncode == 0, "native query failed: " + repr(argv))
    if argv == ["djob", "-J"]:
        decoder = json.JSONDecoder()
        raw = p.stdout.decode().strip()
        need(raw, "empty native queue response")
        rows = []
        while raw:
            page, end = decoder.raw_decode(raw)
            need(page["code"] == "success" and len(page["data"]) == page["totalElements"],
                 "incomplete native queue page")
            rows.extend(page["data"])
            raw = raw[end:].lstrip()
        return dict(data=rows, totalElements=len(rows))
    value = json.loads(p.stdout)
    need(value["code"] == "success", "native query failed: " + repr(argv))
    return value


def owned(row, binding):
    expected = binding["native_argv"]
    return (row["execPath"] == str(ROOT) and shlex.split(row["cmd"]) == expected[expected.index("bash"):]
            and row["logRedirectPath"]["stdoutRedirectPath"] == str(ROOT / "job.log"))


def detail(job, label):
    need(re.fullmatch(r"[1-9][0-9]*",job), "invalid native job id")
    value = query(["djob","-J","-l",job],label)
    row, = value["data"]["successData"]
    need(str(row["jobId"]) == job, "native detail returned other job")
    return row


def main(pin):
    binding = verify(ROOT,pin)
    need(sys.platform == "linux" and not os.getenv("CCS_JOB_ID"), "native login required")
    need(not any((ROOT / name).exists() for name in ("submit_once.marker","job_id.txt","job_evidence")),
         "existing run: read-only reconciliation only")
    ready = json.loads((ROOT / "site_static.json").read_bytes())
    need(ready["status"] == "SHA_LF_AST_BASH_PASS" and ready["binding_sha256"] == pin, "static deployment gate missing")
    for file, expected in (("LOGIN_METADATA_CHECK.json","ENGINEERING_METADATA_HASH_GATE_PASS"),
                           ("FIXED_INPUTS_BEFORE.json",binding["fixed_input_status"])):
        need(json.loads((ROOT/file).read_bytes())["status"] == expected, "fixed input login check missing")
    live = query(["djob","-J"],"queue_before_submit.json")
    need(len(live["data"]) == live["totalElements"] <= 20, "incomplete native queue list")
    for job in live["data"]:
        row = detail(str(job["jobId"]),f"active_{job['jobId']}.json")
        if row["state"] in {"SUCCEEDED","FAILED","CANCELLED"}:
            continue
        path = row["execPath"]
        need("/stage4_sessions/S00/" not in path, "active S00 job already exists")
        if any(s in path for s in ("/M23_MEMORY_HBM/","/S10_BF16_FUSION/")):
            groups = row["resGroups"]
            nodes = {n["execNode"] for g in groups for n in g.get("nodeResUsages") or []}
            preferred = {n.strip() for g in groups for n in g["preferNodes"].split(",")
                         if not nodes and re.fullmatch(r"cn[0-9]+",n.strip())}
            need(not (nodes | preferred) & set(binding["eligible_hosts"]), "other-window host conflict")
    queue = query(["dqueue","-J","-l","q_hpcai"],"queue_resource.json")["data"][0]
    need(set(queue["status"]) == {"OPEN","ACTIVE"} and queue["exclusive"] == "job" and queue["requeueTimes"] == 0,
         "native exclusive queue/retry conditions differ")
    qualified = []
    for host in binding["eligible_hosts"]:
        row, = query(["dnode","-J","-l",host],f"host_{host}_before_submit.json")["data"]
        topo = row["numaInfo"]
        res = row["nativeResources"]["loadResources"]
        need(row["nodeName"] == host and host not in binding["excluded_hosts"]
             and "q_hpcai" in row["queues"].split(",") and topo["architecture"] == "aarch64"
             and topo["nNumaNodes"] == 16 and topo["nCoresPerNode"] * topo["nSockets"] == 608
             and topo["nThreadsPerCore"] == 1,
             f"node class differs: {host}")
        if (row["status"] == "OK" and row["runningJobsCount"] == 0 and res["cpuFree"] >= 608
                and res["memFree"] >= 393216 and res["hugePagesFree"] >= 16*(binding["hbm_cap_MiB"]//2+16)):
            qualified.append(host)
    need(qualified, "no eligible host currently shows full-node CPU, DDR and hugepage capacity")
    until = datetime.fromisoformat(binding["batch_deadline_utc"])
    room = (until - datetime.now(timezone.utc)).total_seconds()
    need(room > binding["wall_seconds"] + 120, "insufficient batch time to execute full job")
    stop_queue = time.monotonic() + min(binding["remaining_queue_seconds"],room-binding["wall_seconds"]-120)
    argv = binding["native_argv"]
    # The source pin is passed as its explicit runtime operand, avoiding a self-hash cycle.
    argv = [pin if a == "BINDING_SHA256" else a for a in argv]
    command = dict(argv=argv, binding_sha256=pin, created_utc=datetime.now(timezone.utc).isoformat())
    save(ROOT / "submission.command.json", command)
    with (ROOT / "submit_once.marker").open("x") as marker:
        marker.write(json.dumps(command) + "\n")
        marker.flush()
        os.fsync(marker.fileno())
    try:
        response = subprocess.run(argv,capture_output=True,timeout=10)
    except subprocess.TimeoutExpired as exc:
        (ROOT / "submission.stdout").write_bytes(exc.stdout or b"")
        (ROOT / "submission.stderr").write_bytes(exc.stderr or b"")
        save(ROOT / "submission.result.json", dict(state="AMBIGUOUS_NO_RESUBMIT"))
        raise
    (ROOT / "submission.stdout").write_bytes(response.stdout)
    (ROOT / "submission.stderr").write_bytes(response.stderr)
    save(ROOT / "submission.result.json", dict(returncode=response.returncode))
    need(response.returncode == 0,"native submission failed; reconcile only")
    job = str(json.loads(response.stdout)["data"]["jobId"])
    need(re.fullmatch(r"[1-9][0-9]*",job),"ambiguous submission ID")
    (ROOT/"job_id.txt").write_text(job+"\n")
    actual = dict(binding,native_argv=argv)
    while True:
        row = detail(job,"scheduler_observed.json")
        need(owned(row,actual),"native job ownership differs")
        if row["state"] == "RUNNING":
            publish(ROOT,job)
            print("PUBLISHED_ONCE",job,flush=True)
            return
        if row["state"] in {"SUCCEEDED","FAILED","CANCELLED"}:
            print("TERMINAL_BEFORE_PUBLICATION",job,row["state"],flush=True)
            return
        if time.monotonic() >= stop_queue:
            need(row["state"] == "PENDING","queue cutoff but state not verified pending")
            p = subprocess.run(["dkill","-y","-s","PENDING",job],capture_output=True,timeout=10)
            (ROOT/"cancel.stdout").write_bytes(p.stdout)
            (ROOT/"cancel.stderr").write_bytes(p.stderr)
            print("QUEUE_CUTOFF",job,p.returncode,flush=True)
            return
        time.sleep(5)


if __name__ == "__main__":
    main(sys.argv[1])
