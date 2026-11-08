"""Run frozen C checks, then exercise the real library in the allocated domains."""
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import time

from prepare import need, save, sha


def execute(out, name, argv, deadline, env=None):
    save(out / (name + ".command.json"), dict(argv=argv, hbm={
        k: v for k, v in (env or {}).items() if k in
        {"LD_PRELOAD", "HBM_MB", "HBM_NODE", "HBM_MIN_KB", "HBM_STATS"}}))
    with (out / (name + ".log")).open("xb") as log:
        proc = subprocess.run(argv, cwd=out, env=env, stdout=log, stderr=subprocess.STDOUT,
                              timeout=max(0.1, deadline - time.monotonic()))
    save(out / (name + ".exit.json"), dict(exit_code=proc.returncode))
    need(proc.returncode == 0, f"{name} exit {proc.returncode}; see {name}.log")


def free_pages(node):
    return int(Path(f"/sys/devices/system/node/node{node}/hugepages/hugepages-2048kB/free_hugepages")
               .read_text())


def probe_placement(out, node, hbm, cap, library):
    log = (out / "real_probe.log").read_text()
    need("PASS policy_restored=1 worker_threads=4 reuse=1" in log, "missing successful C probe")
    pointers = {k: int(v, 16) for k, v in re.findall(r"(first|bulk|fallback|worker[0-3])=(0x[0-9a-f]+)", log)}
    need(set(pointers) == {"first", "bulk", "fallback", "worker0", "worker1", "worker2", "worker3"},
         "probe pointer receipt incomplete")
    maps = (out / "probe.maps").read_text().splitlines()
    numa = {int(line.split()[0], 16): line for line in (out / "probe.numa_maps").read_text().splitlines()}
    need(any(line.endswith(str(library)) for line in maps), "actual allocator absent from probe maps")
    details = {}
    for name, pointer in pointers.items():
        line = next(line for line in maps if (lambda span: span[0] <= pointer < span[1])(
            [int(v, 16) for v in line.split()[0].split("-")]))
        start, end = (int(v, 16) for v in line.split()[0].split("-"))
        fields = numa[start].split()
        resident = {int(k): int(v) for k, v in re.findall(r"\bN(\d+)=(\d+)\b", numa[start])}
        if name == "fallback":
            need("huge" not in fields and set(resident) == {node}, "fallback not ordinary local DDR")
        else:
            need("huge" in fields and f"bind:{hbm}" in fields and resident == {hbm: cap // 2}
                 and "kernelpagesize_kB=2048" in fields and end-start == cap*2**20,
                 "arena not fully touched on exact HBM node")
        details[name] = dict(mapping=line, numa=numa[start])
    need(len(set(pointers.values())) == len(pointers), "concurrent live buffers alias")
    return details


def prepare_hbm(root, evidence, contracts, binding, deadline):
    source = Path(binding["allocator_origin"])
    need(sha(source) == binding["allocator_sha256"], "frozen 16E normal build SHA differs")
    library = evidence / "libhbm_alloc_s03_round2.so"
    shutil.copyfile(source, library)
    need(sha(library) == binding["allocator_sha256"], "private allocator copy differs")
    execute(evidence, "allocator_ldd", ["ldd", str(library)], min(deadline, time.monotonic()+10))
    ldd = (evidence / "allocator_ldd.log").read_text()
    need("not found" not in ldd and "libubsan" not in ldd, "wrong independent normal library")
    save(evidence / "allocator_identity.json", dict(source=str(source), sha256=sha(library),
         candidate_c_sha256=binding["candidate_sha256"], existing_c50_ubsan_evidence_job="2061258",
         existing_16e_validation_reference=binding["existing_16e_validation_reference"]))
    executable = evidence / "real_hbm_probe"
    execute(evidence, "build_real_probe", ["/usr/bin/cc", "-std=gnu11", "-O2", "-Wall", "-Wextra", "-pthread",
            str(root / "real_hbm_probe.c"), "-o", str(executable)], min(deadline, time.monotonic()+20))
    topology = json.loads((evidence / "domain_map.json").read_bytes())
    placements = {}
    for node, contract in contracts.items():
        paired = node + 16
        nodes = topology["node_ids"]
        distance = topology["distances"][str(node)]
        memory_nodes = [n for n in nodes if not topology["cpu_nodes"][str(n)]]
        need(paired in memory_nodes and distance[nodes.index(paired)] ==
             min(distance[nodes.index(n)] for n in memory_nodes), "paired HBM topology differs")
        out = evidence / f"real_hbm_node{node}"
        out.mkdir()
        before = free_pages(paired)
        cap = min(3800, max(0, before - 16) * 2)
        need(cap >= 64, "insufficient local HBM pool")
        env = dict(os.environ, LD_PRELOAD=str(library), HBM_NODE=str(paired), HBM_MB=str(cap),
                   HBM_MIN_KB="256", HBM_STATS="1")
        cpus = ",".join(map(str, contract["selected"]))
        execute(out, "real_probe", ["/usr/bin/numactl", "--physcpubind=" + cpus,
                "--membind=" + str(node), str(executable), str(cap)], min(deadline, time.monotonic()+90), env)
        maps = probe_placement(out, node, paired, cap, library)
        after = free_pages(paired)
        need(after == before, "HBM pool pages did not return after probe exit")
        placements[node] = dict(status="PASS_REAL_HBM_SAFETY", hbm_node=paired, cap_MiB=cap,
                                pool_pages_before=before, pool_pages_after=after, placement=maps,
                                library=str(library), library_sha256=sha(library))
        save(out / "RECEIPT.json", placements[node])
    return placements
