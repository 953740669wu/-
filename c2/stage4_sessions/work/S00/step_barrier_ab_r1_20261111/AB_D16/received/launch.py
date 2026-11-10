"""Verify a full node, then run the bound DDR/HBM and stability phases."""
import time

START = time.monotonic()

import ctypes
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import tempfile
import sys
import traceback

from hbm_gate import prepare_hbm, free_pages
from owned_processes import Owned, cleanup, process_table
from prepare import ROOT, need, save, verify
from scheduler_handoff import await_handoff, create_request, live_context
from topology16 import full_topology

sys.path.insert(0, str(ROOT / "payload"))
from cpu36_contract import cpu_list, discover_contracts
from window_control import WINDOW_NS, PER_ARM_CAP

EVIDENCE = ROOT / "job_evidence"


def read(path):
    return json.loads(path.read_bytes())


def memory_controller(job, native, mem):
    proc = Path("/proc/self")
    for name in ("cgroup", "mountinfo", "status"):
        (EVIDENCE / ("native." + name)).write_bytes((proc / name).read_bytes())
    memberships = {}
    for line in (proc / "cgroup").read_text().splitlines():
        hierarchy, controller, path = line.split(":", 2)
        if "memory" in controller.split(","):
            memberships["cgroup"] = Path(path)
        elif hierarchy == "0" and controller == "":
            memberships["cgroup2"] = Path(path)
    mounts = []
    for line in (proc / "mountinfo").read_text().splitlines():
        left, right = line.split(" - ", 1)
        fields, (fstype, _, options) = left.split(), right.split()
        if fstype not in memberships or (fstype == "cgroup" and "memory" not in options.split(",")):
            continue
        group = memberships[fstype]
        base = Path(fields[3])
        if base == group or base in group.parents:
            mounts.append((fstype, base, Path(fields[4]), group))
    need(len(mounts) == 1, "unique native memory controller mount missing")
    fstype, base, mount, group = mounts[0]
    leaf = mount / group.relative_to(base)
    control = "memory.max" if fstype == "cgroup2" else "memory.limit_in_bytes"
    limits = {}
    for directory in (leaf, *leaf.parents):
        if mount != directory and mount not in directory.parents:
            break
        path = directory / control
        if directory == mount and not path.is_file() and fstype == "cgroup2":
            break
        try:
            limits[str(directory)] = path.read_text().strip()
        except PermissionError as exc:
            # This site's agent protects the active v1 replica controller.
            # Accept only the exact own container and live native -RL receipt.
            need(directory == leaf and fstype == "cgroup" and mount == Path("/sys/fs/cgroup/memory")
                 and re.fullmatch(r"/batch/container_" + re.escape(job) + r"_rg0_[0-9]+_e[0-9]+", str(group))
                 and native["replica"] == 1 and native["resReq"]["mem"] == native["resAlloc"]["mem"] == native["resLimit"]["mem"] == mem,
                 "protected controller lacks the exact own native hard-limit binding")
            save(EVIDENCE / "native_memory_limit.json", dict(job_id=job, group=str(group), controller=fstype,
                 status="NATIVE_SCHEDULER_LIMIT_WITH_BOUND_CGROUP", kernel_limit_bytes=None,
                 native_limit_MB=native["resLimit"]["mem"], request_MB=native["resReq"]["mem"],
                 allocated_MB=native["resAlloc"]["mem"], kernel_read_error=str(exc), scheduler_evidence="scheduler_allocation.json"))
            return
    need(limits, "memory controller unreadable")
    effective = min((int(v) for v in limits.values() if v != "max"), default=-1)
    save(EVIDENCE / "native_memory_limit.json", dict(job_id=job, group=str(group), controller=fstype,
         limits_bytes=limits, effective_limit_bytes=effective))
    need(effective == mem * 2**20, "actual inherited DDR hard limit differs")


def topology(context, count):
    allowed = context["allowed"]
    need(len(allowed) == 38 * count, "wrong allocation core count")
    nodes = sorted(Path("/sys/devices/system/node").glob("node[0-9]*"), key=lambda p:int(p.name[4:]))
    ids = [int(p.name[4:]) for p in nodes]
    cpu_nodes = {n: cpu_list((p / "cpulist").read_text()) for n,p in zip(ids,nodes)}
    distances = {n: [int(v) for v in (p / "distance").read_text().split()] for n,p in zip(ids,nodes)}
    contracts = discover_contracts(allowed, count)
    need(len(contracts) == count and sorted(c for r in contracts.values() for c in r["allocated"]) == allowed,
         "allocation does not contain 16 whole CPU36 domains")
    targets = [n for n,p in zip(ids,nodes) if not cpu_nodes[n]
               and (p/"hugepages/hugepages-2048kB/free_hugepages").is_file()]
    placement = full_topology(cpu_nodes,{n:dict(zip(ids,row)) for n,row in distances.items()},contracts,targets)
    physical = {}
    for node, contract in contracts.items():
        need(contract["allocated"] == cpu_nodes[node] and len(contract["allocated"]) == 38,
             "partial domain allocation")
        node_path = Path("/sys/devices/system/node") / f"node{node}"
        meminfo = (node_path / "meminfo").read_text()
        (EVIDENCE / f"node{node}.meminfo").write_text(meminfo)
        match = re.search(r"MemTotal:\s+(\d+) kB", meminfo)
        need(match and int(match[1]) >= 24576 * 1024, "CPU-bearing DDR capacity below 24 GiB")
        for cpu in contract["allocated"]:
            directory = Path(f"/sys/devices/system/cpu/cpu{cpu}")
            need([p.name for p in directory.glob("node[0-9]*")] == [f"node{node}"], "CPU-to-node topology drift")
            info = directory / "topology"
            physical[cpu] = {key: (info / key).read_text().strip() for key in ("physical_package_id","core_id","die_id") if (info / key).is_file()}
        save(EVIDENCE / f"node{node}.allocation.json", dict(job_id=context["job_id"], host=context["host"], receipt=contract))
    need(len({tuple(s) for r in contracts.values() for s in r["physical_siblings"].values()}) == 608,
         "608 distinct physical cores required across dies")
    save(EVIDENCE / "domain_map.json", dict(context=context, contracts=contracts, node_ids=ids, cpu_nodes=cpu_nodes,
         distances=distances, physical=physical, **placement))
    for n, node_path in zip(ids, nodes):
        for huge in node_path.glob("hugepages/hugepages-*"):
            fields = {p.name: p.read_text().strip() for p in sorted(huge.glob("*")) if p.is_file()}
            save(EVIDENCE / f"node{n}.{huge.name}.json", dict(cpus=cpu_nodes[n], counters=fields))
    return contracts


def allocation(binding):
    context = live_context()
    need(context["host"] in binding["eligible_hosts"] and context["host"] not in binding["excluded_hosts"],
         "host outside bound eligible set")
    count = binding["domain_count"]
    need(count == 16, "full node requires exactly 16 domains")
    mem = count * 24576
    req = create_request(ROOT, context)
    gate = await_handoff(ROOT, req, context, 38 * count, mem, binding["wall_seconds"], timeout=35)
    save(EVIDENCE / "scheduler_handoff.json", gate)
    raw = read(ROOT / "scheduler_allocation.json")["data"]["successData"][0]
    need(raw["queue"] == "q_hpcai" and raw["execPath"] == str(ROOT) and raw["user"] == binding["scheduler_user"]
         and raw["retryPolicy"] == dict(maxRetryCnt=0, currentRetryTimes=0), "wrong native job scope or retries")
    group = raw["resGroups"][0]
    need([s.replace(" ", "") for s in group["affinityRequest"]] == [f"numa[count={count},distribution=pack]"], "native domain placement request differs")
    for res in (group["resReq"], group["resAlloc"]):
        need(res["cpu"] == 38 * count and res["mem"] == mem and res["gpu"]["amount"] == 0
             and res["npu"]["count"] == 0, "native request/allocation differs")
    memory_controller(context["job_id"], group, mem)
    return topology(context, count)


def sample(proc, contracts):
    selected = {f"cpu{c}" for r in contracts.values() for c in r["selected"]}
    cpu = {}
    for line in Path("/proc/stat").read_text().splitlines():
        fields = line.split()
        if fields[0] in selected:
            cpu[fields[0]] = list(map(int, fields[1:]))
    ticks = {}
    for node, child in proc.items():
        try:
            value = Path(f"/proc/{child.pid}/stat").read_text()
            fields = value[value.rfind(")") + 2:].split()
            ticks[node] = dict(pid=child.pid, ticks=int(fields[11])+int(fields[12]), start_ticks=int(fields[19]))
        except FileNotFoundError:
            continue
    return dict(at_ns=time.monotonic_ns(), per_cpu=cpu, worker_ticks=ticks)


def phase(arm, contracts, owner, binding, deadline, placements, counter):
    name, variant = "perf", "candidate"
    out = EVIDENCE / arm
    out.mkdir()
    barriers = out / "barriers"
    barriers.mkdir()
    allocated = {cpu for receipt in contracts.values() for cpu in receipt["allocated"]}
    os.sched_setaffinity(0, allocated)
    need(os.sched_getaffinity(0) == allocated, "worker launch must inherit the exact allocation")
    status = Path("/proc/self/status").read_text().splitlines()
    inherited = next(line.split(":", 1)[1].strip() for line in status if line.startswith("Cpus_allowed_list:"))
    need(set(cpu_list(inherited)) == allocated, "parent native CPU list differs")
    save(out / "parent_before_spawn.json", dict(pid=os.getpid(), job_id=os.environ["CCS_JOB_ID"],
         allowed=sorted(allocated), allowed_list=inherited))
    proc = {}
    for node, receipt in contracts.items():
        rank = f"node{node}"
        argv = ["/bin/bash", str(ROOT / "run_worker.sh"), ",".join(map(str,receipt["allocated"])), str(node),
                "--phase",name,"--variant",variant,"--descriptor",str(ROOT / "ENGINEERING_DESCRIPTOR.json"),
                "--descriptor-sha",binding["descriptor_sha256"],"--allocation",str(EVIDENCE / f"{rank}.allocation.json"),
                "--phase-root",str(out),"--output",str(out / rank),"--deadline",str(deadline),
                "--reference",str(ROOT / "FROZEN_REFERENCE"),"--arm",arm,"--counter",str(counter)]
        save(out / f"{rank}.command.json", dict(argv=argv))
        env = dict(os.environ, M1_PARENT_CPU_LIST=inherited, M1_INHERIT_RECEIPT=str(out / f"{rank}.before_numactl.txt"))
        if variant == "candidate":
            cfg = placements[node]
            need((free_pages(cfg["hbm_node"])-16)*2 >= cfg["cap_MiB"], "HBM pool became smaller after safety gate")
            env.update(M23_HBM_LIBRARY=cfg["library"], M23_HBM_LIBRARY_SHA=cfg["library_sha256"],
                       HBM_NODE=str(cfg["hbm_node"]), HBM_MB=str(cfg["cap_MiB"]), HBM_MIN_KB="256", HBM_STATS="1")
        env.update(S09_INVENTORY="0", S00_BATCH=str(binding["batch_size"]),
                   S00_MATCHED_CKPT=str(binding["checkpoint_layers"]))
        save(out / f"{rank}.env.json", {k:v for k,v in env.items() if k.startswith(("M23_", "HBM_", "S09_", "S00_"))})
        with (out / f"{rank}.log").open("xb") as log:
            proc[node] = subprocess.Popen(argv, cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
    os.sched_setaffinity(0, {next(iter(contracts.values()))["reserved"][0]})
    save(out / "parent_after_spawn.json", dict(pid=os.getpid(), allowed=sorted(os.sched_getaffinity(0)),
         children={n:p.pid for n,p in proc.items()}))
    step, sampled_at = 1, 0
    window = None
    with (out / "cpu_samples.jsonl").open("x") as samples:
        while True:
            now = time.monotonic()
            codes = {n:p.poll() for n,p in proc.items()}
            if any(code not in (None, 0) for code in codes.values()):
                save(out / "exit_codes.json", codes)
                raise RuntimeError(name + " worker failed: " + repr(codes))
            if all(code == 0 for code in codes.values()):
                save(out / "exit_codes.json", codes)
                break
            if now >= deadline:
                raise TimeoutError(name + " shared deadline")
            if now - sampled_at >= 5:
                owner.update(process_table())
                samples.write(json.dumps(sample(proc, contracts)) + "\n")
                samples.flush()
                sampled_at = now
            if step <= 6 or (arm == "A" and time.monotonic_ns() < window["close_ns"]):
                ready = {n:barriers / f"{step}.node{n}.ready" for n in proc}
                if all(p.is_file() for p in ready.values()):
                    arrivals = {n:read(p) for n,p in ready.items()}
                    need(all(r["pid"] == proc[n].pid for n,r in arrivals.items()), "barrier PID differs")
                    release = time.monotonic_ns()+100_000_000
                    if step == 6:
                        window = dict(open_ns=release,close_ns=release+WINDOW_NS)
                        need(window["close_ns"]/1e9 < deadline, "not enough time for a complete 600-second window")
                        save(out/"WINDOW.json",window)
                    if step <= 6 or release < window["close_ns"]:
                        save(barriers / f"{step}.release", dict(step=step, arrivals=arrivals, release_at_ns=release))
                    step += 1
            time.sleep(.02)
    need(window and time.monotonic_ns() >= window["close_ns"], "incomplete fixed window")
    results = [read(out / f"node{n}" / "result.json") for n in contracts]
    need(all(r["status"] == "PASS_FIXED_WINDOW" and r["completed_updates"] >= 5 and r["window"] == window
             and r["job_id"] == os.environ["CCS_JOB_ID"] and r["host"] == os.uname().nodename
             and r["variant"] == variant for r in results), "all 16 fixed-window receipts required")
    save(out / "phase_receipt.json", dict(status="PASS_FIXED_WINDOW", job_id=os.environ["CCS_JOB_ID"],
         window=window, updates_reserved=int(counter.read_text()),
         domains={n:r["completed_updates"] for n,r in zip(contracts,results)}))


def stop(signum, _):
    raise InterruptedError("native signal " + str(signum))


def verify_return(placements, label):
    actual = {n:free_pages(c["hbm_node"]) for n,c in placements.items()}
    expected = {n:c["pool_pages_before"] for n,c in placements.items()}
    save(EVIDENCE / f"pool_return_{label}.json", dict(actual=actual, expected=expected, passed=actual==expected))
    need(actual == expected, f"HBM pool not restored after {label}")


def main(pin):
    EVIDENCE.mkdir(exist_ok=False)
    outcome = dict(status="FAIL_STOP", job_id=os.environ.get("CCS_JOB_ID"), start=START, steps={})
    owner = Owned(os.getpid())
    deadline = START + 120
    placements = {}
    counters = {}
    local = None
    try:
        binding = verify(ROOT, pin)
        wall = binding["wall_seconds"]
        deadline = START + wall - 30
        need(1200+120 < wall <= 7200 and binding["mode"] == "step_barrier_ab_fixed_window"
             and binding["window_seconds"] == 600 and binding["max_model_updates"] == 2*PER_ARM_CAP,
             "wrong authorized A/B scope")
        libc = ctypes.CDLL(None, use_errno=True)
        need(libc.prctl(36,1,0,0,0) == 0, "cannot become owned-process subreaper")
        for sig in (signal.SIGTERM, signal.SIGINT, signal.SIGALRM):
            signal.signal(sig, stop)
        end = START + wall - 120
        signal.setitimer(signal.ITIMER_REAL, max(.001, end-time.monotonic()))
        contracts = allocation(binding)
        placements = prepare_hbm(ROOT, EVIDENCE, contracts, binding, end)
        outcome["hbm_safety"] = "PASS"
        local = tempfile.TemporaryDirectory(prefix="s00_step_ab_",dir="/dev/shm")
        outcome["completed_arms"] = []
        for arm in ("A","B"):
            if end-time.monotonic() <= (1200 if arm == "A" else 600):
                raise TimeoutError("not enough time for complete remaining windows")
            counter = counters[arm] = Path(local.name)/arm
            counter.write_text("0000")
            outcome["active_phase"] = arm
            phase(arm, contracts, owner, binding, end, placements, counter)
            verify_return(placements, arm)
            outcome["completed_arms"].append(arm)
        outcome["active_phase"] = None
        verify(ROOT, pin)
        outcome["status"] = "PASS_FULL_NODE_COMPLETED_PHASES"
    except BaseException as exc:
        outcome.update(error=repr(exc), traceback=traceback.format_exc())
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        for sig in (signal.SIGINT, signal.SIGTERM):
            signal.signal(sig, signal.SIG_IGN)
        try:
            receipt = cleanup(owner, min(deadline,time.monotonic()+30))
            save(EVIDENCE / "cleanup.json", receipt)
            need(receipt["all_reaped"], "owned process cleanup incomplete")
            if local is not None:
                reservations = {arm:int(counter.read_text()) for arm,counter in counters.items()}
                local.cleanup()
                save(EVIDENCE/"update_budget_cleanup.json",dict(reservations=reservations,
                     path=local.name,removed=not Path(local.name).exists()))
            if placements:
                verify_return(placements, "terminal")
                outcome["hbm_pool_restored"] = True
            elif (EVIDENCE / "hbm_capacity_before.json").is_file():
                topo = read(EVIDENCE / "domain_map.json")
                expected = read(EVIDENCE / "hbm_capacity_before.json")["free_pages"]
                actual = {n:free_pages(topo["hbm_pairs"][n]) for n in expected}
                save(EVIDENCE / "pool_return_after_partial_gate.json", dict(actual=actual, expected=expected, passed=actual==expected))
                outcome["hbm_pool_restored"] = actual == expected
        except BaseException as exc:
            outcome.update(status="FAIL_STOP", cleanup_error=repr(exc))
        outcome["finished"] = time.monotonic()
        save(EVIDENCE / "SUMMARY.json", outcome)
    return 0 if outcome["status"] == "PASS_FULL_NODE_COMPLETED_PHASES" else 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1]))
