"""Delivery integrity only; does not compile or execute C or check C behavior."""
import argparse
import ast
import difflib
import hashlib
import json
from pathlib import Path

from cases import cases


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", type=Path, required=True)
    parser.add_argument("--check-previous", action="store_true")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    checks = []
    previous_sha = "8ec586c60c97bbcdb437fe848b6d9645ea3cfca850952ff9d94c0d36fdaed35d"
    assert sha(root / "frozen/hbm_alloc.c") == previous_sha
    checks.append("frozen_source_identity")
    old = (root / "frozen/hbm_alloc.c").read_text(encoding="utf-8")
    new = (root / "candidate/hbm_alloc.c").read_text(encoding="utf-8")
    expected = "".join(difflib.unified_diff(old.splitlines(True), new.splitlines(True),
                                         fromfile="frozen/hbm_alloc.c", tofile="candidate/hbm_alloc.c"))
    assert (root / "candidate/hbm_alloc.diff").read_text(encoding="utf-8") == expected
    checks.append("diff_matches_exact_sources")
    for first, last in (("void free(void *p)", "__attribute__((destructor))"),
                        ("static void arena_put", "int posix_memalign"),
                        ("static bucket *slot", "static void *arena_get"),
                        ("    unsigned long mask[2]", "static int in_arena")):
        assert old[old.index(first):old.index(last)] == new[new.index(first):new.index(last)]
    checks.append("free_realloc_reuse_and_policy_cleanup_unchanged")
    first_checks = json.loads((root / "evidence/tests_before_candidate.json").read_text(encoding="utf-8"))
    for name, value in first_checks["test_sha256"].items():
        assert sha(root / name.replace("\\", "/")) == value
    assert sha(root / "BEHAVIOR.md") == first_checks["contract_sha256"]
    checks.append("pre_implementation_test_and_contract_identity")
    rows = cases()
    assert len(rows) == len({r["name"] for r in rows}) == 50
    assert sum(r["previous_failure"] for r in rows) == 21
    assert sum(r["sanitizer_failure"] for r in rows) == 2
    checks.append("new_case_catalog_50_with_21_expected_previous_defects")
    for path in (root / "tests").glob("*.py"):
        ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    checks.append("python_syntax")
    if args.check_previous:
        protected = json.loads((root / "evidence/protected_previous_files.json").read_text(encoding="utf-8"))
        for name, value in protected.items():
            assert sha(Path(name)) == value
        assert sha(root.parent / "candidate/hbm_alloc.c") == previous_sha
        checks.append("19_previous_delivery_files_unchanged")
    record = dict(scope="LOCAL_DELIVERY_INTEGRITY_ONLY", checks=checks, passed=len(checks),
                  candidate_sha256=sha(root / "candidate/hbm_alloc.c"),
                  c_compiled_or_executed=False, real_kernel_or_hbm=False, jobs_submitted=0)
    args.json.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(record, indent=2))


if __name__ == "__main__":
    main()
