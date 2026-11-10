"""Reuse frozen V2, with a namespace-aware receipt for its actual locking KML handle."""
import ast
from datetime import datetime, timezone
from difflib import unified_diff
from hashlib import sha256
import json
from pathlib import Path
import re
import sys
from zipfile import ZIP_DEFLATED, ZipFile

HERE=Path(__file__).resolve().parent
PREVIOUS=HERE.parent
V2=PREVIOUS/'V2_D1'
COORD=PREVIOUS.parent.parent/'COORDINATION'
REVIEW=COORD/'S00_FP32_ATTN_R1_REVIEW_20261110.json'


def sha(data):
    return sha256(data).hexdigest()


def read(path):
    return json.loads(path.read_bytes())


def write(path,value):
    path.write_bytes((json.dumps(value,sort_keys=True,indent=2)+'\n').encode())


def swap(code, old, new):
    if code.count(old)!=1:
        raise ValueError('source anchor absent or ambiguous: '+old)
    return code.replace(old,new)


def initialize():
    review=read(REVIEW)
    assert sha((PREVIOUS/'FP32_ATTN_AB_RESULT.json').read_bytes())==review['result_sha256']
    for file,digest in review['verified_refs'].items():
        assert sha(Path(file).read_bytes())==digest,file
    ledger=read(PREVIOUS/'BUDGET_LEDGER.json')
    assert (len(ledger['attempts']),ledger['allocation_seconds'],ledger['queue_seconds'],ledger['model_updates'])==(2,116,5,10)
    assert ledger['deadline_utc']=='2026-11-12T14:04:34+00:00'
    ledger.update(status='CONTINUING_NAMESPACE_REPAIR',
                  mathematical_candidates=[dict(id='M1_FP32_BQ64',previous_kernel_sha256=read(V2/'RUN_BINDING.json')['kernel_source_sha256'])],
                  engineering_revisions=[dict(id='CLOCK_HANDOFF',completed_job='2085051')])
    for name,data in [('BUDGET_LEDGER.json',ledger),('ACTIVE_JOB.json',dict(active_job=None,status='NO_ACTIVE_JOB_INITIAL_LIVE_QUEUE'))]:
        with (HERE/name).open('x',encoding='utf-8') as f:
            f.write(json.dumps(data,sort_keys=True,indent=2)+'\n')


def loader(code):
    code=swap(code,'#include <dlfcn.h>','#include <dlfcn.h>\n#include <link.h>')
    code=swap(code,'static sgemm_t sg;', 'static sgemm_t sg;\nstatic void *locking_handle;')
    return swap(code,'    sg = (sgemm_t)f; return 0;\n}', '''    locking_handle = h;
    sg = (sgemm_t)f; return 0;
}

int kml_attn_locking_info(void **handle, long *namespace_id, const char **path, void **gemm) {
    struct link_map *map = NULL;
    Lmid_t id = LM_ID_BASE;
    Dl_info symbol;
    void *symbol_map = NULL;
    if (!locking_handle || !sg || dlinfo(locking_handle, RTLD_DI_LMID, &id) != 0 || id == LM_ID_BASE ||
        dlinfo(locking_handle, RTLD_DI_LINKMAP, &map) != 0 || !map || !map->l_name || !*map->l_name ||
        !dladdr1((void *)sg, &symbol, &symbol_map, RTLD_DL_LINKMAP) || symbol_map != map)
        return -1;
    *handle = locking_handle;
    *namespace_id = id;
    *path = map->l_name;
    *gemm = (void *)sg;
    return 0;
}''')


def dispatch(code):
    code=swap(code,"            raise RuntimeError('failed to load the distinct locking KML namespace')\n        v =",
              """            raise RuntimeError('failed to load the distinct locking KML namespace')
        self.locking_info = self.lib.kml_attn_locking_info
        self.locking_info.argtypes = [ctypes.POINTER(ctypes.c_void_p), ctypes.POINTER(ctypes.c_long),
                                      ctypes.POINTER(ctypes.c_char_p), ctypes.POINTER(ctypes.c_void_p)]
        self.locking_info.restype = ctypes.c_int
        self.namespace = self.locking_namespace()
        v =""")
    return swap(code,'    def check_maps(self):', '''    def locking_namespace(self):
        handle, namespace_id, path, gemm = ctypes.c_void_p(), ctypes.c_long(), ctypes.c_char_p(), ctypes.c_void_p()
        if self.locking_info(ctypes.byref(handle), ctypes.byref(namespace_id), ctypes.byref(path), ctypes.byref(gemm)):
            raise RuntimeError('cannot identify the actual isolated locking KML handle and SGEMM owner')
        expected = self.identity['locking_kml']
        if (not handle.value or namespace_id.value <= 0 or not path.value or not gemm.value
                or str(Path(path.value.decode()).resolve(strict=True)) != expected['path']):
            raise RuntimeError('isolated locking KML handle, namespace, or path differs')
        receipt = dict(**expected, namespace_id=namespace_id.value, handle=handle.value, gemm_address=gemm.value)
        if hasattr(self, 'namespace') and self.namespace != receipt:
            raise RuntimeError('isolated locking KML identity changed within worker')
        return receipt

    def check_maps(self):''')


def contract(code):
    code=swap(code,'def runtime_info():','def runtime_info(namespace_probe=None):')
    code=swap(code,'    libraries = {}\n    for path in paths:', '''    namespace = namespace_probe() if namespace_probe else None
    if namespace and namespace['path'] not in paths:
        raise ValueError('isolated locking KML is missing from actual process maps')
    libraries = {}
    for path in paths:''')
    return swap(code,'        lib = ctypes.CDLL(path, mode=os.RTLD_NOLOAD | os.RTLD_LOCAL)', '''        if namespace and path == namespace['path']:
            if info['sha256'] != namespace['sha256']:
                raise ValueError('mapped locking KML SHA differs')
            info.update(namespace)
            lib = ctypes.CDLL(path, handle=namespace['handle'])
        else:
            lib = ctypes.CDLL(path, mode=os.RTLD_NOLOAD | os.RTLD_LOCAL)''')


def guard(code):
    code=swap(code,'def checkpoint(state, name, torch=None):','def checkpoint(state, name, torch=None, namespace_probe=None):')
    return swap(code,'runtime=contract.runtime_info())','runtime=contract.runtime_info(namespace_probe))')


def worker(code):
    code=swap(code,'    attention = None\n    if args.variant', '    attention = namespace_probe = None\n    if args.variant')
    code=swap(code,'        attention.install()\n        result["attention"]',
              '        attention.install()\n        namespace_probe = attention.locking_namespace\n        result["attention"]')
    code=swap(code,'counts=attention.counts, bf16=0, bq=64,',
              'counts=attention.counts, bf16=0, bq=64, locking_namespace=attention.namespace,')
    for label in ('"after_backend"','f"before_{role}_{step}"','f"after_{role}_{step}"','"publish"'):
        code=swap(code,f'cpu36_guard.checkpoint(guard, {label}, torch)',
                  f'cpu36_guard.checkpoint(guard, {label}, torch, namespace_probe)')
    return code


def freeze(version, domains, host, wall, projection=0):
    assert re.fullmatch(r'M1_NS[1-9]_D(?:1|4|16)',version) and re.fullmatch(r'cn[0-9]+',host)
    assert domains in (1,4,16) and host not in ('cn21341','cn22044')
    ledger=read(HERE/'BUDGET_LEDGER.json')
    assert not read(HERE/'ACTIVE_JOB.json')['active_job'] and len(ledger['attempts'])<6
    assert 120<wall<=min(7200,21600-ledger['allocation_seconds']) and ledger['queue_seconds']<86400
    assert len({a['host'] for a in ledger['attempts'] if a.get('host')}|{host})<=3
    assert (datetime.fromisoformat(ledger['deadline_utc'])-datetime.now(timezone.utc)).total_seconds()>wall+120
    pairs=0 if domains==1 else 3
    cap=domains*(10+50*pairs)
    assert cap<=4000 and cap+ledger['model_updates']<=16000
    prior=None
    if domains>1:
        prior=read(HERE/f'{1 if domains==4 else 4}DOMAIN_GATE.json')
        assert prior['status']=='PASS' and projection>0 and projection*3+120<wall
    review=read(REVIEW)
    bind=read(V2/'RUN_BINDING.json')
    assert sha((V2/'RUN_BINDING.json').read_bytes())==review['verified_refs'][str(V2/'RUN_BINDING.json')]
    assert sha((V2/'FULL16_PAYLOAD.zip').read_bytes())==bind['package_sha256']
    manifest=read(V2/'SOURCE_SHA256.json')
    assert sha((V2/'SOURCE_SHA256.json').read_bytes())==bind['source_manifest_sha256']
    with ZipFile(V2/'FULL16_PAYLOAD.zip') as z:
        assert len(z.namelist())==len(manifest)+1 and set(z.namelist())==set(manifest)|{'SOURCE_SHA256.json'}
        sources={n:z.read(n) for n in manifest}
    assert all(sha(b)==manifest[n] for n,b in sources.items())
    math_marker=b'/* exp(x)'
    math_bytes=sources['kml_attn.c'].split(math_marker,1)[1]
    patches={'kml_attn.c':loader,'payload/attn_dispatch.py':dispatch,'payload/cpu36_contract.py':contract,
             'payload/cpu36_guard.py':guard,'payload/worker.py':worker}
    diff=[]
    for n,patch in patches.items():
        old=sources[n].decode(); new=patch(old)
        diff.extend(unified_diff(old.splitlines(True),new.splitlines(True),f'a/{n}',f'b/{n}'))
        sources[n]=new.encode()
    assert sources['kml_attn.c'].split(math_marker,1)[1]==math_bytes
    if prior:
        assert prior['kernel_source_sha256']==sha(sources['kml_attn.c']) and prior['dispatch_sha256']==sha(sources['payload/attn_dispatch.py'])
    out=HERE/version; out.mkdir()
    for name,digest in bind['frozen_sidecars'].items():
        data=(V2/name).read_bytes(); assert sha(data)==digest; (out/name).write_bytes(data)
    (out/'MINIMAL.diff').write_bytes(''.join(diff).encode())
    write(out/'SOURCE_SHA256.json',{n:sha(b) for n,b in sources.items()})
    with ZipFile(out/'FULL16_PAYLOAD.zip','x',ZIP_DEFLATED) as z:
        for n,data in sorted(sources.items()):
            if n.endswith('.py'):ast.parse(data,filename=n,feature_version=(3,9))
            assert b'\r' not in data or not n.endswith(('.py','.sh','.c'))
            z.writestr(n,data)
        z.writestr('SOURCE_SHA256.json',(out/'SOURCE_SHA256.json').read_bytes())
    remote=f'/home/share/wujunyi/opt/stage4_sessions/S00/ATTN_R1_{version}'
    cpus,mem=38*domains,24576*domains
    excluded=bind['excluded_hosts']
    argv=['dsub','-J','-q','q_hpcai','-x','job','-nl',' '.join([host]+['!'+h for h in excluded]),'-R',f'cpu={cpus},mem={mem}MB',
          '-RL',f'mem={mem}MB','-a',f'numa[count={domains},distribution=pack]','-T',str(wall),'--env','none','--cwd',remote,
          '-oo',remote+'/job.log','bash',remote+'/run_job.sh','BINDING_SHA256']
    last=read(V2/'ANALYSIS.json')['build']['locking_kml']
    bind.update(version=version,domain_count=domains,pairs=pairs,first_pair_projection_seconds=projection,max_model_updates=cap,
        strict_storage_min_bytes=domains*6*2**30,allocator_origin=remote+'/FROZEN_HBM_ALLOCATOR.so',
        remote_root=remote,eligible_hosts=[host],native_argv=argv,prior_locking_kml=prior['locking_kml'] if prior else last,
        remaining_queue_seconds=86400-ledger['queue_seconds'],wall_seconds=wall,submission_ordinal=len(ledger['attempts'])+1,
        source_manifest_sha256=sha((out/'SOURCE_SHA256.json').read_bytes()),package_sha256=sha((out/'FULL16_PAYLOAD.zip').read_bytes()),
        diff_sha256=sha((out/'MINIMAL.diff').read_bytes()),kernel_source_sha256=sha(sources['kml_attn.c']),
        dispatch_sha256=sha(sources['payload/attn_dispatch.py']),unchanged_math_body_sha256=sha(math_bytes),
        math_candidate='M1_FP32_BQ64',engineering_revision='NS1_ACTUAL_HANDLE',
        allocation_contract=dict(domains=domains,allocated_cpus=cpus,compute_cpus=36*domains,reserved_cpus=2*domains,
                                 DDR_request_MB=mem,DDR_limit_MB=mem,HBM_max_MiB_per_domain=3800,
                                 HBM_max_MiB_total=3800*domains,exclusive=True,GPU=0))
    write(out/'RUN_BINDING.json',bind)
    print('RUN='+remote+'\nPIN='+sha((out/'RUN_BINDING.json').read_bytes())+'\nPKG='+bind['package_sha256'])


if __name__=='__main__':
    if sys.argv[1]=='initialize':
        initialize()
    else:
        version,domains,host,wall,*projection=sys.argv[1:]
        freeze(version,int(domains),host,int(wall),*(int(x) for x in projection))
