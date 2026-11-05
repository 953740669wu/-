"""Bounded, stdlib-only, read-only audit. Emit compressed JSON in terminal-safe lines."""
import ast
import base64
import collections
import datetime
import glob
import hashlib
import json
import math
import os
import platform
import struct
import subprocess
import sys
import zipfile
import zlib

H = '/home/share/songzhenlong/eitfm'


def digest(path):
    with open(path, 'rb') as stream:
        return hashlib.sha256(stream.read()).hexdigest()


def command(args):
    try:
        p = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                           universal_newlines=True, timeout=25)
        return dict(exit_code=p.returncode, output=p.stdout)
    except Exception as error:
        return dict(error=str(error))


out = dict(captured_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
           host=platform.node(), username=os.getlogin(), python=sys.version,
           executable=sys.executable, architecture=platform.machine(), sources={},
           project_write_access=os.access(H, os.W_OK), inputs={}, reports={}, jobs={})
for relative in ['opt/code/s1_prepare.py', 'opt/code/s4_models.py', 'opt/code/kml_ops.py',
                 'opt/run_node16.sh', 'opt/hbm_alloc.c', 'opt/code/kml_sgemm_shim.c',
                 'corpus_shape_20261102/code/s2_mesh.py', 'corpus_shape_20261102/code/s3_forward.py',
                 'corpus_shape_20261102/code/s6_corpus.py', 'corpus_shape_20261102/code/HASHES',
                 'corpus_shape_20261102/cases.txt', 'sw/hbm_alloc/libhbm_alloc.so',
                 'sw/kml_shim/libkml_sgemm_shim.so']:
    path = H + '/' + relative
    if os.path.isfile(path):
        row = dict(sha256=digest(path), bytes=os.path.getsize(path), mtime=os.path.getmtime(path))
        if relative.endswith('.sh') or relative.endswith('/HASHES'):
            row['text'] = open(path).read()
        out['sources'][relative] = row
    else:
        out['sources'][relative] = dict(status='MISSING_OR_UNREADABLE')

import csv
manifest = H + '/corpus_shape_20261102/manifest.csv'
with open(manifest, newline='') as stream:
    rows = list(csv.DictReader(stream))
out['manifest'] = dict(path=manifest, sha256=digest(manifest), rows=len(rows),
    pairs=sum(int(r['n_pairs']) for r in rows), unique_cases=len({r['case'] for r in rows}),
    columns=list(rows[0]), unique_units=len({r['unit'] for r in rows}),
    counts={key: dict(collections.Counter(r.get(key) for r in rows))
            for key in ('code_hash', 'config_hash', 'finite', 'status', 'belt')},
    scope='manifest and source identity only; not all corpus payload checksums')
out['split_candidates'] = sorted(set(glob.glob(H + '/*split*') + glob.glob(H + '/*/*split*')))
out['project_root_entries'] = sorted(os.listdir(H))

for case in ('s0322p0', 's0322p1'):
    path = H + '/opt/s4/cases/' + case + '/frames.npz'
    entry = dict(path=path, sha256=digest(path), bytes=os.path.getsize(path), arrays={})
    with zipfile.ZipFile(path) as archive:
        for name in archive.namelist():
            data = archive.read(name)
            version = data[6:8]
            length_width = 2 if version[0] == 1 else 4
            header_size = int.from_bytes(data[8:8 + length_width], 'little')
            offset = 8 + length_width + header_size
            header = ast.literal_eval(data[8 + length_width:offset].decode('latin1').strip())
            item = dict(header=header, npy_sha256=hashlib.sha256(data).hexdigest())
            key = name[:-4] if name.endswith('.npy') else name
            fmt = {'<f2': '<e', '<f4': '<f', '<f8': '<d'}.get(header['descr'])
            if fmt and (key == 'images' or key.endswith('_v_ref') or key.endswith('_v_cur')):
                values = [v[0] for v in struct.iter_unpack(fmt, data[offset:])]
                item.update(finite=all(math.isfinite(v) for v in values), minimum=min(values),
                            maximum=max(values), elements=len(values))
                if key.endswith('_v_ref'):
                    width = header['shape'][1]
                    means = [sum(abs(v) for v in values[i:i + width]) / width
                             for i in range(0, len(values), width)]
                    item['normalization_denominator_min'] = min(means)
            else:
                item['finite_scan'] = 'NOT_RUN_NONTRAINING_FIELD'
            entry['arrays'][key] = item
    entry['stable_after_read'] = digest(path) == entry['sha256']
    out['inputs'][case] = entry

tags = ['node16_sync_kmlfp32', 'node16_b32_membind', 'node16_b32_hbm',
        'die4_b32_ddr', 'die4_b32_hbm', 'node16_b64ckpt_hbm']
for tag in tags:
    folder = H + '/opt/s4/reports/' + tag
    files = []
    for path in sorted(glob.glob(folder + '/r*_d*.json')):
        raw = open(path, 'rb').read()
        log = path[:-5] + '.log'
        row = dict(name=os.path.basename(path), sha256=hashlib.sha256(raw).hexdigest(),
                   mtime=os.path.getmtime(path), data=json.loads(raw))
        if os.path.isfile(log):
            text = open(log, errors='replace').read()
            row['log'] = dict(sha256=digest(log), mtime=os.path.getmtime(log),
                errors=[line for line in text.splitlines() if any(s in line.lower()
                    for s in ('traceback', 'killed', 'bus error', 'memoryerror', 'timeout', 'hbm_alloc:'))][-12:])
        row['stable_after_read'] = digest(path) == row['sha256']
        files.append(row)
    out['reports'][tag] = dict(path=folder, files=files,
        log_without_json=[os.path.basename(p) for p in sorted(glob.glob(folder + '/r*_d*.log'))
                          if not os.path.isfile(p[:-4] + '.json')])

for user in ('dengqingtian', 'songzhenlong'):
    out['jobs'][user] = command(['bash', '-c',
        'source /etc/profile.d/donaukit_scheduler.sh; djob -w -u ' + user])
out['processes_project_owner_login_host'] = command(
    ['ps', '-u', 'songzhenlong', '-o', 'pid,ppid,etime,stat,comm'])
out['login_gcc'] = command(['gcc', '--version'])
out['login_numactl'] = command(['numactl', '--hardware'])
out['live_launcher_syntax'] = command(['bash', '-n', H + '/opt/run_node16.sh'])
out['source_launcher_stable_after_audit'] = digest(H + '/opt/run_node16.sh') == out['sources']['opt/run_node16.sh']['sha256']
payload = base64.b64encode(zlib.compress(json.dumps(out).encode(), 9)).decode()
print('S00_JSON_BEGIN')
for i in range(0, len(payload), 64):
    print(payload[i:i + 64])
print('S00_JSON_END')
