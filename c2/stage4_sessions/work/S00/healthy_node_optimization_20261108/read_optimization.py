"""Settle one healthy-node job and verify the original-vs-candidate pair."""
from pathlib import Path
from statistics import median
import sys

from freeze_optimization import ROOT, R3, identity, read, write
from read_baseline import analyze, compare_rows, jsonl

sys.path.insert(0,str(R3))
from read_r3 import native_time, unpack
sys.path.pop(0)


def actual_pair(raw,binding):
    evidence=raw/"job_evidence"
    ticks=int((raw/"login_clock_ticks.txt").read_text())
    topo=read(evidence/"domain_map.json")
    domains=topo["contracts"]
    numeric={}
    for n in domains:
        stage=evidence/"strict"/f"node{n}"
        value=read(stage/"result.json")
        numeric[n]=compare_rows(value)
        assert value["candidate_source_sha256"]==binding["candidate_source_sha256"]
        rows=jsonl(stage/"steps.jsonl")
        assert [(r["role"],r["candidate_ffn_calls"]) for r in rows]==[("baseline",0),("candidate",12)]*5
    assert sum(x["rows"] for x in numeric.values())==15580
    left,right=(analyze(raw,ticks,role) for role in ("baseline","candidate"))
    source_inputs=("frame_indices","frame_ids","mask_sha256","native_shapes")
    diff={}
    rank_maps=[read(evidence/role/"rank_map.json") for role in ("baseline","candidate")]
    assert all(rank_maps[0][k]==rank_maps[1][k] for k in ("logical_to_physical","spawn_order"))
    for n in domains:
        folders=[evidence/role/f"node{n}" for role in ("baseline","candidate")]
        lr,rr=[read(p/"result.json") for p in folders]
        assert lr["pid"]!=rr["pid"]
        assert lr["runtime"]["libraries_after"]==rr["runtime"]["libraries_after"]
        assert lr["candidate_source_sha256"]==rr["candidate_source_sha256"]==binding["candidate_source_sha256"]
        a,b=[jsonl(p/"steps.jsonl") for p in folders]
        assert len(a)==len(b)==25
        for u,v in zip(a,b):
            assert u["role"]=="baseline" and v["role"]=="candidate"
            assert u["candidate_ffn_calls"]==0 and v["candidate_ffn_calls"]==12
            assert all(u[k]==v[k] for k in source_inputs)
        dl,dr=left["domains"][n],right["domains"][n]
        diff[n]=dict(
            median_reduction_pct=100*(1-dr["sampled_seconds"]["median"]/dl["sampled_seconds"]["median"]),
            summed_pure_step_reduction_pct=100*(1-dr["sampled_seconds"]["total"]/dl["sampled_seconds"]["total"]),
            sampled_hwm_delta_MiB=dr["sample_hwm_MiB"]-dl["sample_hwm_MiB"],
            final_model_sha_equal=lr["final_model_sha256"]==rr["final_model_sha256"],
            candidate_dispatches=sum(x["candidate_ffn_calls"] for x in b))
        for series,role in ((a,dl),(b,dr)):
            observed=series[5:]
            native_seconds=[sum(row["native_sgemm_ns_by_shape"].values())/1e9 for row in observed]
            assert all(0<k<=row["step_seconds"] for k,row in zip(native_seconds,observed))
            role["median_native_seconds"]=median(native_seconds)
            role["median_non_native_seconds"]=median(row["step_seconds"]-k for row,k in zip(observed,native_seconds))
    span0,span1=left["common_window_seconds"],right["common_window_seconds"]
    return dict(baseline=left,candidate=right,strict_gate=numeric,per_domain=diff,rank_maps=rank_maps,
        synchronized_window_time_reduction_pct=100*(1-span1/span0),
        synchronized_throughput_gain_pct=100*(span0/span1-1))


def main(folder,job,transfer_sha):
    raw,receipt=unpack(folder,job,transfer_sha)
    binding=read(folder/"NUMA_RUN_BINDING.json")
    row,=read(raw/"djob_final.json")["data"]["successData"]
    assert row["jobId"]==job and row["state"]==receipt["state"] and row["state"] in {"FAILED","SUCCEEDED","CANCELLED"}
    evidence=raw/"job_evidence"
    native_nodes=[n for g in row["resGroups"] for n in g.get("nodeResUsages") or []]
    result=dict(version=binding["version"],job_id=job,native_state=row["state"])
    if row["startTime"]=="-":
        cleanup=raw/"UNALLOCATED_CLEANUP.json"
        assert not native_nodes and not receipt["pids"] and read(cleanup)["job_id"]==job
        qend=native_time(row["endTime"])
        allocated=updates=0
        result["status"]="NOT_ALLOCATED"
    else:
        node,=native_nodes
        assert node["execNode"] in binding["eligible_hosts"] and node["execNode"]!="cn21341"
        assert receipt["pids"]==[node["pids"]]==["-"]
        cleanup=evidence/"cleanup.json"
        clean=read(cleanup)
        assert clean["all_reaped"] and not clean["remaining_live"] and not clean["remaining_processes"]
        app=read(evidence/"SUMMARY.json")
        assert app["job_id"]==job
        qend=native_time(row["startTime"])
        allocated=max(node["wallclockDuration"],int((native_time(row["endTime"])-qend).total_seconds()))
        updates=sum(len(p.read_bytes().splitlines()) for p in evidence.glob("*/node*/steps.jsonl"))
        result.update(status=app["status"],host=node["execNode"],application=app,scheduler_peak_MB=node["memMax"],
                      scheduler_swap_peak_MB=node["swapMax"])
        result["worker_failures"]={str(p.relative_to(evidence)):v["error"] for p in evidence.glob("*/node*/result.json")
                                   for v in [read(p)] if "error" in v}
        if app["status"]=="PASS_SAME_HOST_FFN_RELU_AB":
            assert row["state"]=="SUCCEEDED" and updates==240
            before,after=[read(raw/f"FIXED_INPUTS_{x}.json") for x in ("BEFORE","AFTER")]
            assert before["status"]==after["status"]=="FIXED16_CURRENT_SOURCE_SHA_PASS" and before["checked"]==after["checked"]
            result["pair"]=actual_pair(raw,binding)
    queued=int((qend-native_time(row["createTime"])).total_seconds())
    ledger_path=ROOT/"BUDGET_LEDGER.json"
    ledger=read(ledger_path)
    assert binding["submission_ordinal"]==len(ledger["attempts"])+1 and queued>=0 and updates<=240
    item=dict(job_id=job,version=binding["version"],host=result.get("host"),native_state=row["state"],exit_code=row.get("exitCode"),
        terminal_confirmed=True,cleanup_confirmed=True,queue_seconds=queued,allocated_seconds=allocated,
        microprobe_seconds=0,confirmed_updates=updates,model_updates_upper_bound=updates if not allocated or row["state"]=="SUCCEEDED" else 240,
        package=identity(folder/"NUMA_M1.zip"),binding=identity(folder/"NUMA_RUN_BINDING.json"),
        native=identity(raw/"djob_final.json"),cleanup=identity(cleanup),transfer=identity(folder/f"JOB_{job}_TRANSFER.tgz"))
    ledger["attempts"].append(item)
    write(folder/"ANALYSIS.json",result)
    write(ledger_path,ledger)
    print(job,result["status"],result.get("host"),queued,allocated,updates)
    if "pair" in result:
        print(result["pair"]["synchronized_window_time_reduction_pct"],result["pair"]["per_domain"])


if __name__=="__main__":
    main(Path(sys.argv[1]).resolve(),sys.argv[2],sys.argv[3])
