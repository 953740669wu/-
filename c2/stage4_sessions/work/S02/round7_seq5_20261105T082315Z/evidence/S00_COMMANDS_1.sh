set -euo pipefail
RUN=/home/share/dengqingtian/opt/stage4_sessions/S00/S02_SEQUENCE5_R7_20261105T082315Z
PAYLOAD="$RUN/payload"
CASE=/home/share/dengqingtian/opt/stage4_sessions/S00/S02_CPU36_R5_20261105T034705Z/fixed_16_pre.pt
cd "$RUN"
sha256sum -c S02_SEQUENCE5_R7_CODE.zip.sha256
mkdir "$PAYLOAD"
unzip -q S02_SEQUENCE5_R7_CODE.zip -d "$PAYLOAD"
source "$PAYLOAD/interfaces/cluster_runtime.env"
export S02_PAYLOAD="$PAYLOAD" S02_CASE_FILE="$CASE"
# 标准库文件/语法检查；不导入框架，不重复R7完整启动。
"$C2_PYTHON" -B - >"$RUN/pre_submit_checks.json" <<'PY'
import ast,hashlib,json,os,subprocess
from pathlib import Path
root=Path(os.environ['S02_PAYLOAD'])
sources=json.loads((root/'SOURCE_SHA256.json').read_text())
for name,expected in sources.items():
    path=root/name;data=path.read_bytes()
    assert hashlib.sha256(data).hexdigest()==expected,name
    if path.suffix in ('.sh','.env'):
        assert b'\r' not in data,name
        subprocess.run(['bash','-n',str(path)],check=True)
    if path.suffix=='.py':ast.parse(data.decode('utf-8'),filename=name,feature_version=(3,9))
case=Path(os.environ['S02_CASE_FILE']);frozen=json.loads((root/'CASE_MANIFEST.json').read_text())
h=hashlib.sha256()
with case.open('rb') as stream:
    for block in iter(lambda:stream.read(1024*1024),b''):h.update(block)
assert h.hexdigest()==frozen['sha256'] and case.stat().st_size==frozen['bytes']
print(json.dumps(dict(status='SHA_LF_SYNTAX_ONLY',source_sha256=sources,case_file_sha256=h.hexdigest()),indent=2))
PY
# 仅登录侧恢复调度CLI；计算节点包装不source登录端profile。
source /etc/profile.d/donaukit_scheduler.sh
command -v dsub
(set -o noclobber; printf '%s\n' "$PAYLOAD" >"$RUN/strict_submit_once.marker")
dsub -J -q q_hpcai -R 'cpu=38,mem=24576MB' -RL 'mem=24576MB' \
  -a 'numa[count=1,distribution=pack]' -T 900 --env none \
  --cwd "$PAYLOAD" -oo "$RUN/strict_job.log" \
  env S02_CASE_FILE="$CASE" bash "$PAYLOAD/run_s00_seq5_job.sh" strict \
  >"$RUN/strict_submission.json" 2>"$RUN/strict_submission.stderr.txt"
