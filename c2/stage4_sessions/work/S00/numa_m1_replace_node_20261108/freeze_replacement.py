"""Freeze one replacement after verifying the cancelled original's receipt."""
import ast
from datetime import datetime, timedelta, timezone
import difflib
import hashlib
import json
from pathlib import Path
import re
import sys
import zipfile

HERE = Path(__file__).resolve().parent
CONT = HERE.parent / "numa_m1_continue_affinity_20261107"
COORD = HERE.parents[1] / "COORDINATION"
CARD = COORD / "NUMA_M1_CANCEL_REPLACE_NODE_S00_20261108.md"
BUDGET = CARD.with_name(CARD.stem + "_BUDGET.json")
REMOTE = "/home/share/dengqingtian/opt/stage4_sessions/S00/NUMA_M1_R1_REPLACE_20261108"
PACKAGE = HERE / "NUMA_M1.zip"


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def identity(path):
    raw = path.read_bytes()
    return dict(path=str(path), bytes=len(raw), sha256=sha(raw))


def read(path):
    return json.loads(path.read_bytes())


def encode(value):
    return (json.dumps(value,indent=2,sort_keys=True,ensure_ascii=False)+"\n").encode()


def iso(value):
    return datetime.fromisoformat(value.replace("Z","+00:00"))


def build():
    assert identity(CARD)["sha256"] == read(BUDGET)["sha256"]
    origin = CONT/"NUMA_M1.zip"
    assert identity(origin)["sha256"] == "02e6b7efd3da8bcab5e4e427c6d219ee58c3cac11c25301f645933dd18666d67"
    with zipfile.ZipFile(origin) as z:
        before = {n:z.read(n) for n in z.namelist() if n!="SOURCE_SHA256.json"}
    after = {n:(HERE/"src"/n).read_bytes() for n in before}
    changed = {n for n in before if before[n]!=after[n]}
    assert changed == {"launch.py","submit_once.py"}
    for name in changed:
        ast.parse(after[name],filename=name,feature_version=(3,9))
        assert b"\r" not in after[name] and b' binding["host"]' not in after[name]
    assert b'context["host"] in binding["eligible_hosts"]' in after["launch.py"]
    assert b'await_handoff(ROOT, req, context, 152, 98304' in after["launch.py"]
    assert b'"strict", contracts, owner, binding, host, end' in after["launch.py"]
    assert b'"perf", contracts, owner, binding, host, end' in after["launch.py"]
    assert b'"-s","PENDING",job' in after["submit_once.py"]
    diff = [line for n in sorted(changed) for line in difflib.unified_diff(
        before[n].decode().splitlines(True),after[n].decode().splitlines(True),
        fromfile="CONT_AFF_R1/"+n,tofile="REPLACE_NODE_R1/"+n)]
    (HERE/"NODE_REBIND.diff").write_bytes("".join(diff).encode())
    after["SOURCE_SHA256.json"] = encode({n:sha(raw) for n,raw in after.items()})
    with zipfile.ZipFile(PACKAGE,"x",zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for name,raw in after.items():
            info=zipfile.ZipInfo(name)
            info.compress_type=zipfile.ZIP_DEFLATED
            z.writestr(info,raw,compresslevel=9)
    with zipfile.ZipFile(PACKAGE) as z:
        assert z.namelist() == list(after) and all(z.read(n)==raw for n,raw in after.items())
    print(identity(PACKAGE)["sha256"])


def bind(hosts):
    assert len(set(hosts))==len(hosts) and hosts and all(re.fullmatch(r"cn[0-9]+",h) and h!="cn21340" for h in hosts)
    prior = read(CONT/"NUMA_RUN_BINDING.json")
    ledger = read(CONT/"BUDGET_LEDGER.json")
    queue = read(CONT/"QUEUE_AUTHORITY_UPDATE.json")
    old_evidence = HERE/"old-2060643"
    old_bundle = old_evidence/"JOB_2060643_evidence.zip"
    receipt = read(old_evidence/"bundle_receipt.json")
    assert identity(old_bundle)["sha256"] == receipt["sha256"] and old_bundle.stat().st_size == receipt["bytes"]
    with zipfile.ZipFile(old_bundle) as z:
        terminal = json.loads(z.read("djob_final.json"))["data"]["successData"][0]
        original = json.loads(z.read("submission.command.json"))
        cancelled = json.loads(z.read("replace_node_site/cancel.stdout"))
        assert len(z.namelist()) == len(set(z.namelist())) == receipt["members"]
        assert original["binding_sha256"] == "1349dcc5e3b21e00a8d6d5e230e428cc10fcad2d3a46e0323507a5fae2b33ee4"
        assert not z.read("replace_node_site/observers_after_cancel.txt")
    assert cancelled["code"]=="success" and cancelled["data"]["successData"]==["2060643"]
    assert terminal["jobId"]=="2060643" and terminal["state"]=="FAILED" and terminal["startTime"]=="-"
    assert terminal["exitCode"]==10003 and terminal["exitMessage"]=="Job was terminated by dengqingtian"
    assert not any(g.get("nodeResUsages") for g in terminal["resGroups"]) and receipt["pids"]==[]
    assert terminal["totalResUsage"]["wallclockDurationTotal"]==0
    queue_seconds = int((iso(terminal["endTime"])-iso(terminal["createTime"])).total_seconds())
    assert queue_seconds >= 0
    settled = dict(job_id="2060643",version="CONT_AFF_R1",state=terminal["state"],
                   disposition="CANCELLED_WHILE_PENDING",native_exit_code=terminal["exitCode"],native_pids_cleared=True,
                   assigned_node=None,model_updates=0,allocated_seconds_charged=0,queue_seconds=queue_seconds,
                   created_utc=terminal["createTime"],ended_utc=terminal["endTime"],bundle=identity(old_bundle))
    assert len(ledger["attempts"])==3
    ledger["attempts"].append(settled)
    ledger["actual"].update(submissions=4,aggregate_queue_seconds=6+queue_seconds,active_job=None)
    ledger["remaining"].update(submissions=2,aggregate_allocated_seconds=5392)
    queue_cutoff = iso(queue["queue_reset_utc"])+timedelta(seconds=queue["queue_seconds_from_reset"])
    deadline = iso(ledger["deadline_utc"])
    wall = min(1800,5400-ledger["actual"]["aggregate_allocated_seconds"])
    now = datetime.now(timezone.utc)
    assert now < min(deadline-timedelta(seconds=wall+60),queue_cutoff)
    old = prior.pop("remote_root")
    prior.pop("host")
    argv = [item.replace(old,REMOTE) for item in prior["native_argv"]]
    argv[argv.index("-nl")+1]=" ".join(hosts)
    argv[argv.index("-T")+1]=str(wall)
    with zipfile.ZipFile(PACKAGE) as z:
        manifest_sha = sha(z.read("SOURCE_SHA256.json"))
    prior.update(version="REPLACE_NODE_R1",remote_root=REMOTE,eligible_hosts=hosts,wall_seconds=wall,
                 queue_cutoff_utc=queue_cutoff.isoformat(),package_sha256=identity(PACKAGE)["sha256"],
                 source_manifest_sha256=manifest_sha,native_argv=argv,observed_predecessor=settled,
                 replacement_authority=dict(card=identity(CARD),budget=identity(BUDGET),user_explicit=True,
                     cancelled_job="2060643",submission_ordinal=5,total_submissions_max=6),
                 domain_mapping=dict(status="PLANNED_RUNTIME_RESOLUTION",eligible_hosts=hosts,
                     native_allocation=152,rule="exact actual hostname from the verified native allocation, four whole 38-core distance-20 domains",
                     compute="first 36 sorted actual CPUs",reserved="last two actual CPUs"),
                 changed="Replace fixed host with vetted eligible host list and runtime native host binding; same compute payload and affinity repair.")
    output=HERE/"NUMA_RUN_BINDING.json"
    output.write_bytes(encode(prior))
    (HERE/"BUDGET_LEDGER.json").write_bytes(encode(ledger))
    print(prior["package_sha256"],identity(output)["sha256"],queue_seconds)


if __name__=="__main__":
    if sys.argv[1]=="build":
        build()
    else:
        assert sys.argv[1]=="bind"
        bind(sys.argv[2:])
