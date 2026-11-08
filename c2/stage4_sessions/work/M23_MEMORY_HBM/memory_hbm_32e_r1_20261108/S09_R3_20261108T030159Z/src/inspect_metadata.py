"""Login-only original descriptor/hash gate; no framework or NPZ array imports."""
import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent/'payload'))
from data_gate import engineering_data as data
p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);args=p.parse_args()
if args.output.exists():p.error('refuse overwriting metadata evidence')
root=Path(__file__).resolve().parent
descriptor=root/'ENGINEERING_DESCRIPTOR.json'
metadata=data.load_descriptor(descriptor,json.loads((root/"M23_RUN_BINDING.json").read_bytes())["descriptor_sha256"])
result=dict(status='ENGINEERING_METADATA_HASH_GATE_PASS',identity=metadata['identity'],npz_arrays_read=False,framework_imported=False)
args.output.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8');print(result['status'])
