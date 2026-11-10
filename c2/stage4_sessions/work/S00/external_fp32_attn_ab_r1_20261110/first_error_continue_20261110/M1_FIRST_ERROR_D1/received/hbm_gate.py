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
    topology = json.loads((evidence / "domain_map.json").read_bytes())
    placements = {}
    pairs = topology["hbm_pairs"]
    cap = binding["hbm_cap_MiB"]
    need(64 <= cap <= 3800 and cap % 2 == 0, "invalid bound 2MiB-page HBM capacity")
    initial = {str(node):free_pages(pairs[str(node)]) for node in contracts}
    save(evidence / "hbm_capacity_before.json", dict(free_pages=initial, cap_MiB=cap, reserve_pages=16,
         insufficient=[n for n,v in initial.items() if (v-16)*2 < cap]))
    need(all((v-16)*2 >= cap for v in initial.values()), "whole-node HBM pool below fixed matched capacity")
    return {node: dict(hbm_node=pairs[str(node)], cap_MiB=cap, pool_pages_before=initial[str(node)],
                       library=str(library), library_sha256=sha(library)) for node in contracts}
