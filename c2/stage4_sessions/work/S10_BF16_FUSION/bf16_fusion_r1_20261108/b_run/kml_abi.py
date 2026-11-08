"""Compile against an installed, unambiguous KML header and the frozen runtime library."""
import json
from pathlib import Path
import re
import subprocess

from prepare import need, save, sha

KML = Path("/opt/HPCKit/kml-lib/sme/kblas/multi/libkblas.so")
KML_SHA = "c9b2f040c5b4756d426589956059e3865749cd8751eb3914c57d42a9e84ebf3c"


def record(out, name, argv, check=True):
    proc = subprocess.run(argv, capture_output=True, timeout=30)
    (out / (name + ".stdout")).write_bytes(proc.stdout)
    (out / (name + ".stderr")).write_bytes(proc.stderr)
    save(out / (name + ".json"), dict(argv=argv, returncode=proc.returncode))
    if check:
        need(proc.returncode == 0, f"{name} failed")
    return proc.stdout


def build(root, evidence):
    out = evidence / "kml_abi"
    out.mkdir()
    library = KML.resolve(strict=True)
    need(sha(library) == KML_SHA, "frozen KML runtime differs")
    record(out, "library_owner", ["rpm", "-qf", str(library)], check=False)
    search_roots = [str(p) for p in map(Path, ("/opt/HPCKit", "/usr/include", "/usr/local/include")) if p.is_dir()]
    raw = record(out, "find_header", ["find", "-L", *search_roots, "-name", "kblas.h", "-print"], check=False)
    headers = sorted({Path(line).resolve(strict=True) for line in raw.decode().splitlines()})
    save(out / "header_search.json", dict(paths=[str(p) for p in headers], library=str(library), library_sha256=KML_SHA))
    matched = root / "verified_kml"
    provenance = (matched / "PROVENANCE.json").read_bytes()
    receipt = json.loads(provenance)
    header = matched / "kblas.h"
    need(receipt["exact_library_sha256"] == KML_SHA and receipt["header_sha256"] == sha(header)
         and sha(header) == "eb34aa92122daaa109467955f8424a71d377f18629dbcdede280f7e6f6d028c1",
         "official header or binary identity differs")
    need(all(sha(path) == sha(header) for path in headers), "installed and exact-release headers disagree")
    (out / "HEADER_PROVENANCE.json").write_bytes(provenance)
    if headers:
        header = headers[0]
    common = ["/usr/bin/cc", "-I", str(header.parent)]
    preprocessed = record(out, "preprocess", [*common, "-E", "-P", "-x", "c", str(header)])
    declarations = re.findall(r"[^;{}]*\bcblas_sbgemm\s*\([^;]*\)\s*;", preprocessed.decode(), flags=re.S)
    need(len(declarations) == 1, "installed cblas_sbgemm declaration missing or ambiguous")
    declaration = " ".join(declarations[0].split())
    (out / "kblas.h").write_bytes(header.read_bytes())
    (out / "cblas_sbgemm.declaration.txt").write_text(declaration + "\n")
    need(len(re.findall(r"\bfloat\b", declaration)) == 3
         and re.search(r"(?:bf16|bfloat16)", declaration, flags=re.I),
         "installed header does not declare BF16 operands and FP32 alpha, beta and C")
    private = out / "libs10_qkv_dw.so"
    record(out, "compile", [*common, "-std=gnu11", "-march=armv8.6-a+bf16", "-O2", "-fPIC", "-shared", "-Wall", "-Wextra",
                            "-Werror", "-Wl,-z,defs", f"-Wl,-rpath,{library.parent}",
                            "-Wl,-rpath-link,/opt/HPCKit/bisheng-lib",
                            str(root / "s10_qkv_dw.c"), str(library), "-o", str(private)])
    save(out / "compiled_identity.json", dict(header=str(header), header_sha256=sha(header),
         declaration=declaration, kml_sha256=KML_SHA, source_sha256=sha(root / "s10_qkv_dw.c"),
         private_library_sha256=sha(private), path=str(private)))
    return private
