"""Check the frozen accepted allocator and each domain's local HBM pool."""
import json
from pathlib import Path
from prepare import need, save, sha

LIBRARY_SHA = "89f295754a199dcb6206f8e6217e6cf57651bceed2d364b1a6e4cc83eea6095d"
SOURCE_SHA = "d1f5dbbfb6aa4a973dcc4d12607f62a8b2be5166690897dfd5ea35e067c7d7a2"
CAP_MIB = 3800


def free_pages(node):
    return int(Path(f"/sys/devices/system/node/node{node}/hugepages/hugepages-2048kB/free_hugepages")
               .read_text())


def prepare_hbm(root, evidence, contracts):
    library = root / "s03/build/libhbm_alloc_s03_round2.so"
    need(sha(library) == LIBRARY_SHA and sha(root / "s03/candidate/hbm_alloc.c") == SOURCE_SHA,
         "frozen allocator SHA differs")
    topology = json.loads((evidence / "domain_map.json").read_bytes())
    nodes = topology["node_ids"]
    memory_nodes = [n for n in nodes if not topology["cpu_nodes"][str(n)]]
    placements = {}
    for node in contracts:
        hbm_node = node + 16
        distance = topology["distances"][str(node)]
        need(hbm_node in memory_nodes and distance[nodes.index(hbm_node)] ==
             min(distance[nodes.index(n)] for n in memory_nodes), "paired HBM topology differs")
        before = free_pages(hbm_node)
        need((before - 16) * 2 >= CAP_MIB, "insufficient local HBM for matched 3800 MiB")
        placements[node] = dict(hbm_node=hbm_node, cap_MiB=CAP_MIB, pool_pages_before=before,
                                library=str(library), library_sha256=LIBRARY_SHA)
    save(evidence / "hbm_preflight.json", placements)
    return placements
