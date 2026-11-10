"""Validate the four dies and derive one HBM target per actual CPU domain."""


def full_topology(cpu_nodes, distances, allocated_domains, memory_targets):
    cpu_domains = {n for n, cpus in cpu_nodes.items() if cpus}
    if len(cpu_domains) != 16 or set(allocated_domains) != cpu_domains:
        raise ValueError("require all 16 CPU-bearing NUMA domains on one host")
    if any(len(cpu_nodes[n]) != 38 for n in cpu_domains):
        raise ValueError("require 38 CPUs in every physical domain")
    if any(n not in cpu_nodes or cpu_nodes[n] for n in memory_targets) or len(memory_targets) < 16:
        raise ValueError("expected at least 16 memory-only HBM page-pool targets")
    dies, pairs = {}, {}
    for node in sorted(cpu_domains):
        d = distances[node]
        neighbors = tuple(sorted(n for n in cpu_domains if d[n] <= 20))
        if d[node] != 10 or len(neighbors) != 4 or any(d[n] != 20 for n in neighbors if n != node):
            raise ValueError(f"node{node}: unverified distance-20 die group")
        dies[node] = neighbors
        closest = min(d[n] for n in memory_targets)
        choices = [n for n in memory_targets if d[n] == closest]
        if len(choices) != 1:
            raise ValueError(f"node{node}: closest HBM target is not unique: {choices}")
        pairs[node] = choices[0]
    if len(set(dies.values())) != 4 or any(dies[n] != group for group in dies.values() for n in group):
        raise ValueError("die grouping does not partition into four symmetric groups")
    if len(set(pairs.values())) != 16:
        raise ValueError("CPU-to-HBM target pairing is not one-to-one")
    return dict(die_groups=sorted(set(dies.values())), hbm_pairs=pairs)
