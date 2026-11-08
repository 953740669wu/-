"""Collect a terminal preferred-node attempt that never received resources."""
import hashlib
import subprocess
import sys
import zipfile

from prepare import ROOT, need, save, verify
from submit_once import detail, owned


def main(pin):
    binding = verify(ROOT, pin)
    job = (ROOT / "job_id.txt").read_text().strip()
    binding["native_argv"] = [pin if x == "BINDING_SHA256" else x for x in binding["native_argv"]]
    row = detail(job, "djob_final.json")
    need(owned(row, binding) and row["state"] in {"FAILED", "CANCELLED"}, "owned terminal required")
    need(row["startTime"] == "-" and all(not g.get("nodeResUsages") for g in row["resGroups"]),
         "allocated job requires normal collection")
    need(not (ROOT / "job_evidence").exists(), "worker evidence unexpectedly exists")
    pid = int((ROOT / "login_submit_pid.txt").read_text())
    proc = subprocess.run(["ps", "-o", "stat=", "-p", str(pid)], capture_output=True, text=True, timeout=5)
    need(proc.returncode == 1 or proc.stdout.strip().startswith("Z"), "login submit process still live")
    save(ROOT / "UNALLOCATED_CLEANUP.json", dict(job_id=job, start_time=row["startTime"],
         allocated_nodes=[], job_evidence_exists=False, login_pid=pid, login_pid_status=proc.stdout.strip(),
         scheduler_state=row["state"], exit_code=row.get("exitCode")))
    files = {p.relative_to(ROOT).as_posix():p for p in sorted(ROOT.rglob("*")) if p.is_file()}
    index = {n:dict(bytes=p.stat().st_size, sha256=hashlib.sha256(p.read_bytes()).hexdigest(), archive=True)
             for n,p in files.items()}
    save(ROOT / "COLLECTION_INDEX.json", dict(job_id=job, state=row["state"], pids=[], files=index))
    bundle = ROOT / f"JOB_{job}_evidence.zip"
    with zipfile.ZipFile(bundle, "x", zipfile.ZIP_DEFLATED) as z:
        for n,p in files.items():
            z.write(p,n)
        z.write(ROOT / "COLLECTION_INDEX.json", "COLLECTION_INDEX.json")
    save(ROOT / "bundle_receipt.json", dict(job_id=job, bytes=bundle.stat().st_size,
         sha256=hashlib.sha256(bundle.read_bytes()).hexdigest(), members=len(files)+1,
         state=row["state"], pids=[]))


if __name__ == "__main__":
    main(sys.argv[1])
