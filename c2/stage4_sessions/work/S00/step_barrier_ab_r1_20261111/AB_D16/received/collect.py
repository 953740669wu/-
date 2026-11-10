"""Preserve one exact terminal job and its raw diagnostic artifacts."""
import hashlib
import json
from pathlib import Path
import shlex
import sys
import zipfile

from prepare import ROOT, need, save, verify
from submit_once import detail, owned


def main(pin):
    binding = verify(ROOT,pin)
    job = (ROOT/"job_id.txt").read_text().strip()
    binding["native_argv"] = [pin if arg == "BINDING_SHA256" else arg for arg in binding["native_argv"]]
    row = detail(job,"djob_final.json")
    need(owned(row,binding) and row["state"] in ("SUCCEEDED","FAILED","CANCELLED"),"require owned terminal record")
    bundle = ROOT / f"JOB_{job}_evidence.zip"
    archive, index = {}, {}
    for path in sorted(ROOT.rglob("*")):
        if not path.is_file():
            continue
        need(path.resolve() == path,"unexpected redirected evidence")
        name = path.relative_to(ROOT).as_posix()
        omit = path.suffix in {".pt",".pth",".npz"}
        h = hashlib.sha256()
        with path.open("rb") as stream:
            for block in iter(lambda:stream.read(2**20),b""):
                h.update(block)
        index[name] = dict(bytes=path.stat().st_size,sha256=h.hexdigest(),archive=not omit)
        if not omit:
            archive[name] = path
    pids = [n["pids"] for g in row["resGroups"] for n in g["nodeResUsages"]]
    save(ROOT/"COLLECTION_INDEX.json",dict(job_id=job,state=row["state"],pids=pids,files=index))
    with zipfile.ZipFile(bundle,"x",zipfile.ZIP_DEFLATED) as z:
        for name,path in archive.items():
            z.write(path,name)
        z.write(ROOT/"COLLECTION_INDEX.json","COLLECTION_INDEX.json")
    receipt = dict(job_id=job,bytes=bundle.stat().st_size,sha256=hashlib.sha256(bundle.read_bytes()).hexdigest(),
                   members=len(archive)+1,state=row["state"],pids=pids)
    save(ROOT/"bundle_receipt.json",receipt)
    print(json.dumps(receipt),flush=True)


if __name__ == "__main__":
    main(sys.argv[1])
