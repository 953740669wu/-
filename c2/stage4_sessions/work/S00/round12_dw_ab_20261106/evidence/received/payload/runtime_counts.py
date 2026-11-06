"""Direct KML native counters; logical GEMM stays in the frozen counter."""
import ctypes
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parent
TARGET_KEY=str(([13312,512],[13312,2048],(),True,False))


def source_identity():
    path=ROOT/'SOURCE_SHA256.json';source=json.loads(path.read_text())
    for name,digest in source.items():
        if hashlib.sha256((ROOT/name).read_bytes()).hexdigest()!=digest:raise ValueError('source drift: '+name)
    return hashlib.sha256(path.read_bytes()).hexdigest()


def attach_native(module,capture=False):
    original=module._sgemm
    if not isinstance(original,ctypes._CFuncPtr):raise ValueError('actual ctypes KML function required; no Python substitute')
    state=dict(native_calls=0,target_full=0,target_tiles=0,native_shapes={},captured_target=[],original_type=type(original).__name__)
    def counted(*args,**kwargs):
        if kwargs or len(args)!=14:raise ValueError('original SGEMM ABI required')
        state['native_calls']+=1
        key=str(tuple(args[i] for i in (0,1,2,3,4,5,6,8,10,11,13)))
        state['native_shapes'][key]=state['native_shapes'].get(key,0)+1
        target=args[:3]==(101,112,111) and args[3]==512 and args[5]==13312 and args[6]==1. and args[8]==512 and args[10]==args[13]==2048 and args[11]==0.
        if target and args[4]==2048:state['target_full']+=1
        if target and args[4]==1024:state['target_tiles']+=1
        if capture and target:state['captured_target'].append(list(args))
        return original(*args,**kwargs)
    module._sgemm=counted
    return state


def verify_step(role,logical,target_logical,native,full,tiles):
    expected=(149,12,149,12,0) if role=='baseline' else (149,12,161,0,24)
    if (logical,target_logical,native,full,tiles)!=expected:raise ValueError('logical/native/tile dispatch count mismatch: '+repr((role,logical,target_logical,native,full,tiles)))
