"""Verify and settle one returned full-node job without reloading model tensors."""
from datetime import datetime
import json
from pathlib import Path, PurePosixPath
import re
from statistics import median
import sys
import tarfile
import zipfile

from verify_dependency import HERE, LIBRARY_SHA, check_metrics, identity, read, save, sha


def unpack(folder, job, digest):
    path=folder/f"JOB_{job}_TRANSFER.tgz"
    assert identity(path)["sha256"]==digest
    bundle=folder/f"JOB_{job}_evidence.zip"
    with tarfile.open(path) as tar:
        assert set(tar.getnames())=={bundle.name,"bundle_receipt.json"}
        for name in (bundle.name,"bundle_receipt.json"):
            member=tar.getmember(name)
            assert member.isfile()
            (folder/name).write_bytes(tar.extractfile(member).read())
    receipt=read(folder/"bundle_receipt.json")
    assert receipt["job_id"]==job and identity(bundle)["sha256"]==receipt["sha256"]
    assert bundle.stat().st_size==receipt["bytes"]
    target=folder/"received"
    already_extracted=target.exists()
    with zipfile.ZipFile(bundle) as z:
        names=z.namelist()
        assert len(set(names))==len(names)==receipt["members"]
        assert all(not PurePosixPath(n).is_absolute() and ".." not in PurePosixPath(n).parts
                   and chr(92) not in n and ":" not in n for n in names)
        index=json.loads(z.read("COLLECTION_INDEX.json"))
        assert set(names)=={n for n,r in index["files"].items() if r["archive"]}|{"COLLECTION_INDEX.json"}
        for n in names:
            if n!="COLLECTION_INDEX.json":
                row=index["files"][n]
                raw=z.read(n)
                assert len(raw)==row["bytes"] and sha(raw)==row["sha256"],n
            if already_extracted:
                assert (target/n).read_bytes()==z.read(n),n
        if not already_extracted:
            z.extractall(target)
    return target,receipt


def native_time(s):
    if "/" in s:
        return datetime.strptime(s,"%Y/%m/%d %H:%M:%S")
    return datetime.fromisoformat(s.replace("Z","+00:00"))


def rows(path):
    return [json.loads(line) for line in path.read_bytes().splitlines()]


def resident_hbm(path,target):
    resident=0
    for line in path.read_text().splitlines():
        fields=line.split()
        if "huge" not in fields:
            continue
        assert "kernelpagesize_kB=2048" in fields and f"bind:{target}" in fields
        numa={int(n):int(x) for n,x in re.findall(r"\bN(\d+)=(\d+)\b",line)}
        assert not set(numa)-{target}
        resident+=numa.get(target,0)*2
    return resident


def allocator_stats(path):
    matches=re.findall(r"hbm allocs (\d+) \(([0-9.]+) GB, (\d+) reused\), ddr large allocs (\d+) "
                       r"\(([0-9.]+) GB\), arena high-water ([0-9.]+) GB",path.read_text())
    row,=matches
    a,h,r,d,x,w=row
    return dict(hbm_allocations=int(a),hbm_requested_reported_GB=float(h),reused=int(r),
                ddr_large_fallback_allocations=int(d),ddr_large_requested_reported_GB=float(x),
                arena_high_water_reported_GB=float(w))


def phase(raw,name,topo,bound):
    stage=raw/"job_evidence"/name
    published=read(stage/"phase_receipt.json")
    full_count=len(topo["contracts"])
    assert full_count==len(published["domains"])==16
    strict=name.startswith("strict")
    hbm="candidate" in name
    steps=5 if strict else 25
    expected="PASS_STRICT_ENCODER5" if strict and hbm else "PASS_STRICT_REFERENCE5" if strict else "PASS_PERF25"
    assert published["status"]==expected
    per_domain,aligned={},[]
    for n,c in topo["contracts"].items():
        home=stage/f"node{n}"
        value=read(home/"result.json")
        assert value["job_id"]==topo["context"]["job_id"] and value["host"]==topo["context"]["host"]
        assert value["completed_updates"]==steps and value["status"]==expected
        assert value["cpu36"]["errors"]==[] and value["cpu36"]["receipt"]==c
        for check in value["cpu36"]["checkpoints"]:
            assert check["snapshot"]["complete"]
            assert all(t["affinity"] and set(t["affinity"])<=set(c["selected"]) for t in check["snapshot"]["threads"])
            if "torch_intraop" in check:
                assert check["torch_intraop"]==36
        updates=rows(home/"steps.jsonl")
        assert [r["step"] for r in updates]==list(range(1,steps+1))
        assert all(r["batch_size"]==bound["batch_size"] and r["release_ns"] is not None
                   and r["native_sgemm_calls"]>0 and r["native_shapes"] for r in updates)
        exposure=read(home/"EXPOSURE_LEDGER.json")
        assert exposure["in_flight"] is None and len(exposure["confirmed_updates"])==steps
        d=dict(model_sha=value["final_model_sha256"],pid=value["pid"],
               exposure_unique_frames=len({i for r in updates for i in r["frame_indices"]}),
               kml_call_counts=sorted({r["native_sgemm_calls"] for r in updates}),measurements={})
        alloc=value["hbm_allocator"]
        if hbm:
            assert alloc["sha256"]==LIBRARY_SHA and alloc["node"]==topo["hbm_pairs"][n] and alloc["cap_MiB"]==bound["hbm_cap_MiB"]
            assert all(0<r["rss_after"]["hugetlb_bytes"]<=alloc["cap_MiB"]*2**20 for r in updates)
            d["allocator_stats"]=allocator_stats(stage/f"node{n}.log")
        else:
            assert alloc is None and all(r["rss_after"]["hugetlb_bytes"]==0 for r in updates)
        if bound["electrodes"]==32:
            assert value["checkpoint_layers"]==bound["checkpoint_layers"]
        if strict and hbm:
            d["strict_gate"]=check_metrics(value["metrics"])
        if not strict:
            obs=updates[5:]
            mib=2**20
            hbm_mib=[r["rss_after"]["hugetlb_bytes"]/mib for r in obs]
            peak_rss=[r["rss_after"]["peak_rss_bytes"]/mib for r in obs]
            wall=[r["step_seconds"] for r in obs]
            d["measurements"]=dict(step_seconds=wall,median_seconds=median(wall),sum_seconds=sum(wall),
                visits_per_second=20*bound["batch_size"]/sum(wall),ordinary_rss_peak_MiB=max(peak_rss),
                hbm_step_end_max_MiB=max(hbm_mib),rss_peak_plus_step_end_hbm_estimate_MiB=max(a+b for a,b in zip(peak_rss,hbm_mib)),
                step_end_rss_plus_hbm_MiB=[r["rss_after"]["rss_bytes"]/mib+x for r,x in zip(obs,hbm_mib)])
            if hbm:
                a=resident_hbm(home/"observe_start.numa_maps",alloc["node"])
                z=resident_hbm(home/"observe_end.numa_maps",alloc["node"])
                assert 0<a<=alloc["cap_MiB"] and 0<z<=alloc["cap_MiB"]
                d["measurements"].update(observe_start_hbm_MiB=a,observe_end_hbm_MiB=z)
        aligned.append(updates)
        per_domain[n]=d
    for group in zip(*aligned):
        one=group[0]
        assert all(all(r[k]==one[k] for k in ("frame_indices","frame_ids","mask_sha256","release_ns","native_shapes")) for r in group)
    answer=dict(status=expected,domains=per_domain,domain_count=16)
    if not strict:
        obs=[r[5:] for r in aligned]
        step_spans=[(max(r["end_ns"] for r in g)-min(r["start_ns"] for r in g))/1e9 for g in zip(*obs)]
        whole=(max(x[-1]["end_ns"] for x in obs)-min(x[0]["start_ns"] for x in obs))/1e9
        data={n:d["measurements"] for n,d in per_domain.items()}
        worst=max(data,key=lambda n:data[n]["sum_seconds"])
        totals=[sum(d["step_end_rss_plus_hbm_MiB"][i] for d in data.values()) for i in range(20)]
        answer.update(median_synchronized_step_seconds=median(step_spans),step_spans_seconds=step_spans,
            synchronized_window_seconds=whole,synchronized_window_visits_per_second=16*20*bound["batch_size"]/whole,
            sum_independent_rates=sum(x["visits_per_second"] for x in data.values()),
            slowest_domain=worst,slowest_rate_reference_x16=16*data[worst]["visits_per_second"],
            slowest_pure_total_vs_median_pct=100*(data[worst]["sum_seconds"]/median(x["sum_seconds"] for x in data.values())-1),
            max_sum_of_step_end_samples_MiB=max(totals),step_end_samples_sum_MiB=totals,
            sum_per_domain_peak_estimates_MiB=sum(x["rss_peak_plus_step_end_hbm_estimate_MiB"] for x in data.values()))
    return answer


def main(folder,job,digest):
    raw,receipt=unpack(folder,job,digest)
    binding=read(folder/"RUN_BINDING.json")
    native,=read(raw/"djob_final.json")["data"]["successData"]
    assert native["jobId"]==job and native["state"]==receipt["state"] and native["execPath"]==binding["remote_root"]
    assert native["state"] in {"SUCCEEDED","FAILED","CANCELLED"}
    nodes=[n for g in native["resGroups"] for n in g.get("nodeResUsages") or []]
    evidence=raw/"job_evidence"
    report=dict(job_id=job,workload=binding["workload"],version=binding["version"],scheduler_state=native["state"],phases={})
    if native["startTime"]=="-":
        cleanup=raw/"UNALLOCATED_CLEANUP.json"
        assert not nodes and not receipt["pids"] and read(cleanup)["job_id"]==job
        allocated=updates=0
        qend=native_time(native["endTime"])
        report["status"]="NOT_ALLOCATED"
    else:
        n,=nodes
        assert n["execNode"] in binding["eligible_hosts"] and receipt["pids"]==[n["pids"]]==["-"]
        assert native["exclusive"] is True and native["jobWallClockLimit"]==binding["wall_seconds"]
        g,=native["resGroups"]
        assert g["resReq"]["cpu"]==g["resAlloc"]["cpu"]==608 and g["resReq"]["mem"]==g["resAlloc"]["mem"]==g["resLimit"]["mem"]==393216
        qend=native_time(native["startTime"])
        allocated=max(n["wallclockDuration"],int((native_time(native["endTime"])-qend).total_seconds()))
        cleanup=evidence/"cleanup.json"
        clean=read(cleanup)
        assert clean["all_reaped"] and not clean["remaining_live"] and not clean["remaining_processes"]
        app=read(evidence/"SUMMARY.json")
        assert app["job_id"]==job
        updates=sum(len(p.read_bytes().splitlines()) for p in evidence.glob("*/node*/steps.jsonl"))
        report.update(host=n["execNode"],status=app["status"],application=app,native_peak_MiB=n.get("memMax"),native_swap_peak_MiB=n.get("swapMax"))
        if (evidence/"domain_map.json").is_file():
            topo=read(evidence/"domain_map.json")
            for p in sorted(evidence.glob("*/phase_receipt.json")):
                report["phases"][p.parent.name]=phase(raw,p.parent.name,topo,binding)
            report["topology"]=identity(evidence/"domain_map.json")
        report["worker_exit_codes"]={p.parent.name:read(p) for p in sorted(evidence.glob("*/exit_codes.json"))}
        probe_codes=[read(p)["exit_code"] for p in evidence.glob("real_hbm_node*/real_probe.exit.json")]
        report["SIGBUS_detected"]=-7 in probe_codes or any(-7 in d.values() for d in report["worker_exit_codes"].values())
        report["SIGKILL_detected"]=any(-9 in d.values() for d in report["worker_exit_codes"].values())
        fail_text=" ".join(str(v) for v in (native.get("exitMessage"),app.get("error"),app.get("cleanup_error")))
        report["OOM_explicit"]=bool(re.search(r"out of memory|\bOOM\b",fail_text,re.IGNORECASE))
        if app["status"]=="PASS_FULL_NODE_COMPLETED_PHASES":
            assert native["state"]=="SUCCEEDED" and app["hbm_safety"]=="PASS" and app["hbm_pool_restored"]
            assert all(read(p)["passed"] for p in evidence.glob("pool_return_*.json"))
            expected=16*(10+25*(len(app["completed_hbm_rounds"])+int(binding["ddr_perf_control"])))
            assert updates==expected and len(app["completed_hbm_rounds"])>=1
    before,after=[read(raw/f"FIXED_INPUTS_{x}.json") for x in ("BEFORE","AFTER")]
    assert before["status"]==after["status"]==binding["fixed_input_status"]
    if binding["electrodes"]==32:
        assert before==after
    else:
        assert before["checked"]==after["checked"]
    queued=int((qend-native_time(native["createTime"])).total_seconds())
    charge_updates=updates if native["state"]=="SUCCEEDED" or not allocated else binding["max_model_updates"]
    assert 0<=updates<=charge_updates<=binding["max_model_updates"] and queued>=0
    ledger_path=HERE/"BUDGET_LEDGER.json"
    ledger=read(ledger_path)
    assert binding["submission_ordinal"]==len(ledger["attempts"])+1
    item=dict(job_id=job,host=report.get("host"),version=binding["version"],workload=binding["workload"],
        queue_seconds=queued,allocated_seconds=allocated,confirmed_updates=updates,charged_updates=charge_updates,
        terminal=True,cleanup=True,state=native["state"],artifact=identity(folder/f"JOB_{job}_TRANSFER.tgz"),
        binding=identity(folder/"RUN_BINDING.json"),cleanup_source=identity(cleanup),native=identity(raw/"djob_final.json"))
    ledger["attempts"].append(item)
    ledger["queue_seconds"]+=queued
    ledger["allocation_seconds"]+=allocated
    ledger["model_updates"]+=charge_updates
    save(folder/"ANALYSIS.json",report)
    save(ledger_path,ledger)
    save(HERE/"ACTIVE_JOB.json",dict(active_job=None,status="NO_ACTIVE_JOB",last_terminal=item))
    print(job,report["status"],report.get("host"),allocated,updates,
          [(p,v.get("median_synchronized_step_seconds")) for p,v in report["phases"].items()])


if __name__=="__main__":
    main(Path(sys.argv[1]).resolve(),sys.argv[2],sys.argv[3])
