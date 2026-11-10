"""Frozen real 32_skip4 engineering descriptor and original exposure/load path."""
import json
from pathlib import Path

import real_data
from real_data import require, sha, DataNotReady

PROTOCOL = "S09_REAL32_ENGINEERING_B32_V1"
FLAGS = dict(engineering_only=True, formal_split_status="UNKNOWN", subject_mapping_status="UNKNOWN",
             validation_status="NOT_RUN_NO_FORMAL_SPLIT")


def load_descriptor(path, expected_sha):
    path = Path(path)
    require(sha(path) == expected_sha, "32E descriptor SHA mismatch")
    d = json.loads(path.read_bytes())
    require(d["protocol"] == PROTOCOL and d["data_origin"] == "REAL_CORPUS_ENGINEERING_SAMPLES"
            and all(d[k] == v for k,v in FLAGS.items()), "wrong 32E engineering scope")
    require(d["model_protocol"] == dict(belt="32_skip4", electrodes=32, drive_offset=5, tokens=928),
            "wrong 32E protocol")
    corpus = d["corpus"]
    base = Path("/home/share/songzhenlong/eitfm/corpus_shape_20261102")
    require(corpus["root"] == str(base) and corpus["code_hash"] == "d8b2be8d1f" and
            corpus["config_hash"] == "b1049eac1a", "32E source origin drift")
    for rec, target in ((corpus["manifest"],base/"manifest.csv"),(d["selection"]["cases_txt"],base/"cases.txt")):
        require(rec["path"] == str(target) and target.stat().st_size == rec["bytes"] and sha(target) == rec["sha256"],
                "32E corpus source changed")
    items = d["train"]
    require(len(items) == len({x["unit"] for x in items}) == 8
            and sum(x["n_pairs"] for x in items) == 800, "32E selected frames differ")
    for item in items:
        target = base / "parts" / (item["unit"] + ".npz")
        require(item["subject_id"] is None and item["belt"] == "32_skip4" and item["n_pairs"] == 100,
                "invalid frozen 32E unit")
        for prefix, key, file in (("npz","path",target),("sidecar","sidecar_path",target.with_suffix(".json"))):
            require(item[key] == str(file) and file.stat().st_size == item[prefix+"_bytes"]
                    and sha(file) == item[prefix+"_sha256"], "32E unit source drift: "+str(file))
    return dict(description=d,units=dict(train=items,val=[]),identity=dict(descriptor_sha256=expected_sha,
                protocol=PROTOCOL,corpus=corpus,selection=d["selection"],units=items))


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
