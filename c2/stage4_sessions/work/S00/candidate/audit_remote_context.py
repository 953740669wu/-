"""Return bounded historical log summaries and input statistics, never full logs or helper sources."""
import ast
import base64
import glob
import hashlib
import json
import os
import re
import zipfile
import zlib

H = '/home/share/songzhenlong/eitfm'
out = dict(top_logs={}, provenance={}, dependencies={})
names = ['opt_s4_A1_node16_sync.log', 'opt_s4_A1_node16_b32.log',
         'opt_s4_A1_node16_b32_hbm.log', 'opt_s4_hbm_ab.log',
         'opt_s4_A1_node16_b64ckpt_hbm.log', 'opt_hbm_fix.log']
for name in names:
    path = H + '/logs/' + name
    if os.path.isfile(path):
        raw = open(path, 'rb').read()
        text = raw.decode(errors='replace')
        patterns = ('host ', 'round ', 'node sum', 'conservative', 'gate A1', 'spread',
                    'failed:', 'Bus error', 'Traceback', 'Killed', 'NODE16_DONE',
                    'HBM_FIX_DONE', 'HBM_MB=', 'Job ID', 'JobId', 'Exit Code')
        summary = [line[:400] for line in text.splitlines()
                   if any(token in line for token in patterns)][:120]
        out['top_logs'][name] = dict(sha256=hashlib.sha256(raw).hexdigest(),
            bytes=len(raw), mtime=os.path.getmtime(path), summary=summary,
            host_candidates=sorted(set(re.findall(r'\bcn\d+\b', text))))

def array(path, key):
    with zipfile.ZipFile(path) as archive:
        raw = archive.read(key + '.npy')
    width = 2 if raw[6] == 1 else 4
    n = int.from_bytes(raw[8:8 + width], 'little')
    offset = 8 + width + n
    header = ast.literal_eval(raw[8 + width:offset].decode('latin1').strip())
    return dict(header=header, payload_sha256=hashlib.sha256(raw[offset:]).hexdigest())

for p in (0, 1):
    sources = {}
    for belt in ('16_adjacent', '32_skip4'):
        path = H + '/opt/worker_test/parts/s0322_p%d_%s_c0.npz' % (p, belt)
        if os.path.isfile(path):
            sources[belt] = dict(path=path, images=array(path, 'images'),
                file_sha256=hashlib.sha256(open(path, 'rb').read()).hexdigest())
    demo = H + '/opt/s4/cases/s0322p%d/frames.npz' % p
    out['provenance'][str(p)] = dict(sources=sources, demo_images=array(demo, 'images'))

for path in [H + '/opt/sample_foreign.py',
             '/opt/HPCKit/kml-lib/sme/kblas/multi/libkblas.so']:
    if os.path.isfile(path):
        raw = open(path, 'rb').read()
        row = dict(sha256=hashlib.sha256(raw).hexdigest(), bytes=len(raw))
        out['dependencies'][path] = row
out['numpy_locations'] = glob.glob(H + '/sw/*/numpy') + glob.glob(
    '/home/share/songzhenlong/.local/lib/python3.9/site-packages/numpy')
out['gpu_report_candidates'] = [p for p in glob.glob(H + '/opt/s4/reports/*')
    if any(x in os.path.basename(p).lower() for x in ('gpu', 'cuda', '4090'))]
payload = base64.b64encode(zlib.compress(json.dumps(out).encode(), 9)).decode()
print('S00_CONTEXT_BEGIN')
for i in range(0, len(payload), 64):
    print(payload[i:i + 64])
print('S00_CONTEXT_END')
