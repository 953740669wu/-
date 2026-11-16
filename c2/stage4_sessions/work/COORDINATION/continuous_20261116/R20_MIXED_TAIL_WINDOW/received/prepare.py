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
    gate = json.loads((root/"STRICT16_REVIEW.json").read_bytes())
    profile = json.loads((root/"PROFILE_GATE.json").read_bytes())
    need(profile["tail_domains"] == [i for i in range(16) if i != 4]
         and profile["original_domains"] == [4], "wrong mixed profile")
    need(gate["cleanup_passed"] and gate["job_id"] == "2146931", "strict source not closed")
    need(all(d["phases"]["baseline"]["passed"] for d in gate["domains"].values()), "original coverage incomplete")
    for node in profile["tail_domains"]:
        value = gate["domains"]["node"+str(node)]
        phase = value["phases"]["candidate"]
        need(value["strict5_passed"] and phase["metrics"] == 3880
             and not phase["failed_metrics"], "changed domain strict gate incomplete")
    return binding


if __name__ == "__main__":
    verify(ROOT, sys.argv[1])
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
