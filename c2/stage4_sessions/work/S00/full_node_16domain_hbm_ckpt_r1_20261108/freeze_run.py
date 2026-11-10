"""Create one immutable full-node payload and budget-bound native command."""
import ast
from datetime import datetime, timedelta, timezone
import difflib
from pathlib import Path
import re
import sys
import zipfile

from adapt_workers import adapt_batch, adapt_worker
from verify_dependency import HERE, COMPARE_SHA, KML_SHA, R16, R32, identity, read, save, sha


def freeze(version, workload, first, rounds, ddr, hosts, excludes):
    assert re.fullmatch(r"[A-Z0-9_]+",version)
    assert workload in {"32B32","32B64","16B64"}
    assert 1<=first<=3 and 1<=rounds<=4-first and (not ddr or workload.startswith("32") and first==1)
    assert "cn21341" in excludes and hosts and not set(hosts)&set(excludes)
    assert all(re.fullmatch(r"cn[0-9]+",h) for h in hosts+excludes)
    ledger=read(HERE/"BUDGET_LEDGER.json")
    receipt_path=HERE/"DEPENDENCY_RECEIPT.json"
    assert identity(receipt_path)==ledger["dependency"]
    dep=read(receipt_path)
    limit=ledger["limits"]
    attempts=ledger["attempts"]
    assert len(attempts)<limit["submissions"] and all(a["terminal"] and a["cleanup"] for a in attempts)
    hosts_used={a["host"] for a in attempts if a.get("host")}
    assert len(hosts_used)<limit["physical_hosts"] or set(hosts)<=hosts_used
    if len(hosts_used)==1 and set(hosts)-hosts_used:
        assert not set(hosts)&hosts_used
    queued=limit["queue_seconds"]-ledger["queue_seconds"]
    deadline=datetime.fromisoformat(ledger["execution_deadline_utc"])
    room=int((deadline-datetime.now(timezone.utc)).total_seconds())
    wall=min(limit["job_seconds"],limit["allocated_seconds"]-ledger["allocation_seconds"],room-120)
    max_updates=16*(10+25*(rounds+int(ddr)))
    assert queued>0 and wall>=600 and max_updates<=limit["model_updates_per_job"]
    assert ledger["model_updates"]+max_updates<=limit["model_updates"]
    e,b=(int(x) for x in workload.split("B"))
    reference=dep[f"real{e}"]
    path=Path(reference["payload"]["path"])
    assert identity(path)==reference["payload"]
    with zipfile.ZipFile(path) as z:
        before={name:z.read(name) for name in z.namelist() if name!="SOURCE_SHA256.json"}
    assert sha(before["payload/tests/check_equivalence.py"])==COMPARE_SHA
    assert sha(before["payload/baseline/kml_ops.py"])==KML_SHA
    after=dict(before)
    for f in sorted((HERE/"overrides").glob("*.py")):
        after[f.name]=f.read_bytes()
    if e==32:
        for name in ("inspect_metadata.py","recheck_fixed_inputs.py"):
            original=after[name]
            assert original.count(b"M23_RUN_BINDING.json")==1
            after[name]=original.replace(b"M23_RUN_BINDING.json",b"RUN_BINDING.json")
    after["topology16.py"]=(HERE/"topology16.py").read_bytes()
    after["payload/worker.py"]=adapt_worker(before["payload/worker.py"],e)
    if e==32:
        assert sha(before["payload/checkpoint_layers.py"])==reference["checkpoint_source"]["sha256"]
        after["payload/engineering_training.py"]=adapt_batch(before["payload/engineering_training.py"])
    for n,v in after.items():
        if n.endswith((".py",".sh")):
            assert b"\r" not in v,n
        if n.endswith(".py"):
            ast.parse(v,filename=n,feature_version=(3,9))
    local=HERE/version
    local.mkdir()
    sidecars={}
    for file,key in (("ENGINEERING_DESCRIPTOR.json","descriptor"),("PRIOR_PAIRING.json","pairing")):
        if key not in reference:
            continue
        src=Path(reference[key]["path"])
        assert identity(src)==reference[key]
        raw=src.read_bytes()
        if file in before:
            assert raw==before[file]
        (local/file).write_bytes(raw)
        sidecars[file]=sha(raw)
    (local/"DEPENDENCY_RECEIPT.json").write_bytes(receipt_path.read_bytes())
    sidecars["DEPENDENCY_RECEIPT.json"]=sha(receipt_path.read_bytes())
    if e==32 and b==64:
        prior=read(local/"PRIOR_PAIRING.json")
        save(local/"B64_SAMPLE_PLAN.json",dict(source_800=reference["descriptor"],descriptor_sha256=reference["descriptor"]["sha256"],
             order=prior["order"]*2,batch_size=64,steps=25,unique_frames=800,frame_visits=1600,
             seed=0,initial_weights_sha256=prior["initial_weights_sha256"],mask_shape=[64,928],
             mask_recipe="original Torch RNG after seed0 Encoder initialization; 25 draws <0.5; freeze all hashes before first DDR update"))
        sidecars["B64_SAMPLE_PLAN.json"]=identity(local/"B64_SAMPLE_PLAN.json")["sha256"]
    manifest={n:sha(v) for n,v in after.items()}
    save(local/"SOURCE_SHA256.json",manifest)
    after["SOURCE_SHA256.json"]=(local/"SOURCE_SHA256.json").read_bytes()
    package=local/"FULL16_PAYLOAD.zip"
    with zipfile.ZipFile(package,"x",zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for n,v in sorted(after.items()):
            i=zipfile.ZipInfo(n)
            i.compress_type=zipfile.ZIP_DEFLATED
            z.writestr(i,v,compresslevel=9)
    with zipfile.ZipFile(package) as z:
        assert set(z.namelist())==set(after) and all(z.read(n)==v for n,v in after.items())
    changes=[n for n,v in after.items() if n!="SOURCE_SHA256.json" and before.get(n)!=v]
    diff=(s for n in changes for s in difflib.unified_diff(before.get(n,b"").decode().splitlines(True),
        after[n].decode().splitlines(True),fromfile=f"accepted{e}/"+n,tofile=version+"/"+n))
    (local/"MINIMAL.diff").write_bytes("".join(diff).encode())
    remote="/home/share/dengqingtian/opt/stage4_sessions/S00/FULL16_R1_"+version
    argv=["dsub","-J","-q","q_hpcai","-x","job","-nl"," ".join(hosts+["!"+h for h in excludes]),
          "-R","cpu=608,mem=393216MB","-RL","mem=393216MB","-a","numa[count=16,distribution=pack]",
          "-T",str(wall),"--env","none","--cwd",remote,"-oo",remote+"/job.log","bash",remote+"/run_job.sh","BINDING_SHA256"]
    pin=local/"RUN_BINDING.json"
    save(pin,dict(version=version,workload=workload,electrodes=e,batch_size=b,checkpoint_layers=12 if e==32 else 0,
         mode="full_node_hbm_ckpt",domain_count=16,remote_root=remote,eligible_hosts=hosts,excluded_hosts=excludes,
         native_argv=argv,user_authorized=True,wall_seconds=wall,batch_deadline_utc=deadline.isoformat(),
         remaining_queue_seconds=queued,submission_ordinal=len(attempts)+1,max_model_updates=max_updates,
         hbm_rounds_max=rounds,first_hbm_round=first,ddr_perf_control=ddr,strict_storage_min_bytes=88*2**30,
         fixed_input_status=f"FIXED{e}_CURRENT_SOURCE_SHA_PASS",allocator_origin=dep["real32"]["allocator_origin"],
         allocator_sha256=dep["allocator_sha256"],candidate_sha256=dep["allocator_source_sha256"],
         existing_16e_validation_reference=dep["real16"]["accepted_parent"],hbm_cap_MiB=3800,
         package_sha256=identity(package)["sha256"],source_manifest_sha256=identity(local/"SOURCE_SHA256.json")["sha256"],
         descriptor_sha256=reference["descriptor"]["sha256"],frozen_sidecars=sidecars,dependency=identity(receipt_path),
         allocation_contract=ledger["resources"],numerical=dict(tensor_abs=2e-5,state_abs=2e-6,relative_L2=2e-6,
         near_zero_norm=1e-8,denominator_floor=1e-12,strict_steps=5),stability=dict(rounds=3,spread_pct=5)))
    print(remote,identity(pin)["sha256"],identity(package)["sha256"],wall)


if __name__=="__main__":
    version,workload,first,rounds,ddr,hosts,excluded=sys.argv[1:]
    freeze(version,workload,int(first),int(rounds),bool(int(ddr)),hosts.split(","),excluded.split(","))
