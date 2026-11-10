"""Freeze a real 32_skip4 engineering subset using only login-side metadata."""
import ast
import csv
import hashlib
import json
from pathlib import Path
import random
import struct
import zipfile


ROOT = Path("/home/share/songzhenlong/eitfm/corpus_shape_20261102")
MANIFEST_SHA = "bdd146040bddf2ddd47fb9d571d5d2f40e5fa20fbd30d0c0d11239893e647032"
CASES_SHA = "f0a3c5bd443b63f06dc69c8bed5e58dd50999a91fddb5222f0c38594ba92d836"
CODE, CONFIG = "d8b2be8d1f", "b1049eac1a"
BELT, L, SKIP, TOKENS = "32_skip4", 32, 5, 928
SEED, BATCH, STEPS = 2026, 32, 25


def sha(path):
    with path.open("rb") as stream:
        digest = hashlib.sha256()
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
        return digest.hexdigest()


def identity(path):
    return dict(path=str(path), bytes=path.stat().st_size, sha256=sha(path))


def npy_header(stream):
    assert stream.read(6) == b"\x93NUMPY"
    major, minor = stream.read(2)
    assert (major, minor) in {(1, 0), (2, 0)}
    size = struct.unpack("<H" if major == 1 else "<I", stream.read(2 if major == 1 else 4))[0]
    return ast.literal_eval(stream.read(size).decode("ascii"))


def ordered_protocol():
    drives = [(i, (i + SKIP) % L) for i in range(L)]
    meas = [(i, j) for i, d in enumerate(drives) for j, m in enumerate(drives) if not set(d) & set(m)]
    assert len(meas) == TOKENS
    return drives, meas


def inspect_unit(path):
    drives, meas = ordered_protocol()
    with zipfile.ZipFile(path) as archive:
        for key, expected in (("drives", drives), ("meas", meas)):
            with archive.open(key + ".npy") as stream:
                header = npy_header(stream)
                assert header == dict(descr="<i2", fortran_order=False, shape=(len(expected), 2))
                assert stream.read() == struct.pack("<" + "hh" * len(expected), *(i for row in expected for i in row))
        headers = {}
        for key in ("v_ref", "v_cur", "images", "base_of_pair"):
            with archive.open(key + ".npy") as stream:
                headers[key] = npy_header(stream)
    assert headers["v_ref"]["shape"][1:] == (TOKENS,) and headers["v_ref"]["descr"] == "<f4"
    assert headers["v_cur"]["shape"] == (100, TOKENS) and headers["v_cur"]["descr"] == "<f4"
    assert headers["images"]["shape"] == (100, 64, 64) and headers["images"]["descr"] in {"<f2", "<f4"}
    assert headers["base_of_pair"]["shape"] == (100,)
    return headers


def selection(rows, preferred):
    eligible = [r for r in rows if r["belt"] == BELT and r["status"] == "done" and r["finite"] == "True"
                and r["code_hash"] == CODE and r["config_hash"] == CONFIG and int(r["n_pairs"]) == 100]
    cases = sorted({r["case"] for r in eligible} & set(preferred))
    rng = random.Random(SEED)
    chosen = sorted(rng.sample(cases, 2))
    units = [r for c in chosen for r in sorted(rng.sample(
        sorted((r for r in eligible if r["case"] == c), key=lambda r: r["unit"]), 4), key=lambda r: r["unit"])]
    return eligible, units


def main():
    manifest = identity(ROOT / "manifest.csv")
    case_file = identity(ROOT / "cases.txt")
    assert manifest["sha256"] == MANIFEST_SHA and case_file["sha256"] == CASES_SHA
    with (ROOT / "manifest.csv").open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == len({r["unit"] for r in rows}) == 14300
    preferred = (ROOT / "cases.txt").read_text(encoding="utf-8-sig").splitlines()
    assert len(preferred) == len(set(preferred)) == 119
    eligible, selected = selection(rows, preferred)
    records = []
    for row in selected:
        unit = row["unit"]
        assert row["file"] == unit + ".npz"
        path = ROOT / "parts" / row["file"]
        side = path.with_suffix(".json")
        meta = json.loads(side.read_bytes())
        item = {k: int(row[k]) if k in {"placement", "contact", "n_pairs"} else row[k]
                for k in ("unit", "case", "placement", "contact", "n_pairs", "belt")}
        assert all(meta[k] == v for k, v in item.items())
        assert (meta["L"], meta["finite"], meta["code_hash"], meta["config_hash"]) == (L, True, CODE, CONFIG)
        arrays = inspect_unit(path)
        item.update(path=str(path), sidecar_path=str(side), subject_id=None, npz_bytes=path.stat().st_size,
                    npz_sha256=sha(path), sidecar_bytes=side.stat().st_size, sidecar_sha256=sha(side), npy_headers=arrays)
        records.append(item)
    assert sum(r["n_pairs"] for r in records) == BATCH * STEPS
    out = dict(protocol="S09_REAL32_ENGINEERING_B32_V1", data_origin="REAL_CORPUS_ENGINEERING_SAMPLES",
               engineering_only=True, formal_split_status="UNKNOWN", subject_mapping_status="UNKNOWN",
               validation_status="NOT_RUN_NO_FORMAL_SPLIT",
               corpus=dict(root=str(ROOT), manifest=manifest, code_hash=CODE, config_hash=CONFIG),
               selection=dict(algorithm="preferred119_sorted_seed2026_two_cases_four_units_each",
                              seed=SEED, cases_txt=case_file, eligible_units=len(eligible), frames=BATCH*STEPS),
               model_protocol=dict(belt=BELT, electrodes=L, drive_offset=SKIP, tokens=TOKENS),
               train=records)
    path = Path("ENGINEERING_DESCRIPTOR.json")
    with path.open("x", encoding="utf-8") as f:
        json.dump(out, f, sort_keys=True, indent=2)
        f.write("\n")
    print("S09_DESCRIPTOR", sha(path), len(records), BATCH*STEPS, len(eligible))


if __name__ == "__main__":
    main()
