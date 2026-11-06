"""Read-only fixed small-unit selection/checks on C2 login; no Torch or training."""
import collections
import csv
import datetime
import hashlib
import io
import json
import os
from pathlib import Path
import random
import signal
import socket
import subprocess
import sys

ROOT=Path('/home/share/songzhenlong/eitfm/corpus_shape_20261102')
ANCHOR='bdd146040bddf2ddd47fb9d571d5d2f40e5fa20fbd30d0c0d11239893e647032'
OWNER=Path('/home/share/dengqingtian/opt/stage4_sessions/S00')
result=dict(status='STARTED',engineering_only=True,formal_split_status='UNKNOWN',
 validation_status='NOT_RUN_NO_FORMAL_SPLIT',subject_mapping_status='UNKNOWN',
 started_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),host=socket.gethostname(),
 jobs_submitted=0,selected=[],training_consumed=False)


def require(ok,message):
    if not ok:raise ValueError(message)


def read(path):
    before=path.stat();b=path.read_bytes();after=path.stat()
    require((before.st_size,before.st_mtime_ns)==(after.st_size,after.st_mtime_ns),'SOURCE_CHANGED: '+str(path))
    return b,dict(path=str(path),bytes=len(b),sha256=hashlib.sha256(b).hexdigest(),mtime_ns=after.st_mtime_ns)


def main():
    q=subprocess.run(['djob','-J'],stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=8)
    result['queue']=dict(command=['djob','-J'],returncode=q.returncode,stdout=q.stdout.decode(),stderr=q.stderr.decode())
    require(q.returncode==0,'queue read failed')
    entries=sorted(OWNER.iterdir(),key=lambda p:p.name)
    result['owner_directory_names']=[p.name for p in entries]
    result['existing_engineering_records']=[]
    for d in entries:
        if d.is_dir() and any(k in d.name.upper() for k in ('ENGINEER','OVERNIGHT','REAL_TRAIN')):
            row=dict(directory=str(d),files=sorted(p.name for p in d.iterdir())[:100])
            for name in ('job_id.txt','submit_once.marker','submission.stdout','submission.result.json'):
                if (d/name).is_file():row[name]=(d/name).read_text(errors='replace')[:2000]
            result['existing_engineering_records'].append(row)
    require(not result['existing_engineering_records'],'existing engineering directory: inspect without selecting again')
    raw,identity=read(ROOT/'manifest.csv')
    require(identity['bytes']==3399057 and identity['sha256']==ANCHOR,'SOURCE_CHANGED: engineering manifest anchor')
    rows=list(csv.DictReader(io.StringIO(raw.decode('utf-8-sig'))))
    require(len(rows)==14300 and sum(int(r['n_pairs']) for r in rows)==1430000,'manifest count changed')
    require(len({r['unit'] for r in rows})==len(rows),'duplicate manifest unit')
    case_raw,case_identity=read(ROOT/'cases.txt');original=sorted(set(case_raw.decode().split()))
    require(case_identity['sha256']=='f0a3c5bd443b63f06dc69c8bed5e58dd50999a91fddb5222f0c38594ba92d836' and len(original)==119,'original engineering case-range list changed')
    groups=collections.defaultdict(list)
    for row in rows:
        if row['case'] in original and row['belt']=='16_adjacent' and row['status']=='done' and row['finite']=='True' and int(row['n_pairs'])==100:
            groups[row['case']].append(row)
    candidates=sorted(k for k,v in groups.items() if len(v)>=8)
    require(len(candidates)>=2,'not enough engineering candidate cases; no expansion')
    rng=random.Random(2026);chosen=sorted(rng.sample(candidates,2));selected=[]
    for case in chosen:
        units=sorted(groups[case],key=lambda r:r['unit'])
        selected.extend(sorted(rng.sample(units,8),key=lambda r:r['unit']))
    result.update(manifest=identity,original_case_range=case_identity,candidate_cases=candidates,
      selected_cases=chosen,selection_seed=2026,
      selection_algorithm='Python Random(2026): sample2 sorted eligible original-case IDs; sort chosen cases; sample8 sorted16_adjacent units for each with same RNG; sort chosen units; no replacement/fallback',
      selection_scope='original cases.txt is only engineering case range, NEVER subject split',
      metadata_candidate_eligibility='manifest original-case membership,16_adjacent,done,finite=True,n_pairs100,at least8units; selected payload failure stops without replacement')
    import numpy as np
    result['numpy']=dict(version=np.__version__,file=np.__file__,python=sys.executable)
    drives=np.array([(i,(i+1)%16) for i in range(16)],dtype=np.int16)
    meas=np.array([(i,j) for i,d in enumerate(drives) for j,m in enumerate(drives) if not(set(d)&set(m))],dtype=np.int16)
    for row in selected:
        unit=row['unit'];path=ROOT/'parts'/row['file'];side=path.with_suffix('.json')
        require(path.stem==unit and row['file']==unit+'.npz','unit path mismatch')
        item=dict(unit=unit,case=row['case'],placement=int(row['placement']),contact=int(row['contact']),
          belt=row['belt'],n_pairs=int(row['n_pairs']),path=str(path),sidecar_path=str(side),
          code_hash=row['code_hash'],config_hash=row['config_hash'],subject_mapping_status='UNKNOWN',status='SELECTED_CHECKING')
        result['selected'].append(item)  # Keep identity even when a later read/check fails.
        raw_npz,npz_id=read(path);raw_side,side_id=read(side);meta=json.loads(raw_side)
        item.update(npz_sha256=npz_id['sha256'],sidecar_sha256=side_id['sha256'],npz_identity=npz_id,sidecar_identity=side_id)
        require(all(meta[k]==item[k] for k in ('unit','case','placement','contact','belt','n_pairs','code_hash','config_hash')),'sidecar/manifest identity mismatch')
        require(meta['L']==16 and meta['finite'] is True and item['code_hash']=='d8b2be8d1f' and item['config_hash']=='b1049eac1a','unit producer identity mismatch')
        with np.load(io.BytesIO(raw_npz),allow_pickle=False) as z:
            arrays={k:z[k] for k in ('v_ref','v_cur','images','base_of_pair','drives','meas')}
        ref,cur,img,base=(arrays[k] for k in ('v_ref','v_cur','images','base_of_pair'))
        require(ref.shape==(5,208) and cur.shape==(100,208) and img.shape==(100,64,64) and base.shape==(100,),'training schema/count mismatch')
        require(ref.dtype==cur.dtype==np.float32 and img.dtype in (np.float16,np.float32),'training dtype mismatch')
        require(arrays['drives'].dtype==arrays['meas'].dtype==np.int16 and np.array_equal(arrays['drives'],drives) and np.array_equal(arrays['meas'],meas),'ordered electrode protocol mismatch')
        require(np.issubdtype(base.dtype,np.integer) and (base>=0).all() and (base<len(ref)).all(),'invalid base_of_pair')
        require(len(meta['states'])==100 and [s['baseline'] for s in meta['states']]==base.tolist(),'states/base_of_pair row mismatch')
        require(all(np.isfinite(v).all() for v in arrays.values()),'nonfinite source values')
        denominator=np.abs(ref[base]).mean(1)
        require(np.isfinite(denominator).all() and (denominator>0).all(),'zero/nonfinite reference denominator')
        voltage=((cur-ref[base])/denominator[:,None]*np.float32(100)).astype(np.float32)
        require(np.isfinite(voltage).all(),'nonfinite normalized voltage')
        image_absmax=float(np.abs(img.astype(np.float32)).max())
        require(np.isfinite(image_absmax) and image_absmax>0,'zero/nonfinite image scale')
        item.update(status='PASS_FINITE_PAIRED_REAL_UNIT_ONLY',arrays={k:dict(shape=list(v.shape),dtype=str(v.dtype),finite=bool(np.isfinite(v).all())) for k,v in arrays.items()},
          base_of_pair=base.tolist(),states_baselines=[s['baseline'] for s in meta['states']],
          same_belt_unit_pair_rows=True,reference_denominator_min=float(denominator.min()),reference_denominator_max=float(denominator.max()),image_absmax=image_absmax)
        require(read(path)[1]['sha256']==npz_id['sha256'] and read(side)[1]['sha256']==side_id['sha256'],'SOURCE_CHANGED after sample check')
    require(read(ROOT/'manifest.csv')[1]['sha256']==ANCHOR,'SOURCE_CHANGED after selection')
    result.update(status='FIXED_ENGINEERING_SAMPLE_CHECKS_PASS_NOT_FORMAL_SPLIT',total_units=len(result['selected']),
      total_frames=sum(i['n_pairs'] for i in result['selected']),image_absmax_engineering_train_only=max(i['image_absmax'] for i in result['selected']),
      multiple_batches_at64=True,manifest_after_sha256=ANCHOR,finished_utc=datetime.datetime.now(datetime.timezone.utc).isoformat())


if __name__=='__main__':
    signal.alarm(90)
    try:main()
    except Exception as exc:result.update(status='SOURCE_CHANGED' if 'SOURCE_CHANGED' in str(exc) else 'FAIL_STOP_NO_RESELECT',error=repr(exc))
    finally:print(json.dumps(result,indent=2,sort_keys=True))
