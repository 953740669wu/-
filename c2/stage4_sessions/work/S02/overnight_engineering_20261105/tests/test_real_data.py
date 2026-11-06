"""LOCAL_SYNTHETIC_TEST_ONLY NPZ fixtures; never a formal corpus descriptor."""
import csv
import json
from pathlib import Path
import sys
import tempfile
import unittest
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import real_data as data


def write_json(path,value):
    path.write_text(json.dumps(value),encoding='utf-8')


class DataTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(dir=ROOT/'evidence')
        self.root=Path(self.temp.name).resolve();self.root.relative_to(ROOT)
        parts=self.root/'parts';parts.mkdir()
        rows=[];units=[]
        drives,meas=data.protocol_arrays(np)
        for case,subject,start in [('A','S1',1),('B','S2',101),('C','S3',201)]:
            unit=case+'_p0_16_adjacent_c0';path=parts/(unit+'.npz')
            base=np.array([0,1,0,1],np.int8);ref=np.full((2,208),2.,np.float32);ref[1]=4
            images=np.broadcast_to(np.arange(start,start+4,dtype=np.float32)[:,None,None],(4,64,64)).copy()
            cur=ref[base]+np.arange(start,start+4,dtype=np.float32)[:,None]*ref[base]/100
            np.savez(path,v_ref=ref,v_cur=cur,images=images.astype(np.float16),base_of_pair=base,drives=drives,meas=meas)
            meta=dict(unit=unit,case=case,placement=0,contact=0,belt='16_adjacent',L=16,n_pairs=4,
                code_hash='code-test',config_hash='config-test',finite=True,states=[dict(baseline=int(b)) for b in base])
            write_json(path.with_suffix('.json'),meta)
            units.append(dict(unit=unit,case=case,subject_id=subject,placement=0,contact=0,belt='16_adjacent',n_pairs=4,
                path=str(path),sidecar_path=str(path.with_suffix('.json')),npz_sha256=data.sha(path),
                sidecar_sha256=data.sha(path.with_suffix('.json'))))
            rows.append(dict(unit=unit,case=case,placement=0,contact=0,belt='16_adjacent',n_pairs=4,
                code_hash='code-test',config_hash='config-test',status='done',finite='True',file=path.name))
        manifest=self.root/'manifest.csv'
        with manifest.open('w',newline='',encoding='utf-8') as f:
            writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
        write_json(self.root/'split.json',dict(train=['S1'],val=['S2'],test=['S3']))
        write_json(self.root/'map.json',dict(A='S1',B='S2',C='S3'))
        self.subset=dict(selection_seed=2026,selection_algorithm='TEST_ONLY',train=[units[0]],val=[units[1]])
        self.units=units
        write_json(self.root/'subset.json',self.subset)
        def asset(name):return dict(path=str(self.root/name),sha256=data.sha(self.root/name),version='TEST_ONLY')
        self.description=dict(protocol='REAL_CORPUS_PILOT_V1',status='DATA_NOT_READY',data_origin='LOCAL_SYNTHETIC_TEST_ONLY',
            version='TEST_ONLY',authority_reference='TEST_NOT_AUTHORITY',existing_training_entry=None,
            corpus=dict(root=str(self.root),manifest=asset('manifest.csv'),code_hash='code-test',config_hash='config-test'),
            split=dict(**asset('split.json'),authority_reference='TEST_ONLY',subject_id_semantics='TEST_SUBJECT'),
            mapping=asset('map.json'),subset=asset('subset.json'),normalization=dict(mode='fit_train_subset_absmax'))

    def tearDown(self):
        self.root.relative_to(ROOT);self.temp.cleanup()

    def tables(self):
        # Lower-level schema test bypasses the CLI provenance gate deliberately.
        return data.validate_tables(self.description)

    def refresh(self,name,key):
        self.description[key]['sha256']=data.sha(self.root/name)

    def test_same_unit_pair_reference_expansion_and_train_only_scale(self):
        loaded=data.load_arrays(self.tables())
        np.testing.assert_allclose(loaded['train']['v'][:,0],np.arange(1,5),rtol=2e-5)
        self.assertEqual(loaded['image_scale'],4.)
        self.assertEqual(float(loaded['val']['y0'].max()),26.)
        self.assertEqual([f['baseline_index'] for f in loaded['train']['frame_ids']],[0,1,0,1])

    def test_fixture_cannot_pass_production_descriptor_gate(self):
        self.description['status']='DATA_READY_FOR_REVIEW'
        path=self.root/'description.json';write_json(path,self.description)
        with self.assertRaises(data.DataNotReady):data.load_descriptor(path,data.sha(path))

    def test_malformed_descriptor_is_data_not_ready(self):
        path=self.root/'malformed.json';write_json(path,[])
        with self.assertRaises(data.DataNotReady):data.load_descriptor(path,data.sha(path))

    def test_subject_overlap_is_rejected(self):
        write_json(self.root/'split.json',dict(train=['S1'],val=['S1','S2'],test=['S3']))
        self.refresh('split.json','split')
        with self.assertRaises(data.DataNotReady):self.tables()

    def test_test_unit_cannot_be_used_for_train_or_statistics(self):
        self.subset['train']=[self.units[2]];write_json(self.root/'subset.json',self.subset)
        self.refresh('subset.json','subset')
        with self.assertRaises(data.DataNotReady):self.tables()

    def test_val_absence_is_explicit_and_never_uses_test(self):
        write_json(self.root/'split.json',dict(train=['S1'],test=['S2','S3']))
        self.subset['val']=[];write_json(self.root/'subset.json',self.subset)
        self.refresh('split.json','split');self.refresh('subset.json','subset')
        loaded=data.load_arrays(self.tables())
        self.assertIsNone(loaded['val']);self.assertEqual(loaded['val_status'],'VAL_NOT_RUN_NO_FORMAL_VAL')

    def test_bad_source_identity_or_cross_belt_is_rejected(self):
        unit=self.subset['train'][0];path=Path(unit['sidecar_path']);meta=json.loads(path.read_text());meta['belt']='32_skip4';write_json(path,meta)
        with self.assertRaises(data.DataNotReady):data.load_arrays(self.tables())
        unit['sidecar_sha256']=data.sha(path);write_json(self.root/'subset.json',self.subset);self.refresh('subset.json','subset')
        with self.assertRaises(data.DataNotReady):data.load_arrays(self.tables())

    def test_zero_reference_or_wrong_states_order_is_rejected(self):
        unit=self.subset['train'][0];path=Path(unit['path'])
        with np.load(path,allow_pickle=False) as z:arrays={k:z[k] for k in z.files}
        arrays['v_ref'][0]=0;np.savez(path,**arrays);unit['npz_sha256']=data.sha(path)
        write_json(self.root/'subset.json',self.subset);self.refresh('subset.json','subset')
        with self.assertRaises(data.DataNotReady):data.load_arrays(self.tables())

    def test_wrong_states_or_electrode_order_is_rejected(self):
        unit=self.subset['train'][0];path=Path(unit['sidecar_path']);meta=json.loads(path.read_text())
        meta['states'][0]['baseline']=1;write_json(path,meta);unit['sidecar_sha256']=data.sha(path)
        write_json(self.root/'subset.json',self.subset);self.refresh('subset.json','subset')
        with self.assertRaises(data.DataNotReady):data.load_arrays(self.tables())
        meta['states'][0]['baseline']=0;write_json(path,meta);unit['sidecar_sha256']=data.sha(path)
        path=Path(unit['path'])
        with np.load(path,allow_pickle=False) as z:arrays={k:z[k] for k in z.files}
        arrays['meas']=arrays['meas'][::-1];np.savez(path,**arrays);unit['npz_sha256']=data.sha(path)
        write_json(self.root/'subset.json',self.subset);self.refresh('subset.json','subset')
        with self.assertRaises(data.DataNotReady):data.load_arrays(self.tables())

    def test_formal_statistics_must_exclude_val_and_test(self):
        path=self.root/'stats.json'
        stats=dict(fit_partition='train',belt='16_adjacent',split_sha256=self.description['split']['sha256'],
            manifest_sha256=self.description['corpus']['manifest']['sha256'],subjects=['S1'],image_absmax=4.)
        write_json(path,stats)
        self.description['normalization']=dict(mode='formal_train_absmax',statistics=dict(path=str(path),sha256=data.sha(path),version='TEST_ONLY'))
        self.assertEqual(data.load_arrays(self.tables())['image_scale'],4.)
        stats['subjects']=['S2'];write_json(path,stats);self.description['normalization']['statistics']['sha256']=data.sha(path)
        with self.assertRaises(data.DataNotReady):self.tables()

    def test_duplicate_or_multiple_fold_split_is_rejected(self):
        path=self.root/'split.json'
        path.write_text('{"train":["S1"],"train":["S2"],"test":["S3"]}',encoding='utf-8')
        self.refresh('split.json','split')
        with self.assertRaises(data.DataNotReady):self.tables()
        write_json(path,dict(partitions=dict(train=['S1'],val=['S2'],test=['S3']),folds={'unknown':{}}))
        self.refresh('split.json','split')
        with self.assertRaises(data.DataNotReady):self.tables()

    def test_zero_train_image_scale_is_rejected(self):
        unit=self.subset['train'][0];path=Path(unit['path'])
        with np.load(path,allow_pickle=False) as z:arrays={k:z[k] for k in z.files}
        arrays['images'][:]=0;np.savez(path,**arrays);unit['npz_sha256']=data.sha(path)
        write_json(self.root/'subset.json',self.subset);self.refresh('subset.json','subset')
        with self.assertRaises(data.DataNotReady):data.load_arrays(self.tables())


if __name__=='__main__':unittest.main(verbosity=2)
