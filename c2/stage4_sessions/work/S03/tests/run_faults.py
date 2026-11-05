"""Run the compiled Linux/glibc harness. No HBM or kernel-policy validation."""
import argparse
import json
from pathlib import Path
import subprocess
import sys


def cases():
    result = {}
    for name in ("no_node", "pages_0", "pages_15", "pages_16", "pages_17", "pages_47",
                 "read_open_fail", "read_parse_fail", "read_negative", "below_min"):
        result[name] = (0, dict(get=0, bind=0, map=0, restore=0, mbind=0, unmap=0, arena=0, policy_ok=1))
    for name, mb in (("pages_48", 64), ("pages_49", 66), ("pages_2020", 3800),
                     ("cap_9000", 4008), ("cap_64", 64), ("old_default", 3800),
                     ("old_local", 3800), ("old_preferred", 3800)):
        result[name] = (0, dict(get=1, bind=1, map=1, restore=1, mbind=1, unmap=0,
                               arena=1, policy_ok=1, mb=mb, map_hbm=1, mbind_restored=1))
    result["get_fail"] = (0, dict(get=1, bind=0, map=0, restore=0, mbind=0, unmap=0, arena=0, policy_ok=1))
    result["set_fail"] = (0, dict(get=1, bind=1, map=0, restore=1, mbind=0, unmap=0, arena=0, policy_ok=1))
    result["map_fail"] = (0, dict(get=1, bind=1, map=1, restore=1, mbind=0, unmap=0, arena=0, policy_ok=1))
    result["mbind_fail"] = (0, dict(get=1, bind=1, map=1, restore=1, mbind=1, unmap=1, arena=0, policy_ok=1))
    result["restore_fail"] = (1, dict(get=1, bind=1, map=1, restore=1, mbind=0, unmap=1, arena=0))
    result["map_restore_fail"] = (1, dict(get=1, bind=1, map=1, restore=1, mbind=0, unmap=0, arena=0))
    result["set_restore_fail"] = (1, dict(get=1, bind=1, map=0, restore=1, mbind=0, unmap=0, arena=0))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("executable", type=Path)
    parser.add_argument("--json", type=Path, required=True)
    args = parser.parse_args()
    records = []
    for name, (exitcode, expected) in cases().items():
        child = subprocess.run([str(args.executable.resolve()), name], capture_output=True,
                               text=True, timeout=15)
        traces = [line for line in child.stdout.splitlines() if line.startswith("TRACE ")]
        observed = dict(item.split("=", 1) for item in traces[0].split()[1:]) if len(traces) == 1 else {}
        mismatches = {key: dict(expected=value, observed=observed.get(key))
                      for key, value in expected.items() if observed.get(key) != str(value)}
        returned = "RESULT returned_and_allocation_ok" in child.stdout
        ok = child.returncode == exitcode and not mismatches and returned == (exitcode == 0)
        if exitcode:
            ok = ok and "fatal" in child.stderr and "restore" in child.stderr
        record = dict(case=name, passed=ok, expected_exit=exitcode, exitcode=child.returncode,
                      mismatches=mismatches, stdout=child.stdout, stderr=child.stderr)
        records.append(record)
        print(f"{'PASS' if ok else 'FAIL'} {name}: exit={child.returncode}, mismatches={mismatches}")
    args.json.write_text(json.dumps(dict(scope="C_IMPLEMENTATION_WITH_OS_SUBSTITUTES_ONLY",
                                        real_hbm=False, real_mempolicy=False, cases=records), indent=2) + "\n",
                         encoding="utf-8")
    return 0 if all(row["passed"] for row in records) else 1


if __name__ == "__main__":
    sys.exit(main())
