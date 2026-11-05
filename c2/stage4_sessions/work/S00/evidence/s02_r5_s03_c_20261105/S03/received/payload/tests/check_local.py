"""Source contracts only. This does NOT compile or execute the allocator C code."""
import argparse
import ctypes
import json
from pathlib import Path
import re
import sys
import unittest


class SourceContracts(unittest.TestCase):
    source = ""

    def test_capacity_is_guarded_before_unsigned_conversion(self):
        # Reproduce the original expression on the target's 64-bit size_t ABI.
        bits = 64
        wrapped = {n: (((n - 16) % (1 << bits)) * 2) % (1 << bits)
                   for n in (0, 15)}
        self.assertTrue(all(v > 3800 for v in wrapped.values()))
        self.assertNotIn("(size_t)(nfree - 16) * 2 < mb", self.source,
                         "original unsigned-wrap capacity condition remains")
        self.assertRegex(self.source,
                         r"nfree > 16 \? \(size_t\)\(nfree - 16\) \* 2 : 0")
        self.assertRegex(self.source, r"if \(available_mb < mb\) mb = available_mb;")

    def test_unreadable_page_count_stops_before_policy_calls(self):
        guard = re.search(r"if \(nfree < 0\) \{[^}]*return;[^}]*\}", self.source)
        self.assertIsNotNone(guard, "unknown page count must disable arena")
        self.assertLess(guard.end(), self.source.index("SYS_get_mempolicy"))

    def test_failed_policy_snapshot_stops_before_binding(self):
        guard = re.search(r"if \(syscall\(SYS_get_mempolicy[^\n]*!= 0\) \{[^}]*return;[^}]*\}",
                          self.source)
        self.assertIsNotNone(guard, "unchecked policy snapshot")
        self.assertLess(guard.end(), self.source.index("SYS_set_mempolicy"))

    def test_temporary_bind_is_checked_before_mapping(self):
        self.assertRegex(self.source,
                         r"int bound = syscall\(SYS_set_mempolicy[^\n]*== 0;")
        self.assertRegex(self.source, r"void \*p = bound \? mmap\([^\n]*: MAP_FAILED;")
        self.assertRegex(self.source, r"if \(!bound\) \{[^}]*return;[^}]*\}")

    def test_failed_restore_exits_before_arena_publication(self):
        guard = re.search(r"if \(syscall\(SYS_set_mempolicy, oldmode[^\n]*!= 0\) \{([^}]+)\}",
                          self.source)
        self.assertIsNotNone(guard, "unchecked policy restoration")
        self.assertIn("munmap(p, len)", guard.group(1))
        self.assertIn("_exit(EXIT_FAILURE);", guard.group(1))
        self.assertLess(guard.end(), self.source.index("SYS_mbind"))
        self.assertLess(guard.end(), self.source.index("base = bump = p"))

    def test_allocator_outside_init_is_unchanged(self):
        frozen = Path(__file__).resolve().parents[1] / "frozen/hbm_alloc.c"
        baseline = frozen.read_text(encoding="utf-8")
        marker = "static int in_arena"
        self.assertEqual(self.source[self.source.index(marker):],
                         baseline[baseline.index(marker):])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("--json", type=Path, required=True)
    args = parser.parse_args()
    SourceContracts.source = args.source.read_text(encoding="utf-8")
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(SourceContracts)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    record = {
        "scope": "LOCAL_ARITHMETIC_REPRODUCTION_AND_STATIC_SOURCE_CONTRACTS_ONLY",
        "c_compiled_or_executed": False,
        "source": str(args.source.resolve()),
        "tests": result.testsRun,
        "failures": [t.id() for t, _ in result.failures],
        "errors": [t.id() for t, _ in result.errors],
        "success": result.wasSuccessful(),
        "host_size_t_bits": ctypes.sizeof(ctypes.c_size_t) * 8,
        "original_expression_unsigned64_mb": {
            str(n): (((n - 16) % (1 << 64)) * 2) % (1 << 64)
            for n in (0, 15, 16, 17, 48, 2020)
        },
    }
    args.json.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(main())
