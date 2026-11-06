"""Metadata/hash gate only; imports no NumPy/Torch and performs no training."""
import argparse
import json
from pathlib import Path
from data_gate import engineering_data as data

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--descriptor',type=Path,required=True);p.add_argument('--descriptor-sha256',required=True)
    p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    if a.output.exists():p.error('refuse existing inspection evidence')
    try:
        m=data.load_descriptor(a.descriptor,a.descriptor_sha256)
        result=dict(status='ENGINEERING_METADATA_HASH_GATE_PASS',protocol=data.PROTOCOL,**data.FLAGS,
                    identity=m['identity'],npz_arrays_read=False,framework_imported=False)
        code=0
    except data.SourceChanged as exc:result=dict(status='SOURCE_CHANGED',error=str(exc));code=2
    except Exception as exc:result=dict(status='DATA_NOT_READY',error=str(exc));code=2
    a.output.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8');print(json.dumps(result));raise SystemExit(code)
