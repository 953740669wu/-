"""Archive terminal 09-owned evidence without strict tensor scratch files."""
from pathlib import Path
import hashlib
import json
import stat
import sys
import zipfile

job=sys.argv[1]
root=Path.cwd()
assert root.parent.name=="memory_hbm_32e_r1_20261108" and (root/"job_id.txt").read_text().strip()==job
row,=json.loads((root/"djob_final.json").read_bytes())["data"]["successData"]
assert str(row["jobId"])==job and row["execPath"]==str(root)
assert row["state"] in {"SUCCEEDED","FAILED","CANCELLED"}
assert all(u.get("pids")=="-" for g in row.get("resGroups",[]) for u in g.get("nodeResUsages",[]))
out=root/("JOB_"+job+"_evidence.zip")
assert not out.exists() and not (root/"bundle_receipt.json").exists()
paths=sorted(p for p in root.rglob("*") if p.is_file() and not p.is_symlink() and p.suffix!=".pt"
             and "__pycache__" not in p.parts)
entries={}
with zipfile.ZipFile(out.with_suffix(".partial"),"x",zipfile.ZIP_DEFLATED) as archive:
    for p in paths:
        before=p.stat()
        assert stat.S_ISREG(before.st_mode) and before.st_size<32*2**20
        raw=p.read_bytes()
        after=p.stat()
        assert (before.st_mtime_ns,before.st_size)==(after.st_mtime_ns,after.st_size) and len(raw)==before.st_size
        name=p.relative_to(root).as_posix()
        entries[name]=dict(bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest(),mtime_ns=before.st_mtime_ns)
        archive.writestr(name,raw)
    archive.writestr("COLLECTION.json",json.dumps(entries,indent=2)+"\n")
out.with_suffix(".partial").replace(out)
receipt=dict(file=out.name,bytes=out.stat().st_size,sha256=hashlib.sha256(out.read_bytes()).hexdigest(),files=len(entries))
(root/"bundle_receipt.json").write_text(json.dumps(receipt,indent=2)+"\n")
print(json.dumps(receipt))
