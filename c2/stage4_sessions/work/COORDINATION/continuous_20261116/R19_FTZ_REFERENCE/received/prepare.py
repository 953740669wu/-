"""Verify this one M1 deployment and Linux entrypoints."""
import ast
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(path, value):
    path = Path(path)
    tmp = path.with_name("." + path.name + ".partial")
    tmp.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(path)


def need(ok, why):
    if not ok:
        raise ValueError(why)


def verify(root, pin):
    path = root / "RUN_BINDING.json"
    need(sha(path) == pin, "independent run binding SHA differs")
    binding = json.loads(path.read_bytes())
    need(binding["remote_root"] == str(root) and root.parent == Path("/home/share/wujunyi/opt/stage4_sessions/S00")
         and root.name.startswith("CONTINUOUS_20261116_") and binding["user_authorized"] is True,
         "wrong dedicated directory or scope")
    need(sha(root / "FULL16_PAYLOAD.zip") == binding["package_sha256"], "package SHA differs")
    manifest = root / "SOURCE_SHA256.json"
    need(sha(manifest) == binding["source_manifest_sha256"], "source manifest SHA differs")
    for name, expected in json.loads(manifest.read_bytes()).items():
        path = root / name
        need(path.resolve() == path and sha(path) == expected, "source SHA differs: " + name)
    need(sha(root / "ENGINEERING_DESCRIPTOR.json") == binding["descriptor_sha256"], "descriptor differs")
    for name,expected in binding["frozen_sidecars"].items():
        need(sha(root/name) == expected, "frozen dependency sidecar differs: " + name)
    ref = json.loads((root/"EXTERNAL_REFERENCE.json").read_bytes())
    external = Path(binding["external_reference_root"])
    need(str(external) == ref["remote_root"], "external reference directory differs")
    for name, expected in ref["metadata_sha256"].items():
        need(sha(external/name) == expected, "external reference metadata changed: " + name)
    receipt = json.loads((external/"result.json").read_bytes())
    need(receipt["status"] == "PASS_STRICT_REFERENCE5" and receipt["completed_updates"] == 5,
         "external reference is incomplete")
    need([(r["bytes"],r["sha256"]) for r in ref["snapshots"]] ==
         [(r["bytes"],r["sha256"]) for r in receipt["reference_snapshots"]], "reference identities differ")
    for row in ref["snapshots"]:
        need((external/row["name"]).stat().st_size == row["bytes"], "reference snapshot size changed")
    return binding


if __name__ == "__main__":
    from hbm_selection import bound_selection
    bound_selection(ROOT, verify(ROOT, sys.argv[1]))
    for path in ROOT.rglob("*"):
        if path.suffix not in (".py", ".sh"):
            continue
        raw = path.read_bytes()
        need(b"\r" not in raw, "non-LF source " + str(path))
        if path.suffix == ".py":
            ast.parse(raw, filename=str(path), feature_version=(3, 9))
        else:
            subprocess.run(["/bin/bash", "-n", str(path)], check=True, timeout=5)
    save(ROOT / "site_static.json", dict(status="SHA_LF_AST_BASH_PASS", binding_sha256=sys.argv[1]))
