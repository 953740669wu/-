"""Check the deployed selector's two positive and three negative paths without loading ELF."""
from pathlib import Path
import sys
import tempfile


if __name__ == "__main__":
    release = Path(sys.argv[1]).resolve()
    sys.path.insert(0, str(release))
    from hbm_selection import select

    with tempfile.TemporaryDirectory(dir=release) as temp:
        root = Path(temp).resolve()
        (root / "lib").mkdir()
        original = (release / "FROZEN_HBM_ALLOCATOR.so").read_bytes()
        default = root / "FROZEN_HBM_ALLOCATOR.so"
        explicit = root / "lib/libhbm_alloc_explicit.so"
        bad = root / "lib/bad.so"
        default.write_bytes(original)
        explicit.write_bytes(original)
        bad.write_bytes(b"unapproved bytes\n")
        assert select(root, None)["allocator_origin"] == default.as_posix()
        assert select(root, explicit.name)["allocator_origin"] == explicit.as_posix()
        for request, reason in (("missing.so", "missing"), ("bad.so", "sha256"),
                                ("../FROZEN_HBM_ALLOCATOR.so", "outside_private_lib")):
            try:
                select(root, request)
            except ValueError as exc:
                assert str(exc) == reason
            else:
                raise AssertionError("selector accepted " + request)
    print("PASS default, explicit, missing, wrong SHA, outside private lib")
