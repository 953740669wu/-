"""Explicit engineering-only metadata; R8 formal gates remain independent."""
import csv
import io
import json
from pathlib import Path, PurePosixPath
import random

import real_data
from real_data import require,sha,asset,parse_json,DataNotReady

ROOT=Path(__file__).resolve().parent
PROTOCOL='ENGINEERING_REAL_CORPUS_PILOT_V1'
MANIFEST='bdd146040bddf2ddd47fb9d571d5d2f40e5fa20fbd30d0c0d11239893e647032'
CASES='f0a3c5bd443b63f06dc69c8bed5e58dd50999a91fddb5222f0c38594ba92d836'
CODE='d8b2be8d1f';CONFIG='b1049eac1a'
FLAGS=dict(engineering_only=True,formal_split_status='UNKNOWN',
           validation_status='NOT_RUN_NO_FORMAL_SPLIT',subject_mapping_status='UNKNOWN')


class SourceChanged(DataNotReady):pass


def unchanged(condition,message):
    if not condition:raise SourceChanged(message)


def validate_description(d):
    require(d.get('protocol')==PROTOCOL and d.get('status')=='ENGINEERING_DATA_READY','engineering protocol/status required')
    require(d.get('data_origin')=='REAL_CORPUS_ENGINEERING_SAMPLES' and d.get('version'),'engineering provenance/version required')
    require(all(type(d.get(k)) is type(v) and d[k]==v for k,v in FLAGS.items()),'explicit engineering flags required')
    require(not set(d).intersection(('val','test','split','mapping','subset','normalization')),'no formal partitions/statistics in engineering mode')
    require(d['interface_sha256']==sha(ROOT/'INTERFACE.json'),'published interface SHA mismatch')
    c=d['corpus'];m=c['manifest'];s=d['selection']
    unchanged(m['sha256']==MANIFEST and m['bytes']==3399057 and c['code_hash']==CODE and c['config_hash']==CONFIG,
              'SOURCE_CHANGED: engineering source anchor differs')
    require(m['path']=='/home/share/songzhenlong/eitfm/corpus_shape_20261102/manifest.csv' and
            c['root']=='/home/share/songzhenlong/eitfm/corpus_shape_20261102','unexpected engineering source location')
    require(s['seed']==2026 and s['algorithm']=='sorted_prefer119_python_random_sample_v1' and
            s['cases_txt']['sha256']==CASES and type(s['preferred_scope_used']) is bool,'selection identity mismatch')
    items=d['train'];require(isinstance(items,list) and items,'nonempty engineering train required')
    seen=set();counts={}
    for item in items:
        unit=item['unit'];case=item['case']
        require(unit not in seen and item['subject_id'] is None and item['belt']=='16_adjacent','duplicate/wrong-belt/invented subject')
        seen.add(unit);counts[case]=counts.get(case,0)+1
        require(all(type(item[k]) is int and item[k]>=0 for k in ('placement','contact','n_pairs')) and item['n_pairs']>0,'invalid unit integer fields')
        expected=PurePosixPath(c['root'])/'parts'/(unit+'.npz')
        require(PurePosixPath(item['path'])==expected and PurePosixPath(item['sidecar_path'])==expected.with_suffix('.json'),'unit path identity mismatch')
        for prefix in ('npz','sidecar'):
            require(len(item[prefix+'_sha256'])==64 and all(x in '0123456789abcdef' for x in item[prefix+'_sha256']) and
                    type(item[prefix+'_bytes']) is int and item[prefix+'_bytes']>0,'missing file SHA/bytes')
    require(len(counts)<=2 and all(n<=8 for n in counts.values()),'case/unit cap exceeded')
    require(s['selected_cases']==sorted(counts) and [x['unit'] for x in items]==
            [x['unit'] for x in sorted(items,key=lambda x:(x['case'],x['unit']))],'fixed selected case/unit ordering mismatch')
    runtime=PurePosixPath(d['runtime_exposure_ledger_path'])
    owned=PurePosixPath('/home/share/dengqingtian/opt/stage4_sessions/S00')
    require(runtime.is_absolute() and '..' not in runtime.parts and owned in runtime.parents and
            runtime.name=='EXPOSURE_LEDGER.json' and runtime.parent.name=='outputs' and
            runtime.parent.parent.name=='payload' and str(runtime)!=d['exposure_ledger']['path'],
            'new owned payload outputs exposure ledger required')


def select_units(rows,preferred):
    eligible=[r for r in rows if r['belt']=='16_adjacent' and r['status']=='done' and r['finite'].lower()=='true'
              and int(r['n_pairs'])>0 and r['code_hash']==CODE and r['config_hash']==CONFIG]
    cases=sorted({r['case'] for r in eligible});pool=sorted(set(cases).intersection(preferred));used=bool(pool)
    if not pool:pool=cases
    rng=random.Random(2026);chosen=sorted(rng.sample(pool,min(2,len(pool))));selected=[]
    for case in chosen:
        units=sorted((r for r in eligible if r['case']==case),key=lambda r:r['unit'])
        selected.extend(sorted(rng.sample(units,min(8,len(units))),key=lambda r:r['unit']))
    return selected,used


def load_descriptor(path,expected_sha):
    try:
        require(path is not None and expected_sha,'engineering descriptor path and trusted SHA required')
        path=Path(path);require(sha(path)==expected_sha,'descriptor SHA mismatch')
        d=parse_json(path.read_text('utf-8-sig'));validate_description(d)
        c=d['corpus'];mp=Path(c['manifest']['path'])
        unchanged(mp.stat().st_size==3399057 and sha(mp)==MANIFEST,'SOURCE_CHANGED: actual manifest drift')
        _,raw=asset(c['manifest']);rows=list(csv.DictReader(io.StringIO(raw.decode('utf-8-sig'))))
        unchanged(len(rows)==14300 and len({r['case'] for r in rows})==143 and
                  sum(int(r['n_pairs']) for r in rows)==1430000,'SOURCE_CHANGED: manifest counts')
        require(len({r['unit'] for r in rows})==len(rows),'duplicate manifest unit')
        _,raw=asset(d['selection']['cases_txt']);preferred=raw.decode('utf-8-sig').splitlines()
        require(len(preferred)==119 and len(set(preferred))==119,'original119 case pool mismatch')
        chosen,used=select_units(rows,preferred)
        require([r['unit'] for r in chosen]==[r['unit'] for r in d['train']] and
                used==d['selection']['preferred_scope_used'],'deterministic selection mismatch; no replacement')
        for row,item in zip(chosen,d['train']):
            require(all(str(item[k])==row[k] for k in ('unit','case','belt','placement','contact','n_pairs')) and
                    row['file']==item['unit']+'.npz','selected manifest identity mismatch')
            for field,prefix in (('path','npz'),('sidecar_path','sidecar')):
                p=Path(item[field]);unchanged(p.stat().st_size==item[prefix+'_bytes'] and sha(p)==item[prefix+'_sha256'],
                                              'SOURCE_CHANGED: selected unit drift: '+str(p))
        _,raw=asset(d['exposure_ledger']);ledger=parse_json(raw)
        require(ledger['protocol']==PROTOCOL and ledger['engineering_only'] is True and
                ledger['formal_split_status']=='UNKNOWN' and ledger['subject_mapping_status']=='UNKNOWN' and
                ledger.get('future_test_policy'),'initial exposure policy missing')
        expected=[dict(case=x['case'],unit=x['unit'],npz_sha256=x['npz_sha256'],sidecar_sha256=x['sidecar_sha256'],
                       selection_status='SELECTED_RESERVED',usage_status='NOT_STARTED') for x in d['train']]
        require(ledger['units']==expected,'initial exposure selection/usage mismatch')
        return dict(description=d,units=dict(train=d['train'],val=[]),
                    identity=dict(descriptor_sha256=expected_sha,descriptor_version=d['version'],
                                  interface_sha256=d['interface_sha256'],corpus=c,selection=d['selection'],units=d['train']))
    except SourceChanged:raise
    except (OSError,KeyError,TypeError,AttributeError,ValueError,csv.Error) as exc:raise DataNotReady(str(exc)) from exc


class Exposure:
    def __init__(self,path,description):
        self.path=Path(path);require(not self.path.exists(),'refuse existing runtime exposure ledger; no retry')
        self.value=dict(protocol=PROTOCOL,**FLAGS,units=[dict(x,selection_status='SELECTED_RESERVED',usage_status='NOT_STARTED')
                        for x in description['train']],confirmed_updates=[],in_flight=None,recovery_probe=None,
                        future_test_policy='Resolve true subjects and exclude all engineering-exposed subjects from final test; interrupted use requires conservative review.')
        self.save()

    def save(self):
        self.path.parent.mkdir(parents=True,exist_ok=True)
        temporary=self.path.with_suffix('.tmp');require(not temporary.exists(),'stale exposure temporary file')
        with temporary.open('x',encoding='utf-8') as stream:
            json.dump(self.value,stream,indent=2);stream.write('\n');stream.flush()
            import os
            os.fsync(stream.fileno())
        temporary.replace(self.path)

    def unit_status(self,unit,status):
        for item in self.value['units']:
            if item['unit']==unit:item['usage_status']=status
        self.save()

    def attempt(self,step,indices,frame_ids):
        require(self.value['in_flight'] is None,'unfinished prior update')
        self.value['in_flight']=dict(step=step,frame_indices=indices,frame_ids=frame_ids,status='POSSIBLY_USED_IN_INTERRUPTED_UPDATE')
        self.save()

    def confirm(self,step):
        value=self.value['in_flight'];require(value and value['step']==step,'exposure update mismatch')
        value['status']='CONSUMED_CONFIRMED';self.value['confirmed_updates'].append(value);self.value['in_flight']=None
        for unit in {x['unit'] for x in value['frame_ids']}: 
            for item in self.value['units']:
                if item['unit']==unit:item['usage_status']='CONSUMED_CONFIRMED'
        self.save()


def load_arrays(metadata,ledger):
    import numpy as np
    values=[]
    for item in metadata['units']['train']:
        ledger.unit_status(item['unit'],'LOAD_ATTEMPTED')
        values.append(real_data.read_unit(item,metadata['description']['corpus']))
        ledger.unit_status(item['unit'],'LOADED_FOR_ENGINEERING_TRAIN_STATISTICS')
    v=np.concatenate([x[0] for x in values]);images=np.concatenate([x[1] for x in values])
    scale=np.abs(images).max();require(np.isfinite(scale) and scale>0,'engineering train absmax must be positive finite')
    y0=(images/scale)[:,None];require(np.isfinite(y0).all(),'nonfinite normalized images')
    return dict(train=dict(v=v,y0=y0,frame_ids=[f for x in values for f in x[2]]),val=None,
                image_scale=float(scale),normalization_scope='fit_engineering_train_subset_absmax_once')
