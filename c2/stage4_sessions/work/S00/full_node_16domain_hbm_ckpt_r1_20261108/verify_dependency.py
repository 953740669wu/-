"""Pin the returned 09 joint workload and the accepted 16-electrode control."""
from datetime import datetime, timedelta
import hashlib
import json
import math
from pathlib import Path
import re
import zipfile

HERE = Path(__file__).resolve().parent
WORK = HERE.parents[1]
M23 = WORK/"M23_MEMORY_HBM"
S09 = M23/"memory_hbm_32e_r1_20261108"
R32 = S09/"S09_R7_20261108T053223Z"
R16_ROOT = M23/"ubsan_hbm_continue_20261108"
R16 = R16_ROOT/"HBM_R5_20261107T174349Z"
COORD = WORK/"COORDINATION"
FINAL_SHA = "55495a3f3dcc269370be8903e160ef35afddd092bd0b9eda78b00694c8cbb76d"
LIBRARY_SHA = "89f295754a199dcb6206f8e6217e6cf57651bceed2d364b1a6e4cc83eea6095d"
ALLOCATOR_SHA = "d1f5dbbfb6aa4a973dcc4d12607f62a8b2be5166690897dfd5ea35e067c7d7a2"
COMPARE_SHA = "e9b53136146c062b0817fd0bf63632ad6c8cde6daa8d862cf78ba10431024a3e"
KML_SHA = "e6c5c4411c453c8168939cd51d737a7e9d8232bdfff05da3967805a5e917ff26"


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def identity(path):
    raw = path.read_bytes()
    return dict(path=str(path),sha256=sha(raw),bytes=len(raw))


def read(path):
    return json.loads(path.read_bytes())


def save(path,value):
    tmp = path.with_suffix(".tmp")
    tmp.write_bytes((json.dumps(value,indent=2,ensure_ascii=False,sort_keys=True)+"\n").encode())
    tmp.replace(path)


def archive(run):
    receipt=read(run/"bundle_receipt.json")
    path=run/receipt["file"]
    ref=identity(path)
    assert ref["bytes"]==receipt["bytes"] and ref["sha256"]==receipt["sha256"]
    raw=run/"received"
    with zipfile.ZipFile(path) as z:
        index=json.loads(z.read("COLLECTION.json"))
        assert len(z.namelist())==len(index)+1==receipt["files"]+1
        assert set(z.namelist())==set(index)|{"COLLECTION.json"}
        for name,row in index.items():
            assert ".." not in Path(name).parts and not Path(name).is_absolute()
            data=z.read(name)
            assert sha(data)==row["sha256"] and len(data)==row["bytes"] and (raw/name).read_bytes()==data
    return raw,ref


def check_metrics(metrics):
    assert metrics
    for r in metrics:
        limit=2e-6 if ".state." in r["name"] else 2e-5
        a,l2,n=(r[k] for k in ("max_abs","l2_relative","reference_norm"))
        assert r["passed"] is True and all(math.isfinite(x) and x>=0 for x in (a,l2,n))
        assert a<=limit and (n<=1e-8 or l2<=2e-6)
    return dict(rows=len(metrics),max_abs=max(r["max_abs"] for r in metrics),
                max_rel_L2=max(r["l2_relative"] for r in metrics))


def verified_run(run, job, variant, electrodes):
    raw,bundle=archive(run)
    native,=read(raw/"djob_final.json")["data"]["successData"]
    group,=native["resGroups"]
    node,=group["nodeResUsages"]
    assert native["jobId"]==job and native["state"]=="SUCCEEDED" and native["jobExitCode"]==0 and node["pids"]=="-"
    bound=read(raw/"M23_RUN_BINDING.json")
    assert bound["domain_count"]==4 and native["execPath"]==bound["remote_root"]
    assert bound["candidate_sha256"]==ALLOCATOR_SHA
    evidence=raw/"job_evidence"
    app=read(evidence/"SUMMARY.json")
    cleanup=read(evidence/"cleanup.json")
    assert app["status"]=="PASS_HBM_AB" and app["hbm_safety"]=="PASS" and app["hbm_pool_restored"] is True
    assert cleanup["all_reaped"] and not cleanup["remaining_live"] and not cleanup["remaining_processes"]
    topology=read(evidence/"domain_map.json")
    assert len(topology["contracts"])==4 and topology["context"]["host"]==node["execNode"]
    for file,expected in (("payload/tests/check_equivalence.py",COMPARE_SHA),("payload/baseline/kml_ops.py",KML_SHA),
                          ("ENGINEERING_DESCRIPTOR.json",bound["descriptor_sha256"]),("M23_PAYLOAD.zip",bound["package_sha256"]),
                          ("SOURCE_SHA256.json",bound["source_manifest_sha256"])):
        assert identity(raw/file)["sha256"]==expected
    for file,expected in read(raw/"SOURCE_SHA256.json").items():
        assert identity(raw/file)["sha256"]==expected
    caps,checks={},{}
    for n,contract in topology["contracts"].items():
        placement=read(evidence/f"real_hbm_node{n}/RECEIPT.json")
        assert placement["status"]=="PASS_REAL_HBM_SAFETY" and placement["library_sha256"]==LIBRARY_SHA
        assert placement["pool_pages_after"]==placement["pool_pages_before"]
        cap=placement["cap_MiB"]
        assert 0<cap<=3800 and (placement["pool_pages_before"]-16)*2>=cap
        strict=evidence/f"strict_{variant}"/f"node{n}"
        perf=evidence/f"perf_{variant}"/f"node{n}"
        for folder,status,steps in ((strict,"PASS_STRICT_ENCODER5",5),(perf,"PASS_PERF25",25)):
            out=read(folder/"result.json")
            allocator=out["hbm_allocator"]
            assert out["status"]==status and out["completed_updates"]==steps and out["job_id"]==job
            assert out["host"]==node["execNode"] and allocator["sha256"]==LIBRARY_SHA
            assert allocator["node"]==placement["hbm_node"] and allocator["cap_MiB"]==cap
            assert out["cpu36"]["errors"]==[] and out["cpu36"]["receipt"]["selected"]==contract["selected"]
            rows=[json.loads(line) for line in (folder/"steps.jsonl").read_bytes().splitlines()]
            assert len(rows)==steps and all(0<r["rss_after"]["hugetlb_bytes"]<=cap*2**20 for r in rows)
            if electrodes==32:
                assert out["checkpoint_layers"]==12 and all(r["batch_size"]==32 for r in rows)
            if folder==strict:
                checks[n]=check_metrics(out["metrics"])
        maps=(perf/"observe_start.numa_maps").read_text()
        assert re.search(rf"\bbind:{placement['hbm_node']}\b[^\n]+\bhuge\b[^\n]+\bN{placement['hbm_node']}=[1-9]\d*",maps)
        caps[n]=cap
    return dict(job_id=job,host=node["execNode"],domains=4,strict=checks,per_domain_cap_MiB=caps,
                bundle=bundle,payload=identity(raw/"M23_PAYLOAD.zip"),descriptor=identity(raw/"ENGINEERING_DESCRIPTOR.json"),
                binding=identity(raw/"M23_RUN_BINDING.json"),allocator_origin=bound.get("allocator_origin"),
                cleanup=identity(evidence/"cleanup.json"),native=identity(raw/"djob_final.json"))


def main():
    final=identity(S09/"MEMORY_HBM_32E_RESULT.json")
    review_path=COORD/"S09_32E_RESULT_REVIEW_20261108.json"
    review=read(review_path)
    assert final["sha256"]==review["delivery_sha256"]==FINAL_SHA
    assert review["status"]=="ACCEPT_BASELINE_AND_MEMORY_CANDIDATE_WITH_STABILITY_FAIL"
    handoff=identity(COORD/"S09_TO_S00_16DOMAIN_DEPENDENCY_ACCEPTED_20261108.md")
    assert read(S09/"ACTIVE_JOB.json")["active_job"] is None
    v32=verified_run(R32,"2063805","ckpt_hbm",32)
    v16=verified_run(R16,"2061475","candidate",16)
    raw32=R32/"received"
    source=identity(raw32/"payload"/"checkpoint_layers.py")
    assert source["sha256"]=="a55b48fd710fea13b11f9058e2ca568c00f9e6d4e88e7e0f71118f6c7beb2576"
    assert v32["payload"]["sha256"]=="eea37182d930e6947673ada27b435fb7ed8b6b90004cd0571affeac2096fd784"
    pair=raw32/"PRIOR_PAIRING.json"
    assert identity(pair)["sha256"]==read(raw32/"M23_RUN_BINDING.json")["prior_pairing_sha256"]
    contract=read(pair)
    assert (contract["batch_size"],contract["electrodes"],contract["tokens"])==(32,32,928)
    assert sorted(contract["order"])==list(range(800)) and len(contract["mask_sha256"])==25
    review16=read(COORD/"NUMA_HBM_RESULTS_REVIEW_20261108.json")
    parent16=identity(R16_ROOT/"HBM_CONTINUE_RESULT.json")
    assert review16["source_results"][parent16["path"]]==parent16["sha256"] and not review16["errors"]
    v32.update(pairing=identity(pair),checkpoint_source=source)
    v16["accepted_parent"]=parent16
    path=HERE/"DEPENDENCY_RECEIPT.json"
    assert not path.exists()
    start="2026-11-08T06:20:01Z"
    ledger=read(HERE/"BUDGET_LEDGER.json")
    assert ledger["execution_started_utc"] is None
    ts=lambda s:datetime.fromisoformat(s.replace("Z","+00:00"))
    assert ts(start)<=ts(ledger["dependency_deadline_utc"])
    end=min(ts(ledger["absolute_deadline_utc"]),ts(start)+timedelta(seconds=ledger["limits"]["execution_wall_seconds"]))
    save(path,dict(status="DEPENDENCY_ACCEPTED_FOR_FULL_NODE_VALIDATION",received_utc=start,
         handoff=handoff,final_09=final,independent_review=identity(review_path),real32=v32,real16=v16,
         allocator_sha256=LIBRARY_SHA,allocator_source_sha256=ALLOCATOR_SHA,strict_comparator_sha256=COMPARE_SHA,
         ckpt12_stability=dict(spread_pct=5.4363842683,gate_pct=5,stable_speed_adopted=False),
         full_node_safety_or_speed_preaccepted=False))
    ledger.update(execution_started_utc=start,execution_deadline_utc=end.isoformat(),
                  status="DEPENDENCY_ACCEPTED",dependency=identity(path))
    save(HERE/"BUDGET_LEDGER.json",ledger)
    print(start,end.isoformat(),v32["per_domain_cap_MiB"],v16["per_domain_cap_MiB"])


if __name__=="__main__":
    main()
