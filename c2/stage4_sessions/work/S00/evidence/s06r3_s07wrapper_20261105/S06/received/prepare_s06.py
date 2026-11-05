import ast,json,hashlib,subprocess,zipfile,os
from pathlib import Path
r=Path(__file__).resolve().parent
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
m=json.loads((r/'EXECUTION_FILES.json').read_text())
for n,h in m.items(): assert sha(r/n)==h,n
z=r/'S06_R3_PAYLOAD.zip';assert z.stat().st_size==33571
with zipfile.ZipFile(z) as f:
 assert len(f.namelist())==14 and all(n.startswith('payload/') and '..' not in Path(n).parts for n in f.namelist())
 assert not (r/'payload').exists(); f.extractall(r)
files={str(p.relative_to(r)):sha(p) for p in (r/'payload').rglob('*') if p.is_file()}
for p in list((r/'payload').rglob('*'))+list(r.glob('*.py'))+list(r.glob('*.sh')):
 if not p.is_file():continue
 if p.suffix in ('.py','.sh','.env'):
  assert b'\r' not in p.read_bytes(),str(p)
  if p.suffix=='.py':ast.parse(p.read_text(),filename=str(p),feature_version=(3,9))
  else:subprocess.run(['bash','-n',str(p)],check=True)
subprocess.run(['sha256sum','-c','ARTIFACT_SHA256.txt'],cwd=str(r/'payload'),check=True,stdout=(r/'payload_manifest_check.txt').open('w'))
paths=['/usr/bin/python3','/usr/bin/g++','/usr/bin/numactl','/usr/bin/timeout','/home/share/dengqingtian/opt/stage4_sessions/S00/ENV_20261104T130730Z_R4/venv/bin/python3']
for p in paths:assert os.access(p,os.X_OK),p
pre=dict(status='PASS_REMOTE_ORIGINAL_SHA_LF_LINUX_SYNTAX',payload_files=files,package_sha256=m['S06_R3_PAYLOAD.zip'],wrapper_files={p.name:sha(p) for p in r.iterdir() if p.is_file() and p.suffix in ('.py','.sh')},login_path_checks=paths,compute_environment_not_inferred=True)
(r/'pre_submit_checks.json').write_text(json.dumps(pre,indent=2)+'\n')
print(json.dumps(dict(status=pre['status'],original_files=len(files),package_sha256=pre['package_sha256'])))
