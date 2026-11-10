"""Freeze only the external FP32 attention path and its authorized C2 entry."""
import ast
from datetime import datetime, timezone
from difflib import unified_diff
from hashlib import sha256
import json
from pathlib import Path
import re
import sys
from zipfile import ZIP_DEFLATED, ZipFile

HERE = Path(__file__).resolve().parent
R1 = HERE.parent/'full_node_16domain_hbm_ckpt_r1_20261108'
BASE = R1/'H2_32B32_A'
COORD = HERE.parent.parent/'COORDINATION'
EXT = Path('E:/eitfm_c2_stages2-4_2026-11-08')
REVIEW = COORD/'S11_REVIEW_ACCEPTANCE_20261110.json'


def sha(data):
    return sha256(data).hexdigest()


def read(path):
    return json.loads(path.read_bytes())


def write(path, value):
    path.write_bytes((json.dumps(value,sort_keys=True,indent=2)+'\n').encode())


def swap(code, old, new):
    if code.count(old) != 1:
        raise ValueError('source anchor absent or ambiguous: '+old)
    return code.replace(old,new)


def cut(code, first, last):
    start=code.index(first)
    return code[:start]+code[code.index(last,start):]


def fp32_kernel(original):
    # External FP32 fwd and default bwd verbatim except explicit error/bit handling.
    code=original.split('/* ---------------------------------------------------------------- bf16 variant',1)[0]
    code=cut(code,'/* Gradients of kml_attn_fwd, first version','/* Gradients of kml_attn_fwd (default)')
    code=cut(code,'    const char *e = getenv("KML_ATTN_BWD");','    view Q =')
    code=cut(code,'void kml_attn_init(void *f)', '/* The tiles need')
    code=cut(code,'typedef void (*sbgemm_t)', 'int kml_attn_load')
    code=swap(code,'    sg = (sgemm_t)f; sbg = (sbgemm_t)dlsym(h, "cblas_sbgemm"); return 0;\n}\nint kml_attn_has_bf16(void) { return sbg != 0; }',
              '    sg = (sgemm_t)f; return 0;\n}')
    code=swap(code,'   of q/k/v (any row stride, unit column stride) with a per-thread score buffer of BQ x Nk, so the N x N scores never',
              '   of q/k/v (row stride at least head width, unit column stride) with a per-thread score buffer of BQ x Nk, so the N x N scores never')
    code=swap(code,'   Tensors are addressed as x[b*s0 + h*s1 + n*s2 + i] (i < d). The sgemm pointer comes from Python\n   (kml_ops._sgemm, KML SME multi): called inside the parallel region it runs on the calling thread only.',
              '   Tensors are addressed as x[b*s0 + h*s1 + n*s2 + i] (i < d). Each tile calls the locking KML namespace.')
    code=swap(code,'(else sg is unchanged)', '(else the caller must stop)')
    code=swap(code,'int32_t i; memcpy(&i, &p, 4); i += (int32_t)n << 23;',
              'uint32_t i; memcpy(&i, &p, 4); i += (uint32_t)(int32_t)n << 23;')
    for direction in ('fwd','bwd'):
        code=swap(code,f'void kml_attn_{direction}(', f'int kml_attn_{direction}(')
        code=swap(code,f'    prof_print("{direction}", B, H, Nq, Nk, bq);',
                  f'    prof_print("{direction}", B, H, Nq, Nk, bq);\n    return failed ? -1 : 0;')
    code=swap(code,'    if (!D) return;', '    if (!D) return -1;')
    assert code.count('    #pragma omp parallel\n')==2
    code=code.replace('    #pragma omp parallel\n','    int failed = 0;\n    #pragma omp parallel reduction(|:failed)\n')
    code=swap(code,'if (posix_memalign((void **)&s, 64, sizeof(float) * (size_t)bq * Nk)) s = 0;',
              'if (posix_memalign((void **)&s, 64, sizeof(float) * (size_t)bq * Nk)) { s = 0; failed = 1; }')
    code=swap(code,'if (posix_memalign((void **)&p, 64, sizeof(float) * 2 * n)) p = 0;',
              'if (posix_memalign((void **)&p, 64, sizeof(float) * 2 * n)) { p = 0; failed = 1; }')
    return code


def adapt_worker(code):
    code=swap(code,'def runtime_check(runtime, hbm):','def runtime_check(runtime, hbm, attention=None):')
    code=swap(code,'    if "libraries_after" in runtime and runtime["libraries_after"] != expected["libraries"]:',
              '''    libraries = expected["libraries"]
    if attention:
        libraries = sorted(libraries + [attention.identity["locking_kml"]], key=lambda row: row["path"])
    if "libraries_after" in runtime and runtime["libraries_after"] != libraries:''')
    code=swap(code,'    if args.variant in ("candidate","ckpt_hbm"):', '    if args.variant in ("baseline","candidate"):')
    code=swap(code,'    runtime_check(runtime, hbm)\n    module', '''    runtime_check(runtime, hbm)
    attention = None
    if args.variant == "candidate":
        from attn_dispatch import Dispatch
        attention = Dispatch(os.environ["S00_ATTN_BUILD"])
        attention.install()
        result["attention"] = dict(build=attention.identity, counts=attention.counts, bf16=0, bq=64,
                                   shim_guard_present=attention.sm_guard is not None, fallback="prohibited")
    module''')
    code=swap(code,'                begin = time.monotonic_ns()',
              '                attn_before = dict(attention.counts) if attention else None\n                begin = time.monotonic_ns()')
    code=swap(code,'                end = time.monotonic_ns()\n                rss_after = memory_metrics.rss()',
              '''                end = time.monotonic_ns()
                rss_after = memory_metrics.rss()
                dispatch = None
                if attention:
                    dispatch = {k: v-attn_before[k] for k,v in attention.counts.items()}
                    if dispatch["forward"] < ckpt_layers or dispatch["backward"] != ckpt_layers:
                        raise RuntimeError("incomplete actual fused dispatch in model update: " + repr(dispatch))''')
    code=swap(code,'                                 native_shapes=dict(shapes), sampled=not strict and step >= 6))',
              '                                 native_shapes=dict(shapes), fused_attention=dispatch, sampled=not strict and step >= 6))')
    code=swap(code,'    finish_backend(runtime, expected)\n    runtime_check(runtime, hbm)',
              '''    if strict:
        residency(args.output, "strict_end")
    if attention:
        attention.check_maps()
    finish_backend(runtime, expected)
    runtime_check(runtime, hbm, attention)''')
    return code


def adapt_hbm(code):
    # Reuse the accepted allocator and capacity/return guards. No separate old probe matrix.
    code=cut(code,'def probe_placement(', 'def prepare_hbm(')
    code=cut(code,'    executable = evidence / "real_hbm_probe"','    topology = ')
    code=code[:code.index('    for node, contract in contracts.items():')]+'''    return {node: dict(hbm_node=pairs[str(node)], cap_MiB=cap, pool_pages_before=initial[str(node)],
                       library=str(library), library_sha256=sha(library)) for node in contracts}
'''
    return code


def wait_for_handoff_clock(code):
    code=swap(code, "    now = time.time()\n    if not (request['created_at'] <= header['generated_at'] <= now and now - header['generated_at'] <= 30):",
              """    first_clock_observation = now = time.time()
    catch_up = min(deadline, time.monotonic() + 5)
    while now < header['generated_at'] and time.monotonic() < catch_up:
        time.sleep(min(0.02, max(0, catch_up-time.monotonic())))
        now = time.time()
    if not (request['created_at'] <= header['generated_at'] <= now and now - header['generated_at'] <= 30):""")
    return swap(code, "nonce=request['nonce'], verified_at=now, raw_mtime_ns=after.st_mtime_ns)",
                "nonce=request['nonce'], verified_at=now, first_clock_observation=first_clock_observation,\n                raw_mtime_ns=after.st_mtime_ns)")


def adapt_launch(code):
    code=swap(code,'from hbm_gate import prepare_hbm, free_pages','from hbm_gate import execute, prepare_hbm, free_pages')
    code=swap(code,'from prepare import ROOT, need, save, verify','from prepare import ROOT, need, save, sha, verify')
    code=swap(code,'    placement = full_topology(cpu_nodes,{n:dict(zip(ids,row)) for n,row in distances.items()},contracts,targets)',
              '''    all_cpu_domains = {n for n,cpus in cpu_nodes.items() if cpus}
    placement = full_topology(cpu_nodes,{n:dict(zip(ids,row)) for n,row in distances.items()},all_cpu_domains,targets)
    need(count != 4 or sorted(contracts) in [list(g) for g in placement["die_groups"]],
         "actual four domains do not form a complete die")
    placement["hbm_pairs"] = {n:placement["hbm_pairs"][n] for n in contracts}''')
    code=swap(code,'    need(len({tuple(s) for r in contracts.values() for s in r["physical_siblings"].values()}) == 608,\n         "608 distinct physical cores required across dies")',
              '    need(len({tuple(s) for r in contracts.values() for s in r["physical_siblings"].values()}) == 38*count,\n         "distinct physical cores required across allocated domains")')
    code=swap(code,'    need(count == 16, "full node requires exactly 16 domains")','    need(count in (1,4,16), "invalid authorized domain count")')
    code=swap(code,'    need(raw["queue"] == "q_hpcai" and raw["execPath"] == str(ROOT)',
              '    need(raw["queue"] == "q_hpcai" and raw["execPath"] == str(ROOT) and raw["user"] == binding["scheduler_user"]')
    code=swap(code,'        if variant == "candidate":\n            cfg = placements[node]\n            need((free_pages(cfg["hbm_node"])-16)*2 >= cfg["cap_MiB"], "HBM pool became smaller after safety gate")\n            env.update(M23_HBM_LIBRARY=cfg["library"], M23_HBM_LIBRARY_SHA=cfg["library_sha256"],\n                       HBM_NODE=str(cfg["hbm_node"]), HBM_MB=str(cfg["cap_MiB"]), HBM_MIN_KB="256", HBM_STATS="1")',
              '''        cfg = placements[node]
        need((free_pages(cfg["hbm_node"])-16)*2 >= cfg["cap_MiB"], "HBM pool became smaller after capacity gate")
        env.update(M23_HBM_LIBRARY=cfg["library"], M23_HBM_LIBRARY_SHA=cfg["library_sha256"],
                   HBM_NODE=str(cfg["hbm_node"]), HBM_MB=str(cfg["cap_MiB"]), HBM_MIN_KB="256", HBM_STATS="1")
        if variant == "candidate":
            env.update(S00_ATTN_BUILD=str(EVIDENCE/"ATTN_BUILD.json"), KML_ATTN_BF16="0")''')
    code=swap(code,'def stop(signum, _):', '''def build_attention(binding, deadline):
    gomp = Path("/home/share/songzhenlong/eitfm/sw/torch_kml/torch.libs/libgomp-58a43326.so.1.0.0")
    locking = Path("/opt/HPCKit/kml-lib/sme/kblas/locking/libkblas.so").resolve(strict=True)
    library = EVIDENCE/"libfp32_attn.so"
    obj = EVIDENCE/"kml_attn.o"
    source = ROOT/"kml_attn.c"
    runtime = read(ROOT/"payload/RUNTIME_EXPECTED.json")
    omp, = [r for r in runtime["libraries"] if "libomp.so" in r["path"]]
    need(str(gomp.resolve(strict=True)) == omp["path"] and sha(gomp) == omp["sha256"],
         "C build must link the already verified Torch OpenMP runtime")
    execute(EVIDENCE,"cc_version",["/usr/bin/gcc","--version"],min(deadline,time.monotonic()+10))
    execute(EVIDENCE,"attn_compile",["/usr/bin/gcc","-O3","-mcpu=native","-fno-math-errno","-fopenmp",
            "-fPIC","-c",str(source),"-o",str(obj)],min(deadline,time.monotonic()+60))
    execute(EVIDENCE,"attn_link",["/usr/bin/gcc","-shared","-o",str(library),str(obj),str(gomp),"-ldl","-lm"],
            min(deadline,time.monotonic()+30))
    locking_id = dict(path=str(locking),sha256=sha(locking))
    if binding.get("prior_locking_kml"):
        need(locking_id == binding["prior_locking_kml"], "locking KML differs from admitted prior phase")
    save(EVIDENCE/"ATTN_BUILD.json",dict(source_sha256=sha(source),library=dict(path=str(library),sha256=sha(library)),
         locking_kml=locking_id,openmp=omp,bq=64,bf16=0))


def stop(signum, _):''')
    begin=code.index('        need(120 < wall <= 7200 and binding["mode"]')
    end=code.index('        need(shutil.disk_usage',begin)
    code=code[:begin]+'''        need(120 < wall <= 7200 and binding["mode"] == "external_fp32_attn_ab", "wrong wall or mode")
        rounds = binding["pairs"]
        need(rounds == (0 if binding["domain_count"] == 1 else 3), "invalid pair plan")
'''+code[end:]
    code=swap(code,'        placements = prepare_hbm(ROOT, EVIDENCE, contracts, binding, end)\n        outcome["hbm_safety"] = "PASS"',
              '''        build_attention(binding, end)
        placements = prepare_hbm(ROOT, EVIDENCE, contracts, binding, end)
        outcome["hbm_safety"] = "CAPACITY_AND_ALLOCATOR_IDENTITY_PASS"''')
    code=swap(code,'            phase("strict", variant, contracts, owner, binding, end, placements)\n            outcome',
              '            phase("strict", variant, contracts, owner, binding, end, placements)\n            verify_return(placements, f"strict_{variant}")\n            outcome')
    begin=code.index('        verify_return(placements, "strict")')
    end=code.index('        outcome["active_phase"] = None',begin)
    return code[:begin]+'''        dispose_snapshots()
        outcome["completed_pairs"] = []
        estimate = binding["first_pair_projection_seconds"]
        for run in range(1, rounds+1):
            if end-time.monotonic() < estimate*(rounds-run+1):
                raise TimeoutError("remaining wall cannot fit all complete paired rounds and cleanup")
            t0 = time.monotonic()
            order = ("baseline","candidate") if run % 2 else ("candidate","baseline")
            for variant in order:
                label = f"perf_{variant}_r{run}"
                outcome["active_phase"] = label
                phase("perf", variant, contracts, owner, binding, end, placements, run)
                verify_return(placements, label)
                outcome["steps"][label+"_each_domain"] = 25
            outcome["completed_pairs"].append(run)
            estimate = (time.monotonic()-t0)*1.15 + 20
'''+code[end:]


def freeze(version, domains, host, wall, projection=0):
    assert re.fullmatch(r'V[12]_D(?:1|4|16)(?:_[A-Z0-9]+)?',version) and re.fullmatch(r'cn[0-9]+',host)
    assert domains in (1,4,16) and host not in ('cn21341','cn22044')
    l=read(HERE/'BUDGET_LEDGER.json')
    assert not read(HERE/'ACTIVE_JOB.json')['active_job'] and len(l['attempts'])<6
    assert 120<wall<=min(7200,21600-l['allocation_seconds']) and l['queue_seconds']<86400
    assert len({a['host'] for a in l['attempts'] if a.get('host')}|{host})<=3
    assert (datetime.fromisoformat(l['deadline_utc'])-datetime.now(timezone.utc)).total_seconds()>wall+120
    pairs=0 if domains==1 else 3
    cap=domains*(10+50*pairs)
    assert cap<=4000 and cap+l['model_updates']<=16000
    prior=None
    if domains>1:
        prior=read(HERE/f'{1 if domains==4 else 4}DOMAIN_GATE.json')
        assert prior['status']=='PASS' and projection>0 and projection*3+120<wall
    audit=read(REVIEW)
    for n in ('REVIEW.md','VERSION_MAP.json'):
        r=audit['s11_deliverables'][n]; b=Path(r['path']).read_bytes()
        assert len(b)==r['bytes'] and sha(b)==r['sha256']
    for p in (EXT/'kml_ops.py',EXT/'c2/opt/kml_attn.c'):
        assert sha(p.read_bytes())==audit['verified_source_refs'][str(p)]
    assert sha((R1/'FULL_NODE_16DOMAIN_RESULT.json').read_bytes())==read(COORD/'S00_FULL16_REVIEW_20261110.json')['result_sha256']
    s09=read(COORD/'S09_32E_RESULT_REVIEW_20261108.json')
    assert sha(Path(s09['delivery_path']).read_bytes())==s09['delivery_sha256']
    binding=read(BASE/'RUN_BINDING.json')
    assert sha((BASE/'RUN_BINDING.json').read_bytes())==read(COORD/'S00_FULL16_REVIEW_20261110.json')['verified_references'][str(BASE/'RUN_BINDING.json')]
    assert sha((BASE/'FULL16_PAYLOAD.zip').read_bytes())==binding['package_sha256']
    manifest=read(BASE/'SOURCE_SHA256.json')
    assert sha((BASE/'SOURCE_SHA256.json').read_bytes())==binding['source_manifest_sha256']
    with ZipFile(BASE/'FULL16_PAYLOAD.zip') as z:
        assert len(z.namelist())==len(manifest)+1 and set(z.namelist())==set(manifest)|{'SOURCE_SHA256.json'}
        sources={n:z.read(n) for n in manifest}
    assert all(sha(b)==manifest[n] for n,b in sources.items())
    diff=[]
    patches={'launch.py':adapt_launch,'hbm_gate.py':adapt_hbm,'payload/worker.py':adapt_worker,
      'prepare.py':lambda c:swap(swap(c,'FULL16_R1_','ATTN_R1_'),'/home/share/dengqingtian/opt/stage4_sessions/S00','/home/share/wujunyi/opt/stage4_sessions/S00'),
      'run_job.sh':lambda c:swap(c,'HOME=/home/share/dengqingtian USER=dengqingtian','HOME=/home/share/wujunyi USER=wujunyi'),
      'submit_once.py':lambda c:swap(swap(c,'    return (row["execPath"]','    return (row["user"] == binding["scheduler_user"] and row["execPath"]'),
                                     '16*(binding["hbm_cap_MiB"]//2+16)','binding["domain_count"]*(binding["hbm_cap_MiB"]//2+16)')}
    if version.startswith('V2_'):
        assert (HERE/'V1_D1/ANALYSIS.json').is_file()
        assert 'stale/future scheduler handoff' in read(HERE/'V1_D1/ANALYSIS.json')['application']['error']
        patches['scheduler_handoff.py']=wait_for_handoff_clock
    for n, patch in patches.items():
        old=sources[n].decode(); new=patch(old)
        diff.extend(unified_diff(old.splitlines(True),new.splitlines(True),f'a/{n}',f'b/{n}'))
        sources[n]=new.encode()
    old=(EXT/'c2/opt/kml_attn.c').read_text(encoding='utf-8'); new=fp32_kernel(old)
    diff.extend(unified_diff(old.splitlines(True),new.splitlines(True),'a/external/c2/opt/kml_attn.c','b/kml_attn.c'))
    sources['kml_attn.c']=new.encode()
    dispatch=(HERE/'attn_dispatch.py').read_text(encoding='utf-8')
    diff.extend(unified_diff([],dispatch.splitlines(True),'/dev/null','b/payload/attn_dispatch.py'))
    sources['payload/attn_dispatch.py']=dispatch.encode()
    if prior:
        assert prior['kernel_source_sha256']==sha(sources['kml_attn.c']) and prior['dispatch_sha256']==sha(sources['payload/attn_dispatch.py'])
    out=HERE/version
    out.mkdir()
    for name,digest in binding['frozen_sidecars'].items():
        data=(BASE/name).read_bytes(); assert sha(data)==digest
        (out/name).write_bytes(data)
    name='FROZEN_HBM_ALLOCATOR.so'; data=(BASE/'received/job_evidence/libhbm_alloc_s03_round2.so').read_bytes()
    assert sha(data)==binding['allocator_sha256']; (out/name).write_bytes(data)
    binding['frozen_sidecars'][name]=sha(data)
    (out/'MINIMAL.diff').write_bytes(''.join(diff).encode())
    write(out/'SOURCE_SHA256.json',{n:sha(b) for n,b in sources.items()})
    with ZipFile(out/'FULL16_PAYLOAD.zip','x',ZIP_DEFLATED) as z:
        for n,b in sorted(sources.items()):
            assert b'\r' not in b or not n.endswith(('.py','.sh','.c'))
            if n.endswith('.py'):
                ast.parse(b,filename=n,feature_version=(3,9))
            z.writestr(n,b)
        z.writestr('SOURCE_SHA256.json',(out/'SOURCE_SHA256.json').read_bytes())
    remote=f'/home/share/wujunyi/opt/stage4_sessions/S00/ATTN_R1_{version}'
    excluded=['cn21341','cn22044']
    cpus,mem=38*domains,24576*domains
    argv=['dsub','-J','-q','q_hpcai','-x','job','-nl',' '.join([host]+['!'+h for h in excluded]),'-R',f'cpu={cpus},mem={mem}MB',
          '-RL',f'mem={mem}MB','-a',f'numa[count={domains},distribution=pack]','-T',str(wall),'--env','none','--cwd',remote,
          '-oo',remote+'/job.log','bash',remote+'/run_job.sh','BINDING_SHA256']
    for k in ('first_hbm_round','hbm_rounds_max','ddr_perf_control'):
        del binding[k]
    binding.update(version=version,mode='external_fp32_attn_ab',scheduler_user='wujunyi',domain_count=domains,
        pairs=pairs,first_pair_projection_seconds=projection,max_model_updates=cap,strict_storage_min_bytes=domains*6*2**30,
        allocator_origin=remote+'/'+name,remote_root=remote,eligible_hosts=[host],excluded_hosts=excluded,native_argv=argv,
        prior_locking_kml=prior['locking_kml'] if prior else None,batch_deadline_utc=l['deadline_utc'],
        remaining_queue_seconds=86400-l['queue_seconds'],wall_seconds=wall,submission_ordinal=len(l['attempts'])+1,
        source_manifest_sha256=sha((out/'SOURCE_SHA256.json').read_bytes()),package_sha256=sha((out/'FULL16_PAYLOAD.zip').read_bytes()),
        diff_sha256=sha((out/'MINIMAL.diff').read_bytes()),kernel_source_sha256=sha(sources['kml_attn.c']),
        dispatch_sha256=sha(sources['payload/attn_dispatch.py']),review_sha256=audit['s11_deliverables']['REVIEW.md']['sha256'],
        external_kernel_sha256=sha((EXT/'c2/opt/kml_attn.c').read_bytes()),external_kml_ops_sha256=sha((EXT/'kml_ops.py').read_bytes()),
        allocation_contract=dict(domains=domains,allocated_cpus=cpus,compute_cpus=36*domains,reserved_cpus=2*domains,
                                 DDR_request_MB=mem,DDR_limit_MB=mem,HBM_max_MiB_per_domain=3800,
                                 HBM_max_MiB_total=3800*domains,exclusive=True,GPU=0))
    write(out/'RUN_BINDING.json',binding)
    print('RUN='+remote+'\nPIN='+sha((out/'RUN_BINDING.json').read_bytes())+'\nPKG='+binding['package_sha256'])


if __name__=='__main__':
    version,domains,host,wall,*projection=sys.argv[1:]
    freeze(version,int(domains),host,int(wall),*(int(x) for x in projection))
