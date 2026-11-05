"""Deterministically paired synthetic unit files; never real corpus evidence."""
import hashlib
import json
from pathlib import Path
import numpy as np


def protocol(L, skip):
    drives = np.array([(i, (i + skip) % L) for i in range(L)], dtype=np.int16)
    meas = np.array([(i, j) for i, d in enumerate(drives) for j, m in enumerate(drives)
                     if not (set(d) & set(m))], dtype=np.int16)
    return drives, meas


def describe(path):
    path = Path(path)
    return dict(path=str(path.resolve()), npz_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                sidecar_sha256=hashlib.sha256(path.with_suffix('.json').read_bytes()).hexdigest())


def write_fixture(directory):
    directory = Path(directory)
    sources = {}
    for belt, (L, skip) in {'16_adjacent': (16, 1), '32_skip4': (32, 5)}.items():
        drives, meas = protocol(L, skip)
        sources[belt] = []
        for placement in (0, 1):
            uid = f'synthetic_p{placement}_{belt}_c0'
            path = directory / (uid + '.npz')
            base = np.array([0, 0, 1, 1], dtype=np.int8)
            pixels = np.linspace(-1, 1, 4096, dtype=np.float32).reshape(64, 64)
            # A distinct image per belt/placement/frame. Voltage perturbation is
            # the image's spatial mean, so pairing can be checked independently.
            images = np.stack([pixels * 0.01 + L / 100 + placement / 10 + i / 100
                               for i in range(4)]).astype(np.float32)
            ref = np.stack([1 + np.arange(len(meas), dtype=np.float32) / 10000 + b for b in (0, 1)])
            cur = ref[base] + images.mean((1, 2))[:, None]
            np.savez(path, images=images, v_ref=ref, v_cur=cur, base_of_pair=base,
                     drives=drives, meas=meas)
            meta = dict(unit=uid, case='synthetic_case', placement=placement, belt=belt,
                        contact=0, L=L, n_pairs=4, code_hash='SYNTHETIC_ONLY',
                        config_hash='SYNTHETIC_ONLY', states=[dict(baseline=int(b)) for b in base])
            path.with_suffix('.json').write_text(json.dumps(meta), encoding='utf-8')
            sources[belt].append(describe(path))
    return sources
