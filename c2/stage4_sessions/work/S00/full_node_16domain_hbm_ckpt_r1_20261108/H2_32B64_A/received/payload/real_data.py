"""REAL_CORPUS_PILOT_V1: trusted official partitions and same-unit paired rows."""
import csv
import hashlib
import io
import json
import math
from pathlib import Path
import zipfile

PROTOCOL='REAL_CORPUS_PILOT_V1'


class DataNotReady(ValueError):
    pass


def sha(path):
    digest=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda:stream.read(1024*1024),b''):digest.update(block)
    return digest.hexdigest()


def require(condition,message):
    if not condition:raise DataNotReady(message)


def parse_json(raw):
    def unique(pairs):
        result={}
        for key,value in pairs:
            require(key not in result,'duplicate/ambiguous JSON key: '+key)
            result[key]=value
        return result
    return json.loads(raw,object_pairs_hook=unique)


def asset(value):
    require(all(value.get(k) for k in ('path','sha256','version')),'artifact needs absolute path/version/SHA')
    path=Path(value['path']);require(path.is_absolute() and path.is_file(),'missing artifact: '+str(path))
    raw=path.read_bytes();require(hashlib.sha256(raw).hexdigest()==value['sha256'],'artifact SHA mismatch: '+str(path))
    return path,raw


def read_partition(value):
    path,raw=asset(value)
    if path.suffix.lower()=='.csv':
        partitions={k:[] for k in ('train','val','test')}
        reader=csv.DictReader(io.StringIO(raw.decode('utf-8-sig')))
        require(set(reader.fieldnames or [])=={'subject_id','split'},'unsupported split columns/fold: review an explicit adapter')
        for row in reader:
            require(row.get('split') in partitions and row.get('subject_id'),'split CSV requires subject_id,split')
            partitions[row['split']].append(row['subject_id'])
    else:
        obj=parse_json(raw)
        if 'partitions' in obj:require(set(obj)<={'partitions','version','authority_reference'},'ambiguous split container/fold')
        partitions=obj.get('partitions',obj)
        require(set(partitions)<=set(('train','val','test')),'unsupported/ambiguous official split format')
        partitions={k:partitions.get(k,[]) for k in ('train','val','test')}
    require(partitions['train'],'official train is empty')
    seen=set()
    for name,subjects in partitions.items():
        require(isinstance(subjects,list) and all(isinstance(s,str) and s for s in subjects),'invalid subject IDs: '+name)
        require(len(subjects)==len(set(subjects)) and not seen.intersection(subjects),'subject overlaps official partitions')
        seen.update(subjects)
    return partitions


def validate_tables(description):
    """Schema-only helper; production must enter through load_descriptor."""
    corpus=description['corpus'];root=Path(corpus['root'])
    require(root.is_absolute() and root.is_dir(),'corpus root unavailable')
    _,raw=asset(corpus['manifest']);rows={}
    for row in csv.DictReader(io.StringIO(raw.decode('utf-8-sig'))):
        require(row.get('unit') and row['unit'] not in rows,'duplicate/missing manifest unit')
        rows[row['unit']]=row
    require(rows,'empty manifest')
    split=description['split']
    require(split.get('authority_reference') and split.get('subject_id_semantics'),'official split authority/subject semantics missing')
    partitions=read_partition(split)
    path,raw=asset(description['mapping'])
    if path.suffix.lower()=='.csv':
        mapping={}
        reader=csv.DictReader(io.StringIO(raw.decode('utf-8-sig')))
        require(set(reader.fieldnames or [])=={'case','subject_id'},'unsupported subject mapping columns')
        for row in reader:
            require(row.get('case') and row.get('subject_id') and row['case'] not in mapping,'invalid case/subject mapping')
            mapping[row['case']]=row['subject_id']
    else:
        obj=parse_json(raw)
        if 'cases' in obj:require(set(obj)<={'cases','version','authority_reference'},'ambiguous subject mapping container')
        mapping=obj.get('cases',obj)
    require(all(isinstance(k,str) and isinstance(v,str) and k and v for k,v in mapping.items()),'invalid case/subject IDs')
    all_subjects=set().union(*(set(p) for p in partitions.values()))
    require(all(row['case'] in mapping and mapping[row['case']] in all_subjects for row in rows.values()),
            'manifest case lacks authoritative subject/partition mapping')
    _,raw=asset(description['subset']);subset=parse_json(raw)
    require(subset.get('selection_seed')==2026 and subset.get('selection_algorithm'),'missing frozen subset seed/algorithm')
    require(not subset.get('test'),'pilot subset must not contain test data')
    units={};seen=set()
    for partition in ('train','val'):
        selected=subset.get(partition,[]);subjects={};units[partition]=[]
        require(isinstance(selected,list),'subset unit list required')
        for item in selected:
            unit=item['unit'];require(unit in rows and unit not in seen,'unknown/repeated subset unit')
            seen.add(unit);row=rows[unit];subject=mapping[row['case']]
            require(subject in partitions[partition] and item['subject_id']==subject,'unit belongs to wrong official partition')
            for key in ('case','belt'):
                require(item[key]==row[key],'subset/manifest mismatch: '+key)
            for key in ('placement','contact','n_pairs'):
                require(type(item[key]) is int,'subset integer field required: '+key)
                require(int(item[key])==int(row[key]),'subset/manifest mismatch: '+key)
            require(row['belt']=='16_adjacent' and row['status']=='done' and row['finite'].lower()=='true','unit not eligible 16-adjacent data')
            require(row['code_hash']==corpus['code_hash'] and row['config_hash']==corpus['config_hash'],'corpus code/config mismatch')
            require(Path(row['file']).name==row['file'],'invalid manifest file path')
            expected=(root/'parts'/row['file']).resolve()
            require(Path(item['path']).is_absolute() and Path(item['path']).resolve()==expected,'unit path differs from manifest/corpus')
            require(Path(item['sidecar_path']).is_absolute() and Path(item['sidecar_path']).resolve()==expected.with_suffix('.json'),
                    'sidecar must match the same NPZ unit')
            require(item.get('npz_sha256') and item.get('sidecar_sha256'),'unit hashes missing')
            subjects[subject]=subjects.get(subject,0)+1
            units[partition].append(dict(item))
        limit_subjects,limit_units=(2,8) if partition=='train' else (1,4)
        require(len(subjects)<=limit_subjects and all(n<=limit_units for n in subjects.values()),'pilot subject/unit cap exceeded')
    require(units['train'],'pilot train subset is empty')
    require(bool(units['val'])==bool(partitions['val']),'existing formal val must be selected; absent val cannot be invented')
    norm=description['normalization'];require(norm['mode'] in ('fit_train_subset_absmax','formal_train_absmax'),'unknown normalization mode')
    if norm['mode']=='formal_train_absmax':
        _,raw=asset(norm['statistics']);stats=parse_json(raw)
        require(stats.get('fit_partition')=='train' and stats.get('belt')=='16_adjacent','statistics are not train-only same-belt')
        require(stats.get('split_sha256')==split['sha256'] and stats.get('manifest_sha256')==corpus['manifest']['sha256'],'statistics split/corpus identity mismatch')
        require(stats.get('subjects') and set(stats['subjects'])<=set(partitions['train']),'statistics include val/test or unknown subjects')
        require(type(stats.get('image_absmax')) in (float,int) and math.isfinite(stats['image_absmax']) and stats['image_absmax']>0,'invalid formal train scale')
        norm=dict(norm,image_absmax=stats['image_absmax'])
    else:
        require('statistics' not in norm,'formal statistics supplied but not explicitly used')
    return dict(description=description,units=units,partitions=partitions,normalization=norm,
        val_status='FORMAL_VAL_SELECTED' if units['val'] else 'VAL_NOT_RUN_NO_FORMAL_VAL')


def load_descriptor(path,expected_sha):
    try:
        require(path is not None and expected_sha,'S00 descriptor path and trusted SHA are required')
        path=Path(path);require(path.is_file(),'S00 descriptor is missing: '+str(path))
        require(sha(path)==expected_sha,'S00 descriptor SHA mismatch')
        description=parse_json(path.read_text('utf-8-sig'))
        require(description.get('status')=='DATA_READY_FOR_REVIEW',
                'S00 DATA_NOT_READY: '+','.join(str(item.get('code')) for item in description.get('blockers',[])))
        require(description.get('protocol')==PROTOCOL,'real pilot descriptor protocol missing')
        require(description.get('data_origin')=='REAL_FROZEN_CORPUS' and description.get('version') and description.get('authority_reference'),
                'real corpus provenance/version/authority required; synthetic fixtures refused')
        require(description.get('manifest_identity_accepted') is True and description.get('corpus',{}).get('freeze_decision_reference'),
                'exact frozen manifest version has not been accepted; no automatic drift acceptance')
        _,raw=asset(description['source_audit']);audit=parse_json(raw)
        require(audit.get('status')=='DATA_READY_FOR_REVIEW' and not audit.get('blockers'),
                'referenced S00 source audit is not ready')
        require(audit.get('accepted_manifest_sha256')==description['corpus']['manifest']['sha256'],
                'S00 accepted manifest identity differs from descriptor')
        require(description.get('existing_training_entry') is None,'existing official trainer must be reviewed before using this new entry')
        result=validate_tables(description)
        result['identity']=dict(descriptor_sha256=expected_sha,descriptor_version=description['version'],
            artifacts={name:description[name] for name in ('source_audit','split','mapping','subset')},
            corpus=description['corpus'],normalization=description['normalization'])
        return result
    except (OSError,KeyError,TypeError,AttributeError,ValueError,csv.Error) as exc:
        raise DataNotReady(str(exc)) from exc


def protocol_arrays(np):
    drives=np.array([(i,(i+5)%32) for i in range(32)],dtype=np.int16)
    meas=np.array([(i,j) for i,d in enumerate(drives) for j,m in enumerate(drives) if not set(d)&set(m)],dtype=np.int16)
    return drives,meas


def read_unit(item,corpus):
    import numpy as np
    path=Path(item['path']);raw=path.read_bytes();side=Path(item['sidecar_path']).read_bytes()
    require(hashlib.sha256(raw).hexdigest()==item['npz_sha256'] and hashlib.sha256(side).hexdigest()==item['sidecar_sha256'],'unit/sidecar SHA mismatch')
    meta=parse_json(side)
    require(path.stem==meta['unit'],'unit filename/sidecar identity mismatch')
    for key in ('unit','case','placement','contact','belt','n_pairs'):
        require(meta[key]==item[key],'sidecar/descriptor identity mismatch: '+key)
    require(meta['L']==32 and meta['belt']=='32_skip4' and meta['finite'] is True,'wrong belt or nonfinite source declaration')
    require(meta['code_hash']==corpus['code_hash'] and meta['config_hash']==corpus['config_hash'],'unit code/config mismatch')
    with np.load(io.BytesIO(raw),allow_pickle=False) as z:
        ref,cur,images,base=[z[k] for k in ('v_ref','v_cur','images','base_of_pair')]
        drives,meas=protocol_arrays(np)
        require(z['drives'].dtype==np.int16 and z['meas'].dtype==np.int16 and np.array_equal(z['drives'],drives) and np.array_equal(z['meas'],meas),
                'ordered electrode protocol mismatch')
    n=len(cur)
    require(n>0 and ref.ndim==2 and ref.shape[1]==928 and cur.shape==(n,928),'voltage shape mismatch')
    require(images.shape==(n,64,64) and base.shape==(n,) and n==item['n_pairs'],'frame count/shape mismatch')
    require(ref.dtype==cur.dtype==np.float32 and images.dtype in (np.float16,np.float32),'unexpected numeric dtype')
    require(all(np.isfinite(x).all() for x in (ref,cur,images)),'nonfinite corpus values')
    require(np.issubdtype(base.dtype,np.integer) and (base>=0).all() and (base<len(ref)).all(),'invalid base_of_pair')
    require(len(meta['states'])==n and all(type(s['baseline']) is int for s in meta['states']) and [s['baseline'] for s in meta['states']]==base.tolist(),
            'sidecar states order differs from base_of_pair')
    expanded=ref[base];denominator=np.abs(expanded).mean(1,keepdims=True)
    require(np.isfinite(denominator).all() and (denominator>0).all(),'reference denominator must be finite and positive')
    v=((cur-expanded)/denominator*np.float32(100)).astype(np.float32)
    require(np.isfinite(v).all(),'normalized voltage is nonfinite')
    frames=[dict(subject_id=item['subject_id'],case=meta['case'],placement=meta['placement'],contact=meta['contact'],
        belt=meta['belt'],unit=meta['unit'],pair_index=i,baseline_index=int(base[i]),npz_sha256=item['npz_sha256'],
        sidecar_sha256=item['sidecar_sha256']) for i in range(n)]
    return v,images.astype(np.float32),frames


def _load_arrays(metadata):
    import numpy as np
    loaded={};scale=None
    for partition in ('train','val'):
        values=[read_unit(item,metadata['description']['corpus']) for item in metadata['units'][partition]]
        if not values:loaded[partition]=None;continue
        v=np.concatenate([x[0] for x in values]);images=np.concatenate([x[1] for x in values])
        if partition=='train':
            scale=np.float32(metadata['normalization']['image_absmax']) if metadata['normalization']['mode']=='formal_train_absmax' else np.abs(images).max()
            require(np.isfinite(scale) and scale>0,'train image absmax must be positive finite fp32')
        y0=(images/scale)[:,None]
        require(np.isfinite(y0).all(),'normalized image is nonfinite')
        loaded[partition]=dict(v=v,y0=y0,frame_ids=[frame for value in values for frame in value[2]])
    return dict(**loaded,image_scale=float(scale),val_status=metadata['val_status'],
                normalization_scope=metadata['normalization']['mode'])


def load_arrays(metadata):
    try:return _load_arrays(metadata)
    except (OSError,KeyError,TypeError,AttributeError,ValueError,zipfile.BadZipFile) as exc:raise DataNotReady(str(exc)) from exc
