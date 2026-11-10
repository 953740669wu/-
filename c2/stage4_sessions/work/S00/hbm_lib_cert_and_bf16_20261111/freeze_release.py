"""Freeze an isolated real-corpus release against job 2085664's original five-step chain."""
import ast
from datetime import datetime, timedelta, timezone
from difflib import unified_diff
from hashlib import sha256
import json
import os
from pathlib import Path
import sys
from zipfile import ZIP_DEFLATED, ZipFile

HERE = Path(__file__).resolve().parent
BASE = HERE.parent / "external_fp32_attn_ab_r1_20261110/namespace_continue_20261110/M1_NS1_D1"
START = datetime.fromisoformat("2026-11-10T17:47:30+00:00")
ROOT = "/home/share/wujunyi/opt/stage4_sessions/S00"


def sha(raw):
    return sha256(raw).hexdigest()


def read(path):
    return json.loads(path.read_bytes())


def write(path, data):
    path.write_bytes((json.dumps(data, sort_keys=True, indent=2) + "\n").encode())


def replace(code, old, new):
    if code.count(old) != 1:
        raise ValueError("source anchor absent or ambiguous: " + old)
    return code.replace(old, new)


def launch(code):
    code = replace(code, 'from hbm_gate import execute, prepare_hbm, free_pages',
                   'from hbm_gate import execute, prepare_hbm, free_pages\nfrom hbm_selection import bound_selection, select')
    code = replace(code, '        if variant == "candidate":\n            env.update(S00_ATTN_BUILD=str(EVIDENCE/"ATTN_BUILD.json"), KML_ATTN_BF16="0")',
                   '''        requested = binding["hbm_selections"][variant]["HBM_LIB"]
        if requested is not None:
            env["HBM_LIB"] = requested
        if variant == "candidate" and binding["mode"] == "bf16_bq16":
            env.update(S00_ATTN_BUILD=str(EVIDENCE/"ATTN_BUILD.json"), KML_ATTN_BF16="1")''')
    code = replace(code, '    save(out / "phase_receipt.json", dict(status=expected', '''    for node in contracts:
        cfg = placements[node]
        residency = out / f"node{node}" / ("strict_end.numa_maps" if name == "strict" else "observe_end.numa_maps")
        resident = 0
        for line in residency.read_text().splitlines():
            fields = line.split()
            if "huge" not in fields:
                continue
            target = cfg["hbm_node"]
            need("kernelpagesize_kB=2048" in fields and f"bind:{target}" in fields, "wrong HBM page size or policy")
            by_node = {int(n):int(v) for n,v in re.findall(r"\\bN(\\d+)=(\\d+)\\b", line)}
            need(not set(by_node) - {target}, "HBM resident on an unpaired domain")
            resident += 2 * by_node.get(target, 0)
        save(out / f"node{node}.hbm_residency.json", dict(resident_MiB=resident, cap_MiB=cfg["cap_MiB"],
             node=cfg["hbm_node"], page_kB=2048, source=str(residency.relative_to(EVIDENCE))))
        need(0 < resident <= cfg["cap_MiB"], "positive bounded HBM residency required")
    save(out / "phase_receipt.json", dict(status=expected''')
    code = replace(code, '    library = EVIDENCE/"libfp32_attn.so"', '    library = EVIDENCE/"libbf16_attn.so"')
    code = replace(code, 'openmp=omp,bq=64,bf16=0', 'openmp=omp,bq=16,bf16=1')
    code = replace(code, 'def stop(signum, _):', '''def check_rejections():
    for label, request, expected in (
        ("missing", "missing_allocator.so", "missing"),
        ("wrong_sha", "wrong_sha.so", "sha256"),
        ("outside", "../FROZEN_HBM_ALLOCATOR.so", "outside_private_lib"),
    ):
        actual = None
        try:
            select(ROOT, request)
        except ValueError as exc:
            actual = str(exc)
        save(EVIDENCE / f"HBM_LIB_rejection_{label}.json", dict(requested=request,
             reason=actual, expected=expected, before_any_worker=True, passed=actual == expected))
        need(actual == expected, f"incorrect HBM_LIB rejection: {label}")


def stop(signum, _):''')
    code = replace(code, '        need(120 < wall <= 7200 and binding["mode"] == "external_fp32_attn_ab", "wrong wall or mode")',
                   '''        cert = binding["mode"] == "hbm_lib_cert"
        count = binding["domain_count"]
        need((cert and count == 1 or binding["mode"] == "bf16_bq16" and count in (1,4))
             and 120 < wall <= (1800 if count == 1 else 7200), "wrong wall or mode")
        need(binding["max_model_updates"] == 10*count + 50*count*binding["pairs"], "wrong update bound")''')
    code = replace(code, '''        build_attention(binding, end)
        placements = prepare_hbm(ROOT, EVIDENCE, contracts, binding, end)
        outcome["hbm_safety"] = "CAPACITY_AND_ALLOCATOR_IDENTITY_PASS"
        for variant in ("baseline","candidate"):
            outcome["active_phase"] = f"strict_{variant}"''', '''        selections = bound_selection(ROOT, binding)
        if cert:
            need(selections["baseline"]["HBM_LIB"] is None and selections["candidate"]["HBM_LIB"] is not None,
                 "default/explicit ordering required")
            check_rejections()
        else:
            need(selections["baseline"] == selections["candidate"], "BF16 pair must use one HBM selection")
            build_attention(binding, end)
        outcome["hbm_safety"] = "CAPACITY_AND_ALLOCATOR_IDENTITY_PASS"
        for variant in ("baseline","candidate"):
            outcome["active_phase"] = f"strict_{variant}"
            if cert or not placements:
                placements = prepare_hbm(ROOT, EVIDENCE, contracts,
                                         dict(binding, **selections[variant]), end,
                                         variant if cert else "candidate")''')
    return code


def hbm_gate(code):
    code = replace(code, 'def prepare_hbm(root, evidence, contracts, binding, deadline):',
                   'def prepare_hbm(root, evidence, contracts, binding, deadline, side):')
    code = replace(code, '    library = evidence / "libhbm_alloc_s03_round2.so"', '''    location = evidence if side == "baseline" else evidence / "hbm_lib_explicit"
    location.mkdir(exist_ok=True)
    library = location / ("libhbm_alloc_s03_round2.so" if side == "baseline" else source.name)''')
    code = replace(code, '"allocator_ldd"', 'f"allocator_ldd_{side}"')
    code = replace(code, '"allocator_ldd.log"', 'f"allocator_ldd_{side}.log"')
    return replace(code, 'save(evidence / "allocator_identity.json", dict(source=str(source), sha256=sha(library),',
                   '''save(evidence / f"allocator_identity_{side}.json", dict(requested=binding["HBM_LIB"],
         source=str(source), final_preload=str(library), sha256=sha(library),''')


def worker(code):
    code = replace(code, '''    paths = {line.split()[-1] for line in Path("/proc/self/maps").read_text().splitlines()
             if "libhbm_alloc" in line}
''', '''    maps = Path("/proc/self/maps").read_text()
    (args.output / "after_framework.maps").write_text(maps)
    paths = {line.split()[-1] for line in maps.splitlines() if "libhbm_alloc" in line}
''')
    code = replace(code, 'hbm = dict(path=library, sha256=data.sha(library), node=int(os.environ["HBM_NODE"]),',
                   'hbm = dict(path=library, requested=os.environ.get("HBM_LIB"), sha256=data.sha(library), node=int(os.environ["HBM_NODE"]),')
    code = replace(code, '    if args.variant == "candidate":\n        from attn_dispatch import Dispatch',
                   '    if "S00_ATTN_BUILD" in os.environ:\n        from attn_dispatch import Dispatch')
    code = replace(code, 'counts=attention.counts, bf16=0, bq=64', 'counts=attention.counts, bf16=1, bq=16')
    code = replace(code, '    finish_backend(runtime, expected)', '''    maps = Path("/proc/self/maps").read_text()
    (args.output / "publish.maps").write_text(maps)
    if hbm and ({line.split()[-1] for line in maps.splitlines() if "libhbm_alloc" in line} != {hbm["path"]}
                or data.sha(hbm["path"]) != hbm["sha256"]):
        raise ValueError("HBM mapping changed before publication")
    finish_backend(runtime, expected)''')
    return code.replace("strict DDR snapshot", "strict reference snapshot").replace("frozen DDR strict reference", "frozen strict reference")


def prepare(code):
    code = replace(code, 'root.name.startswith("ATTN_R1_")', 'root.name.startswith("HBM_CERT_20261111_")')
    return replace(code, '    verify(ROOT, sys.argv[1])',
                   '    from hbm_selection import bound_selection\n    bound_selection(ROOT, verify(ROOT, sys.argv[1]))')


def freeze(version, mode, count, host, ordinal, queue_left):
    base_binding = read(BASE / "RUN_BINDING.json")
    manifest = read(BASE / "SOURCE_SHA256.json")
    base_zip = BASE / "FULL16_PAYLOAD.zip"
    assert sha(base_zip.read_bytes()) == base_binding["package_sha256"]
    assert sha((BASE / "SOURCE_SHA256.json").read_bytes()) == base_binding["source_manifest_sha256"]
    with ZipFile(base_zip) as z:
        assert len(z.namelist()) == len(manifest) + 1 and set(z.namelist()) == set(manifest) | {"SOURCE_SHA256.json"}
        source = {name:z.read(name) for name in manifest}
    assert all(sha(raw) == manifest[name] for name,raw in source.items())
    cert = mode == "hbm_lib_cert"
    assert (cert and count == 1 or mode == "bf16_bq16" and count in (1,4)) and 1 <= ordinal <= 4
    diffs = []
    changes = {"launch.py":launch, "hbm_gate.py":hbm_gate, "payload/worker.py":worker, "prepare.py":prepare}
    for name, change in changes.items():
        old = source[name].decode()
        new = change(old)
        source[name] = new.encode()
        diffs.extend(unified_diff(old.splitlines(True),new.splitlines(True),f"a/{name}",f"b/{name}"))
    for name in ("kml_attn.c", "payload/attn_dispatch.py"):
        old = source.pop(name).decode()
        new = "" if cert else (HERE / "bf16_source" / name).read_text(encoding="utf-8")
        if new:
            source[name] = new.encode()
        diffs.extend(unified_diff(old.splitlines(True),new.splitlines(True),f"a/{name}",f"b/{name}" if new else "/dev/null"))
    source["hbm_selection.py"] = (HERE / "hbm_selection.py").read_bytes().replace(b"\r\n", b"\n")
    diffs.extend(unified_diff([], source["hbm_selection.py"].decode().splitlines(True), "/dev/null", "b/hbm_selection.py"))
    out = HERE / version
    out.mkdir()
    binding = {k:v for k,v in base_binding.items() if k not in {"external_kernel_sha256", "external_kml_ops_sha256",
        "unchanged_math_body_sha256", "dispatch_sha256", "kernel_source_sha256", "math_candidate", "review_sha256"}}
    for name, expected in binding["frozen_sidecars"].items():
        data = (BASE / name).read_bytes()
        assert sha(data) == expected
        (out / name).write_bytes(data)
    allocator = (out / "FROZEN_HBM_ALLOCATOR.so").read_bytes()
    assert sha(allocator) == binding["allocator_sha256"]
    explicit = os.environ["HBM_LIB"]
    assert explicit == "libhbm_alloc_explicit.so"
    source["lib/" + explicit] = allocator
    if cert:
        source["lib/wrong_sha.so"] = b"deliberately unapproved private bytes, never preload\n"
    diff = out / "MINIMAL.diff"
    diff.write_bytes("".join(diffs).encode())
    write(out / "SOURCE_SHA256.json", {name:sha(raw) for name,raw in source.items()})
    with ZipFile(out / "FULL16_PAYLOAD.zip", "x", ZIP_DEFLATED) as z:
        for name, raw in sorted(source.items()):
            if name.endswith(".py"):
                ast.parse(raw, filename=name, feature_version=(3,9))
            if name.endswith((".py", ".sh", ".c")):
                assert b"\r" not in raw
            z.writestr(name, raw)
        z.writestr("SOURCE_SHA256.json", (out / "SOURCE_SHA256.json").read_bytes())
    for name in ("hbm_selection.py", "prepare.py"):
        (out / name).write_bytes(source[name])
    remote = ROOT + "/HBM_CERT_20261111_" + version
    argv = [arg.replace(binding["remote_root"],remote) for arg in binding["native_argv"]]
    wall, pairs = (1800,0) if count == 1 else (7200,3)
    memory = 24576*count
    for flag, value in {"-nl":f"{host} !cn21341 !cn22044", "-R":f"cpu={38*count},mem={memory}MB", "-RL":f"mem={memory}MB",
                        "-a":f"numa[count={count},distribution=pack]", "-T":str(wall)}.items():
        argv[argv.index(flag)+1] = value
    origins = {side:dict(HBM_LIB=None if cert and side == "baseline" else explicit,
                         allocator_origin=remote + ("/FROZEN_HBM_ALLOCATOR.so" if cert and side == "baseline" else "/lib/" + explicit),
                         allocator_sha256=sha(allocator)) for side in ("baseline", "candidate")}
    binding["allocation_contract"].update(DDR_limit_MB=memory,DDR_request_MB=memory,allocated_cpus=38*count,
          compute_cpus=36*count,domains=count,reserved_cpus=2*count,HBM_max_MiB_total=3800*count)
    binding.update(version=version, engineering_revision="HBM_LIB_REAL_ENGINEERING_R1", remote_root=remote,
        allocator_origin=origins["candidate"]["allocator_origin"], hbm_selections=origins,
        archived_base_job="2085664", archived_base_package_sha256=base_binding["package_sha256"],
        mode=mode, domain_count=count, eligible_hosts=[host], native_argv=argv, wall_seconds=wall,
        pairs=pairs, first_pair_projection_seconds=0 if not pairs else 1600,
        max_model_updates=10*count+50*count*pairs, submission_ordinal=ordinal, remaining_queue_seconds=queue_left,
        batch_deadline_utc=(START+timedelta(hours=48)).isoformat(), diff_sha256=sha(diff.read_bytes()),
        strict_storage_min_bytes=count*base_binding["strict_storage_min_bytes"],
        source_manifest_sha256=sha((out/"SOURCE_SHA256.json").read_bytes()), package_sha256=sha((out/"FULL16_PAYLOAD.zip").read_bytes()))
    if not cert:
        cert_receipt = HERE / "HBM_LIB_CERT_RESULT.json"
        assert read(cert_receipt)["status"] == "PASS_HBM_LIB_CERT"
        binding.update(hbm_cert_result_sha256=sha(cert_receipt.read_bytes()),kernel_source_sha256=sha(source["kml_attn.c"]),
                       dispatch_sha256=sha(source["payload/attn_dispatch.py"]))
    write(out / "RUN_BINDING.json", binding)
    print("RUN="+remote+"\nPIN="+sha((out/"RUN_BINDING.json").read_bytes())+"\nPKG="+binding["package_sha256"])


if __name__ == "__main__":
    v, mode, n, host, ordinal, queue = sys.argv[1:]
    freeze(v, mode, int(n), host, int(ordinal), int(queue))
