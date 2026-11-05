#!/bin/bash
# Connection recovery aid. Read-only; no build, deployment, dataset regeneration or submission.
set -u
H=/home/share/songzhenlong/eitfm
date -u '+%Y-%m-%dT%H:%M:%SZ'
hostname
id
test -d "$H" || exit 2
if test -r /etc/profile.d/donaukit_scheduler.sh; then
  source /etc/profile.d/donaukit_scheduler.sh
fi
for command in dsub djob dnode dqueue numactl gcc g++ clang python3; do
  command -v "$command" || true
done
if command -v djob >/dev/null; then timeout 15 djob; fi
if command -v dqueue >/dev/null; then timeout 15 dqueue; fi
ps -u "$(id -u)" -o pid,ppid,etime,stat,comm
for path in "$H/opt/code/s4_models.py" "$H/opt/code/kml_ops.py" \
  "$H/opt/run_node16.sh" "$H/opt/hbm_alloc.c" "$H/opt/code/kml_sgemm_shim.c" \
  "$H/sw/hbm_alloc/libhbm_alloc.so" "$H/sw/kml_shim/libkml_sgemm_shim.so" \
  "$H/corpus_shape_20261102/code/s2_mesh.py" "$H/corpus_shape_20261102/code/s3_forward.py" \
  "$H/corpus_shape_20261102/code/s6_corpus.py" "$H/corpus_shape_20261102/code/HASHES" \
  "$H/corpus_shape_20261102/cases.txt" "$H/opt/s4/cases/s0322p0/frames.npz" \
  "$H/opt/s4/cases/s0322p1/frames.npz"; do
  if test -f "$path"; then sha256sum "$path"; else printf 'MISSING %s\n' "$path"; fi
done
for path in "$H/opt/stage4_sessions" "$H/opt/s4/reports" "$H/sw/torch_kml"; do
  test ! -d "$path" || ls -ld "$path" "$path"/* 2>/dev/null
done
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$H/sw/torch_kml" python3 -B - <<'PY'
import collections, csv, hashlib, importlib.metadata, importlib.util, json, os, platform, sys
print('python', sys.version, sys.executable, 'arch', platform.machine())
for name in ('torch', 'numpy'):
    try:
        print(name, importlib.metadata.version(name), str(importlib.util.find_spec(name).origin))
    except (importlib.metadata.PackageNotFoundError, AttributeError):
        print(name, 'MISSING')
p = '/home/share/songzhenlong/eitfm/corpus_shape_20261102/manifest.csv'
if os.path.isfile(p):
    print('manifest_sha256', hashlib.sha256(open(p, 'rb').read()).hexdigest())
    with open(p, newline='') as stream:
        rows = list(csv.DictReader(stream))
    print('manifest_rows', len(rows), 'pairs', sum(int(r['n_pairs']) for r in rows))
    for key in ('code_hash', 'config_hash', 'status', 'finite', 'belt'):
        print(key, dict(collections.Counter(r.get(key, 'MISSING') for r in rows)))
    print('unique_cases', len(set(r['case'] for r in rows)))
    print('split_fields', [k for k in rows[0] if 'split' in k] if rows else [])
else:
    print('manifest MISSING', p)
PY
printf 'S00_READONLY_AUDIT_END (not a performance acceptance)\n'
