"""Freeze an isolated FFN candidate, original model, and inherited R3 budget."""
import ast
from datetime import datetime, timedelta, timezone
import difflib
import hashlib
import json
from pathlib import Path
import re
import sys
import zipfile

ROOT=Path(__file__).resolve().parent
R2=ROOT.parent/"numa_m1_straggler_r2_20261108"
R3=ROOT.parent/"numa_root_cause_r3_20261108"
WORK=ROOT.parents[1]
CARD=WORK/"COORDINATION"/"S00_HEALTHY_NODE_OPTIMIZATION_CONTINUE_20261108.md"


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def identity(path):
    raw=path.read_bytes()
    return dict(path=str(path),sha256=sha(raw),bytes=len(raw))


def read(path):
    return json.loads(path.read_bytes())


def write(path,value):
    path.write_bytes((json.dumps(value,indent=2,sort_keys=True,ensure_ascii=False)+"\n").encode())


def main(version,hosts):
    assert re.fullmatch(r"[A-Z0-9_]+",version) and hosts and len(hosts)==len(set(hosts))
    assert all(re.fullmatch(r"cn[0-9]+",h) for h in hosts) and "cn21341" not in hosts
    ledger=read(ROOT/"BUDGET_LEDGER.json")
    inherited=read(R3/"BUDGET_LEDGER.json")
    assert ledger["start_utc"]==inherited["start_utc"]=="2026-11-08T03:12:39+00:00"
    assert ledger["deadline_utc"]==inherited["deadline_utc"]=="2026-11-08T15:12:39+00:00"
    attempts=ledger["attempts"]
    assert attempts[:1]==inherited["attempts"] and attempts[0]["job_id"]=="2063398"
    assert all(a["terminal_confirmed"] and a["cleanup_confirmed"] for a in attempts)
    limits=ledger["limits"]
    assert len(attempts)<limits["submissions"]
    used_hosts={a["host"] for a in attempts if a["host"]}
    assert len(used_hosts)<limits["hosts"] or set(hosts)<=used_hosts
    allocated=sum(a["allocated_seconds"] for a in attempts)
    queued=sum(a["queue_seconds"] for a in attempts)
    updates=sum(a["model_updates_upper_bound"] for a in attempts)
    wall=min(limits["job_seconds"],limits["allocated_seconds"]-allocated)
    deadline=datetime.fromisoformat(ledger["deadline_utc"])
    assert wall>=1200 and queued<limits["queue_seconds"] and updates+240<=limits["model_updates"]
    assert datetime.now(timezone.utc)<deadline-timedelta(seconds=wall+60)
    reference=R2/"ALT_B"/"NUMA_M1.zip"
    assert identity(reference)["sha256"]=="171e6e98f7dde718b166017597dd6baea509bceeadf08fcda79c7820525ede54"
    old=read(R2/"ALT_B"/"NUMA_RUN_BINDING.json")
    with zipfile.ZipFile(reference) as z:
        before={n:z.read(n) for n in z.namelist() if n!="SOURCE_SHA256.json"}
    candidate="payload/ffn_relu_reuse.py"
    after={n:(ROOT/"src"/n).read_bytes() for n in (*before,candidate)}
    modified={n for n in before if after[n]!=before[n]}
    assert modified=={"prepare.py","submit_once.py","launch.py","payload/worker.py"}
    for name,raw in after.items():
        if name.endswith((".py",".sh")):
            assert b"\r" not in raw, name
        if name.endswith(".py"):
            ast.parse(raw,filename=name,feature_version=(3,9))
    folder=ROOT/version
    folder.mkdir()
    diff=lambda n: difflib.unified_diff(before.get(n,b"").decode().splitlines(True),after[n].decode().splitlines(True),
                    fromfile="R2/"+n if n in before else "/dev/null",tofile=version+"/"+n)
    (folder/"CANDIDATE.diff").write_bytes("".join(diff(candidate)).encode())
    (folder/"DEPLOYMENT.diff").write_bytes("".join(line for n in sorted(modified) for line in diff(n)).encode())
    manifest=(json.dumps({n:sha(raw) for n,raw in after.items()},indent=2,sort_keys=True)+"\n").encode()
    after["SOURCE_SHA256.json"]=manifest
    archive=folder/"NUMA_M1.zip"
    with zipfile.ZipFile(archive,"x",zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for n,raw in after.items():
            info=zipfile.ZipInfo(n)
            info.compress_type=zipfile.ZIP_DEFLATED
            z.writestr(info,raw,compresslevel=9)
    with zipfile.ZipFile(archive) as z:
        assert z.namelist()==list(after) and all(z.read(n)==raw for n,raw in after.items())
    remote="/home/share/dengqingtian/opt/stage4_sessions/S00/NUMA_M1_R3_OPT_"+version
    argv=[x.replace(old["remote_root"],remote) for x in old["native_argv"]]
    argv[argv.index("-nl")+1]=" ".join([*hosts,"!cn21341"])
    argv[argv.index("-T")+1]=str(wall)
    binding=dict(version=version,mode="ffn_relu_reuse_ab",remote_root=remote,eligible_hosts=hosts,allow_preferred_queue=False,
        wall_seconds=wall,batch_deadline_utc=deadline.isoformat(),queue_seconds_remaining=limits["queue_seconds"]-queued,
        package_sha256=identity(archive)["sha256"],source_manifest_sha256=sha(manifest),descriptor_sha256=old["descriptor_sha256"],
        candidate_source_sha256=sha(after[candidate]),numeric=old["numeric"],scope=old["scope"],native_argv=argv,user_authorized=True,
        submission_ordinal=len(attempts)+1,plan=dict(strict_updates=40,baseline_updates=100,candidate_updates=100,
        max_updates=240,warmup=5,observed=20,candidate_calls_per_update=12,
        primary_metric="fractional decrease of synchronized observation window wall",
        acceptance=dict(min_percent_reduction=10,independent_pairs=3,max_repeat_spread_pct=5)),task_card=identity(CARD),
        r3_stopped_job=attempts[0],sources={
        "ffn_profile":identity(WORK/"S08"/"profile_r9_2048959_20261106"/"PROFILE_SUMMARY.md"),
        "gemm_profile":identity(WORK/"S08"/"gemm_r11_2049454_20261106"/"GEMM_SUMMARY.md"),
        "four_domain":identity(R2/"ALT_B"/"ANALYSIS.json"),
        "r2_review":identity(WORK/"COORDINATION"/"NUMA_STRAGGLER_R2_RESULT_REVIEW_20261108.json")})
    path=folder/"NUMA_RUN_BINDING.json"
    write(path,binding)
    print(remote,binding["package_sha256"],identity(path)["sha256"],binding["candidate_source_sha256"])


if __name__=="__main__":
    main(sys.argv[1],sys.argv[2:])
