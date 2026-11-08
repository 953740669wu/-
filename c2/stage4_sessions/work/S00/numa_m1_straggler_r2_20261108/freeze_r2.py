"""Freeze the bounded original/rank-rotated R2 target comparison."""
import ast
from datetime import datetime, timedelta, timezone
import difflib
import hashlib
import json
from pathlib import Path
import re
import shlex
import sys
import zipfile

HERE = Path(__file__).resolve().parent
OLD = HERE.parent / "numa_m1_replace_node_20261108"
COORD = HERE.parents[1] / "COORDINATION"
CARD = COORD / "NUMA_STRAGGLER_S00_LONG_R2_20261108.md"
BUDGET = CARD.with_name(CARD.stem + "_BUDGET.json")
REVIEW = COORD / "NUMA_HBM_RESULTS_REVIEW_20261108.json"
START = datetime.fromisoformat("2026-11-08T02:10:59.477070+00:00")


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def identify(path):
    raw = path.read_bytes()
    return dict(path=str(path),bytes=len(raw),sha256=sha(raw))


def read(path):
    return json.loads(path.read_bytes())


def write(path,value):
    path.write_bytes((json.dumps(value,indent=2,sort_keys=True,ensure_ascii=False)+"\n").encode())


def main(version, hosts, queue_attempt):
    assert re.fullmatch(r"[A-Z0-9_]+",version) and hosts and len(set(hosts))==len(hosts)
    assert all(re.fullmatch(r"cn[0-9]+",host) for host in hosts)
    assert identify(CARD)["sha256"] == read(BUDGET)["task_card_sha256"]
    assert identify(OLD/"NUMA_M1.zip")["sha256"] == "1be8cab8371f38320fc6be2543d20989ea09ea506f38369918874aa2142437c9"
    review=read(REVIEW)
    assert review["errors"]==[] and review["source_results"][str(OLD/"NUMA_RUN_RESULT.json")]==identify(OLD/"NUMA_RUN_RESULT.json")["sha256"]
    ledger_file=HERE/"BUDGET_LEDGER.json"
    limits=read(BUDGET)["limits"]
    deadline=START+timedelta(seconds=limits["batch_wall_seconds"])
    ledger=read(ledger_file) if ledger_file.exists() else dict(start_utc=START.isoformat(),
        deadline_utc=deadline.isoformat(), limits=limits, user_authorized=True, attempts=[],
        old_batch_history=dict(submissions=5,allocated_seconds=736,queue_seconds=7584,job_2061246=identify(OLD/"NUMA_RUN_RESULT.json")))
    assert ledger["start_utc"]==START.isoformat() and ledger["deadline_utc"]==deadline.isoformat()
    attempts=ledger["attempts"]
    assert all(x["terminal_confirmed"] and x["cleanup_confirmed"] for x in attempts)
    assert len(attempts)<limits["submissions"]
    assert len({x["host"] for x in attempts if x.get("host")} | set(hosts))<=limits["physical_hosts_max"]
    allocated=sum(x["allocation_seconds_charged"] for x in attempts)
    queued=sum(x["queue_seconds"] for x in attempts)
    micro=sum(x.get("microprobe_charged_seconds",0) for x in attempts)
    wall=min(limits["job_seconds"],limits["allocated_seconds"]-allocated)
    now=datetime.now(timezone.utc)
    assert wall==1800 and now<deadline-timedelta(seconds=wall+60)
    queue_left=limits["queue_seconds"]-queued
    assert queue_left>0 and queue_attempt>0
    old=read(OLD/"NUMA_RUN_BINDING.json")
    with zipfile.ZipFile(OLD/"NUMA_M1.zip") as z:
        before={n:z.read(n) for n in z.namelist() if n!="SOURCE_SHA256.json"}
    after={n:(HERE/"src"/n).read_bytes() for n in before}
    changed={n for n in before if before[n]!=after[n]}
    assert changed=={"prepare.py","submit_once.py","launch.py","payload/worker.py"}
    assert all(b"\r" not in after[n] for n in changed)
    for n in changed:
        ast.parse(after[n],filename=n,feature_version=(3,9))
    shell_exec,=(line for line in after["run_worker.sh"].decode().splitlines() if line.startswith("exec "))
    assert shlex.split(shell_exec)==["exec","/usr/bin/numactl","--physcpubind=$CPUS","--membind=$NODE",
                                    "$C2_PYTHON","-B","$ROOT/payload/worker.py","$@"]
    assert b'phase("perf_rotated", contracts, owner, binding, host, end, rotation=1)' in after["launch.py"]
    target=HERE/version
    target.mkdir()
    diff=[line for n in sorted(changed) for line in difflib.unified_diff(
        before[n].decode().splitlines(True),after[n].decode().splitlines(True),
        fromfile="R1/"+n,tofile=version+"/"+n)]
    (target/"TARGET_CHANGES.diff").write_bytes("".join(diff).encode())
    manifest=(json.dumps({n:sha(raw) for n,raw in after.items()},indent=2,sort_keys=True)+"\n").encode()
    after["SOURCE_SHA256.json"]=manifest
    archive=target/"NUMA_M1.zip"
    with zipfile.ZipFile(archive,"x",zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for n,raw in after.items():
            info=zipfile.ZipInfo(n)
            info.compress_type=zipfile.ZIP_DEFLATED
            z.writestr(info,raw,compresslevel=9)
    with zipfile.ZipFile(archive) as z:
        assert z.namelist()==list(after) and all(z.read(n)==raw for n,raw in after.items())
    remote="/home/share/dengqingtian/opt/stage4_sessions/S00/NUMA_M1_R2_"+version
    argv=[x.replace(old["remote_root"],remote) for x in old["native_argv"]]
    argv[argv.index("-nl")+1]=" ".join(hosts)
    argv[argv.index("-T")+1]=str(wall)
    binding=dict(version=version,mode="rank_rotation_ddr",remote_root=remote,eligible_hosts=hosts,
        wall_seconds=wall,batch_deadline_utc=deadline.isoformat(timespec="seconds"),
        queue_cutoff_utc=(now+timedelta(seconds=queue_left)).isoformat(timespec="seconds"),
        queue_attempt_seconds=queue_attempt,allow_preferred_queue=hosts==["cn21341"],
        package_sha256=identify(archive)["sha256"],source_manifest_sha256=sha(manifest),
        descriptor_sha256=old["descriptor_sha256"],numeric=old["numeric"],scope=old["scope"],
        native_argv=argv,user_authorized=True,submission_ordinal=len(attempts)+1,
        old_numeric_and_source_scope_preserved=True,
        microprobe_seconds_max=max(0,min(90,120-micro-30)),
        diagnostic=dict(rank_rotation=[0,1],full_updates_max=240,first_5_warmup=True,
                        microprobe_allocation_budget_seconds=120,actual_job_mapped_host=True),
        task_card=identify(CARD),prior_baseline=identify(OLD/"NUMA_RUN_RESULT.json"),prior_review=identify(REVIEW),
        current_budget=dict(allocated_before=allocated,queued_before=queued,attempts_before=len(attempts)))
    output=target/"NUMA_RUN_BINDING.json"
    write(output,binding)
    write(ledger_file,ledger)
    print(remote, binding["package_sha256"], identify(output)["sha256"])


if __name__=="__main__":
    main(sys.argv[1],sys.argv[3:],int(sys.argv[2]))
