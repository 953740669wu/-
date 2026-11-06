"""LOCAL_FIXTURE: isolated engineering gates and durable exposure transitions."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import engineering_data as data
import real_data


class EngineeringTests(unittest.TestCase):
    def description(self):
        d=json.loads((ROOT/'tests/ENGINEERING_DESCRIPTOR_METADATA_FIXTURE.json').read_text())
        return d

    def test_actual_s00_schema_only_no_real_data_read(self):
        d=self.description();data.validate_description(d)
        self.assertEqual(sum(x['n_pairs'] for x in d['train']),1600)

    def test_formal_engineering_isolation(self):
        d=self.description();d['protocol']='REAL_CORPUS_PILOT_V1'
        with self.assertRaises(real_data.DataNotReady):data.validate_description(d)
        path=ROOT/'tests/ENGINEERING_DESCRIPTOR_METADATA_FIXTURE.json'
        with self.assertRaises(real_data.DataNotReady):real_data.load_descriptor(path,real_data.sha(path))

    def test_source_third_version(self):
        d=self.description();d['corpus']['manifest']['sha256']='0'*64
        with self.assertRaises(data.SourceChanged):data.validate_description(d)

    def test_caps_duplicates_subject_and_val_rejected(self):
        for mutate in (lambda d:d['train'].append(copy.deepcopy(d['train'][0])),
                       lambda d:d['train'][0].update(subject_id='invented'),
                       lambda d:d.update(val=[]),
                       lambda d:d['train'][0].update(belt='32_adjacent'),
                       lambda d:d['selection'].update(seed=0)):
            d=self.description();mutate(d)
            with self.assertRaises(real_data.DataNotReady):data.validate_description(d)

    def test_deterministic_sorted_selector(self):
        rows=[dict(unit=f'{case}_{i:02}',case=case,belt='16_adjacent',status='done',finite='true',
                   n_pairs='100',code_hash=data.CODE,config_hash=data.CONFIG)
              for case in ['z','b','a'] for i in range(12)]
        a=data.select_units(rows,['b','a']);b=data.select_units(list(reversed(rows)),['a','b'])
        self.assertEqual(a,b);self.assertEqual(len(a[0]),16);self.assertTrue(a[1])
        self.assertEqual({r['case'] for r in a[0]},{'a','b'})

    def test_ninth_unique_unit_rejected(self):
        d=self.description();item=copy.deepcopy(d['train'][0]);item['unit']+='_extra'
        item['path']=str(Path(item['path']).with_name(item['unit']+'.npz')).replace('\\','/')
        item['sidecar_path']=item['path'][:-4]+'.json';d['train'].append(item)
        with self.assertRaisesRegex(real_data.DataNotReady,'cap exceeded'):data.validate_description(d)

    def test_exposure_survives_failure_and_distinguishes_confirmed(self):
        d=self.description()
        with tempfile.TemporaryDirectory(dir=ROOT/'evidence') as tmp:
            path=Path(tmp)/'ledger.json';ledger=data.Exposure(path,d)
            ledger.unit_status(d['train'][0]['unit'],'LOAD_ATTEMPTED')
            ids=[dict(unit=d['train'][0]['unit'],pair_index=2)]
            ledger.attempt(1,[2],ids)
            saved=json.loads(path.read_text());self.assertEqual(saved['in_flight']['status'],'POSSIBLY_USED_IN_INTERRUPTED_UPDATE')
            self.assertEqual(saved['confirmed_updates'],[])
            ledger.confirm(1);saved=json.loads(path.read_text())
            self.assertIsNone(saved['in_flight']);self.assertEqual(saved['confirmed_updates'][0]['frame_ids'],ids)
            with self.assertRaises(real_data.DataNotReady):data.Exposure(path,d)

    def test_engineering_loader_train_only_scale_and_pairing(self):
        from test_real_data import DataTests
        fixture=DataTests();fixture.setUp()
        try:
            d=dict(train=[dict(fixture.units[0],subject_id=None)],corpus=fixture.description['corpus'])
            ledger=data.Exposure(fixture.root/'runtime.json',d)
            loaded=data.load_arrays(dict(description=d,units=dict(train=d['train'])),ledger)
            self.assertIsNone(loaded['val']);self.assertEqual(loaded['image_scale'],4.)
            self.assertEqual([f['baseline_index'] for f in loaded['train']['frame_ids']],[0,1,0,1])
            self.assertTrue(all(f['subject_id'] is None for f in loaded['train']['frame_ids']))
            self.assertEqual(ledger.value['units'][0]['usage_status'],'LOADED_FOR_ENGINEERING_TRAIN_STATISTICS')
            self.assertFalse(ledger.value['confirmed_updates'])
        finally:fixture.tearDown()


if __name__=='__main__':unittest.main(verbosity=2)
