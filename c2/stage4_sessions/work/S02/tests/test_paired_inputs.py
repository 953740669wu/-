"""Real numpy array/identity checks. No torch, model or performance acceptance."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
import numpy as np
from paired_fixture import describe, write_fixture

ROOT = Path(__file__).resolve().parents[1]


class PairedInputs(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=ROOT / 'evidence', prefix='pair_test_')
        self.addCleanup(self.temp.cleanup)
        self.sources = write_fixture(self.temp.name)
        spec = importlib.util.spec_from_file_location('paired_inputs', ROOT / 'candidate' / 'paired_inputs.py')
        self.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.module)

    def load(self, belt='16_adjacent', sources=None):
        return self.module.load_belt_inputs(self.sources[belt] if sources is None else sources, belt)

    def alter(self, key, value):
        path = Path(self.sources['16_adjacent'][0]['path'])
        with np.load(path, allow_pickle=False) as unit:
            arrays = {k: unit[k] for k in unit.files}
        arrays[key] = value
        np.savez(path, **arrays)
        self.sources['16_adjacent'][0] = describe(path)

    def test_belt_specific_targets_and_reference_expansion(self):
        for belt in self.sources:
            out = self.load(belt)
            self.assertEqual(len(out['frame_ids']), 8)
            self.assertEqual(len(set(out['frame_ids'])), 8)
            self.assertEqual(out['v'].dtype, np.float32)
            self.assertEqual(out['y0'].shape, (8, 1, 64, 64))
            self.assertEqual(out['y0'].dtype, np.float32)
            for i, source in enumerate(self.sources[belt]):
                with np.load(source['path'], allow_pickle=False) as z:
                    expected = (z['v_cur'] - z['v_ref'][z['base_of_pair']]) / np.abs(
                        z['v_ref'][z['base_of_pair']]).mean(1, keepdims=True) * 100
                    np.testing.assert_array_equal(out['v'][i*4:(i+1)*4], expected.astype(np.float32))
                    np.testing.assert_array_equal(out['y0'][i*4:(i+1)*4, 0],
                                                  z['images'] / np.float32(out['scale']))
                    np.testing.assert_allclose((z['v_cur'] - z['v_ref'][z['base_of_pair']]).mean(1),
                                               z['images'].mean((1, 2)), atol=2e-7, rtol=2e-6)
        # Same-shaped arrays are deliberately different across belts, like S00's witness.
        self.assertNotEqual(self.load('16_adjacent')['scale'], self.load('32_skip4')['scale'])
        self.assertFalse(np.array_equal(self.load('16_adjacent')['y0'], self.load('32_skip4')['y0']))

    def test_source_order_and_frame_indices_are_preserved(self):
        original = self.load()
        reverse = self.load(sources=list(reversed(self.sources['16_adjacent'])))
        self.assertEqual(reverse['frame_ids'], original['frame_ids'][4:] + original['frame_ids'][:4])
        self.assertEqual([x[-2:] for x in original['frame_ids'][:4]], [(0, 0), (1, 0), (2, 1), (3, 1)])

    def test_cross_belt_source_rejected(self):
        with self.assertRaisesRegex(ValueError, 'belt'):
            self.load(sources=self.sources['32_skip4'])

    def test_changed_same_shape_images_rejected_by_frozen_hash(self):
        source = self.sources['16_adjacent'][0].copy()
        path = Path(source['path'])
        with np.load(path, allow_pickle=False) as z:
            arrays = {k: z[k] for k in z.files}
        arrays['images'] = arrays['images'][::-1]
        np.savez(path, **arrays)
        with self.assertRaisesRegex(ValueError, 'SHA256'):
            self.load(sources=[source])

    def test_duplicate_source_rejected(self):
        source = self.sources['16_adjacent'][0]
        with self.assertRaisesRegex(ValueError, 'duplicate'):
            self.load(sources=[source, source])

    def test_reference_index_out_of_bounds_rejected(self):
        self.alter('base_of_pair', np.array([0, 0, 1, 2], dtype=np.int8))
        with self.assertRaisesRegex(ValueError, 'baseline'):
            self.load()

    def test_sidecar_frame_order_mismatch_rejected(self):
        path = Path(self.sources['16_adjacent'][0]['path'])
        meta = json.loads(path.with_suffix('.json').read_text())
        meta['states'][0]['baseline'] = 1
        path.with_suffix('.json').write_text(json.dumps(meta))
        self.sources['16_adjacent'][0] = describe(path)
        with self.assertRaisesRegex(ValueError, 'frame'):
            self.load()

    def test_zero_denominator_and_nonfinite_rejected(self):
        self.alter('v_ref', np.zeros((2, 208), dtype=np.float32))
        with self.assertRaisesRegex(ValueError, 'denominator'):
            self.load()
        self.alter('images', np.full((4, 64, 64), np.nan, dtype=np.float32))
        with self.assertRaisesRegex(ValueError, 'finite'):
            self.load()

    def test_zero_scale_rejected(self):
        self.alter('images', np.zeros((4, 64, 64), dtype=np.float32))
        # Both units must have zero targets to make the cohort scale zero.
        self.sources['16_adjacent'] = self.sources['16_adjacent'][:1]
        with self.assertRaisesRegex(ValueError, 'scale'):
            self.load()

    def test_protocol_order_mismatch_rejected(self):
        with np.load(self.sources['16_adjacent'][0]['path'], allow_pickle=False) as z:
            self.alter('meas', z['meas'][::-1])
        with self.assertRaisesRegex(ValueError, 'protocol'):
            self.load()


if __name__ == '__main__':
    unittest.main(verbosity=2)
