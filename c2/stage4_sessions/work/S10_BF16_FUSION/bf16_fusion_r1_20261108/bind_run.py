"""Prepare one S10 native job binding from the remaining batch budget."""
import argparse
import ast
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
from zipfile import ZIP_DEFLATED, ZipFile

ROOT = Path(__file__).resolve().parent
REMOTE = "/home/share/dengqingtian/opt/stage4_sessions/S10_BF16_FUSION"
DESCRIPTOR_SHA = "b88ea9745147acf7fa70d51dc27c727f22f14e98af5dff1b80a9047e95648cd6"


def dump(value):
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def sha(data):
    return hashlib.sha256(data).hexdigest()


def load(path):
    return json.loads(path.read_bytes())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_id")
    parser.add_argument("host", choices=("cn21386", "cn21762"))
    parser.add_argument("domains", type=int, choices=(1, 4))
    parser.add_argument("seconds", type=int)
    parser.add_argument("--reverse", action="store_true")
    parser.add_argument("--candidate", choices=("F", "B"), default="F")
    args = parser.parse_args()
    assert re.fullmatch(r"S10_[A-Z0-9_]+", args.run_id)
    ledger = load(ROOT / "BUDGET_LEDGER.json")
    use, limits = ledger["consumed"], ledger["limits"]
    assert load(ROOT / "ACTIVE_JOB.json")["active_job"] is None
    assert all(row["state"] in ("SUCCEEDED", "FAILED", "CANCELLED", "SUBMIT_FAILED")
               for row in ledger["jobs"])
    assert 0 < args.seconds <= min(limits["job_seconds"], limits["allocated_seconds"] - use["allocated_seconds"])
    assert use["submissions"] < limits["submissions"]
    maximum_updates = 60 * args.domains if args.candidate == "F" else 10
    assert args.candidate != "B" or args.domains == 1
    assert use["model_updates"] + maximum_updates <= limits["model_updates"]
    assert use["frame_visits"] + maximum_updates * 64 <= limits["frame_visits"]
    queue_left = limits["queue_seconds"] - use["queue_seconds"]
    assert queue_left > 0
    remaining = (datetime.fromisoformat(ledger["deadline_utc"]) - datetime.now(timezone.utc)).total_seconds()
    assert remaining > args.seconds + 60
    work = ROOT.parent.parent
    active_paths = [
        work / "S00/numa_m1_straggler_r2_20261108/ACTIVE_JOB.json",
        work / "M23_MEMORY_HBM/memory_hbm_32e_r1_20261108/ACTIVE_JOB.json",
    ]
    other = [load(path) for path in active_paths]
    excluded = {"cn21341"}
    for row in other:
        if row.get("state") in ("SUCCEEDED", "FAILED", "CANCELLED"):
            continue
        excluded.update(row.get("eligible_hosts", []))
        if row.get("host"):
            excluded.add(row["host"])
    assert args.host not in excluded
    out = ROOT / "jobs" / args.run_id
    out.mkdir(parents=True, exist_ok=False)
    source = ROOT / ("f_run" if args.candidate == "F" else "b_run")
    files = {p.relative_to(source).as_posix(): p.read_bytes()
             for p in sorted(source.rglob("*")) if p.is_file() and "__pycache__" not in p.parts}
    for name, data in files.items():
        if name.endswith((".py", ".sh")):
            assert b"\r" not in data, name
        if name.endswith(".py"):
            ast.parse(data, filename=name, feature_version=(3, 9))
    assert sha(files["ENGINEERING_DESCRIPTOR.json"]) == DESCRIPTOR_SHA
    manifest = dump({name: sha(data) for name, data in files.items()})
    archive = out / "S10_PAYLOAD.zip"
    with ZipFile(archive, "x", ZIP_DEFLATED) as pack:
        for name, data in files.items():
            pack.writestr(name, data)
        pack.writestr("SOURCE_SHA256.json", manifest)
    with ZipFile(archive) as pack:
        assert pack.testzip() is None
        assert all(sha(pack.read(n)) == sha(d) for n, d in files.items())
    remote = REMOTE + "/" + args.run_id
    memory = args.domains * 24576
    exclusions = sorted(excluded)
    hosts = " ".join([args.host] + ["!" + n for n in exclusions])
    argv = ["dsub", "-J", "-q", "q_hpcai", "-x", "job", "-n", args.run_id,
            "-nl", hosts, "-R", f"cpu={args.domains * 38},mem={memory}MB", "-RL", f"mem={memory}MB",
            "-a", f"numa[count={args.domains},distribution=pack]", "-T", str(args.seconds),
            "--env", "none", "--cwd", remote, "-oo", remote + "/job.log",
            "bash", remote + "/run_job.sh", "BINDING_SHA256"]
    binding = dict(run_id=args.run_id, remote_root=remote, host=args.host, user_authorized=True,
                   mode="f_adamw_hbm" if args.candidate == "F" else "b_qkv_dw_hbm",
                   domain_count=args.domains, wall_seconds=args.seconds,
                   descriptor_sha256=DESCRIPTOR_SHA, source_manifest_sha256=sha(manifest),
                   package_sha256=sha(archive.read_bytes()), excluded_hosts=exclusions,
                   native_argv=argv, batch_deadline_utc=ledger["deadline_utc"],
                   remaining_queue_seconds=queue_left, reverse_performance=args.reverse,
                   prior_usage=use, other_windows=other)
    data = dump(binding)
    (out / "S10_RUN_BINDING.json").write_bytes(data)
    (out / "BINDING_SHA256.txt").write_text(sha(data) + "\n")
    print(json.dumps({k: binding[k] for k in ("remote_root", "host", "excluded_hosts", "package_sha256")}))
    print("BINDING_SHA256", sha(data))


if __name__ == "__main__":
    main()
