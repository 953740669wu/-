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


def query(argv, filename, brief=False):
    p = subprocess.run(argv, capture_output=True, timeout=10)
    (ROOT / filename).write_bytes(p.stdout)
    (ROOT / (filename + ".stderr")).write_bytes(p.stderr)
    need(p.returncode == 0, "native query failed: " + repr(argv))
    if brief:
        pending = p.stdout.decode().strip()
        decoder, rows = json.JSONDecoder(), {}
        need(pending, "native queue returned no documents")
        while pending:
            doc, end = decoder.raw_decode(pending)
            pending = pending[end:].lstrip()
            need(doc["code"] == "success" and len(doc["data"]) == doc["totalElements"], "incomplete native queue list")
            rows.update({str(r["jobId"]):r for r in doc["data"]})
        need(len(rows) <= 20, "too many active jobs to verify native deduplication")
        return list(rows.values())
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
                           ("FIXED_INPUTS_BEFORE.json","FIXED16_CURRENT_SOURCE_SHA_PASS")):
        need(json.loads((ROOT/file).read_bytes())["status"] == expected, "fixed input login check missing")
    live = query(["djob","-J"],"queue_before_submit.json",brief=True)
    for job in live:
        row = detail(str(job["jobId"]),f"active_{job['jobId']}.json")
        if row["state"] in {"SUCCEEDED","FAILED","CANCELLED"}:
            continue
        need("NUMA_M1_R1_" not in row.get("execPath","") + row.get("cmd",""), "active M1 job already exists")
        if "/M23_MEMORY_HBM/" in row.get("execPath","") + row.get("cmd",""):
            groups = row["resGroups"]
            nodes = {n["execNode"] for g in groups for n in g["nodeResUsages"]}
            preferred = {n for g in groups for n in re.findall(r"cn[0-9]+", g.get("preferNodes",""))}
            need(not (nodes | preferred) & set(binding["eligible_hosts"]), "M23 node conflict")
    queue = query(["dqueue","-J","-l","q_hpcai"],"queue_resource.json")["data"][0]
    need(set(queue["status"]) == {"OPEN","ACTIVE"} and queue["exclusive"] == "job" and queue["requeueTimes"] == 0,
         "native exclusive queue/retry conditions differ")
    available = []
    for host in binding["eligible_hosts"]:
        row, = query(["dnode","-J","-l",host],f"host_{host}_before_submit.json")["data"]
        info = row["numaInfo"]
        load = row["nativeResources"]["loadResources"]
        need(row["nodeName"] == host and "q_hpcai" in row["queues"].split(",")
             and info["architecture"] == "aarch64" and info["nNumaNodes"] == 16 and info["nThreadsPerCore"] == 1,
             "site eligible-node class changed: " + host)
        if row["status"] == "OK" and row["runningJobsCount"] == 0 and load["cpuFree"] >= 152 and load["memFree"] >= 98304:
            available.append(host)
    need(available, "no vetted host is presently idle")
    until = datetime.fromisoformat(binding["batch_deadline_utc"])
    room = (until - datetime.now(timezone.utc)).total_seconds()
    need(room > binding["wall_seconds"] + 60, "insufficient batch time to execute full job")
    reset_cutoff = datetime.fromisoformat(binding["queue_cutoff_utc"])
    queue_room = (reset_cutoff-datetime.now(timezone.utc)).total_seconds()
    need(queue_room > 0, "user-reset queue cutoff elapsed")
    stop_queue = time.monotonic() + min(queue_room,room-binding["wall_seconds"]-60)
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
        time.sleep(.5)


if __name__ == "__main__":
    main(sys.argv[1])
