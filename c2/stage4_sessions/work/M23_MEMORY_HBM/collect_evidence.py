from pathlib import Path
import hashlib
import json
import os
import stat
import sys
import zipfile

job = sys.argv[1]
root = Path.cwd()
assert root.parent.name == "M23_MEMORY_HBM" and (root/"job_id.txt").read_text().strip() == job
terminal = json.loads((root/"djob_final.json").read_bytes())["data"]["successData"][0]
assert str(terminal["jobId"]) == job and terminal["execPath"] == str(root)
assert terminal["state"] in {"SUCCEEDED", "FAILED", "CANCELLED"} and terminal["taskExecNodes"] != "cn21340"
out = root / ("JOB_" + job + "_evidence.zip")
assert not out.exists() and not (root/"bundle_receipt.json").exists()
paths = sorted(p for p in root.rglob("*") if p.is_file() and not p.is_symlink() and "__pycache__" not in p.parts)
files = {}
with zipfile.ZipFile(out.with_suffix(".partial"), "x", zipfile.ZIP_DEFLATED) as archive:
    for path in paths:
        name = path.relative_to(root).as_posix()
        before = path.stat()
        assert stat.S_ISREG(before.st_mode) and before.st_size < 16*2**20
        data = path.read_bytes()
        after = path.stat()
        assert (before.st_mtime_ns, before.st_size) == (after.st_mtime_ns, after.st_size) and len(data) == before.st_size
        files[name] = dict(bytes=len(data), sha256=hashlib.sha256(data).hexdigest(), mtime_ns=before.st_mtime_ns)
        archive.writestr(name, data)
    archive.writestr("COLLECTION.json", json.dumps(files, indent=2)+"\n")
out.with_suffix(".partial").replace(out)
receipt = dict(file=out.name, bytes=out.stat().st_size, sha256=hashlib.sha256(out.read_bytes()).hexdigest(), files=len(files))
(root/"bundle_receipt.json").write_text(json.dumps(receipt, indent=2)+"\n")
print(json.dumps(receipt))
