"""Stdlib metadata gate only; never imports a framework or declares NPZ verified."""
import argparse
import json
from pathlib import Path
import sys
import real_data

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--descriptor',type=Path)
    parser.add_argument('--descriptor-sha256')
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if args.output.exists():parser.error('refuse existing audit output')
    try:
        metadata=real_data.load_descriptor(args.descriptor,args.descriptor_sha256)
        result=dict(status='METADATA_READY_ONLY_NPZ_AND_MODEL_NOT_RUN',identity=metadata['identity'],
            train_units=len(metadata['units']['train']),val_units=len(metadata['units']['val']),val_status=metadata['val_status'])
        code=0
    except real_data.DataNotReady as exc:result=dict(status='DATA_NOT_READY',error=str(exc));code=2
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result,indent=2));sys.exit(code)
