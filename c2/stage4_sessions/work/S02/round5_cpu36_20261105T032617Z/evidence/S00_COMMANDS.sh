set -euo pipefail
RUN=/home/share/dengqingtian/opt/stage4_sessions/S00/S02_CPU36_R5_20261105T032617Z
PAYLOAD="$RUN/payload"
cd "$RUN"
sha256sum -c S02_CPU36_R5_CODE.zip.sha256
mkdir "$PAYLOAD"  # 已存在则停止，避免覆盖/重复执行
unzip -q S02_CPU36_R5_CODE.zip -d "$PAYLOAD"
# 若引用远端已有的同一原文件，仅将 CASE 改为其确切绝对路径。
CASE="$RUN/fixed_16_pre.pt"
source "$PAYLOAD/interfaces/cluster_runtime.env"
export S02_PAYLOAD="$PAYLOAD" S02_CASE_FILE="$CASE"
# 仅文件/语法核验，不导入框架或再次运行启动测试。
"$C2_PYTHON" -B - >"$RUN/pre_submit_checks.json" <<'PY'
import ast, hashlib, json, os, subprocess
from pathlib import Path
root = Path(os.environ['S02_PAYLOAD'])
manifest = json.loads((root / 'SOURCE_SHA256.json').read_text())
entries = {}
for name, expected in manifest.items():
    path = root / name
    data = path.read_bytes()
    assert hashlib.sha256(data).hexdigest() == expected, name
    entries[name] = dict(sha256=expected, bytes=len(data))
    if path.suffix in ('.sh', '.env'):
        assert b'\r' not in data, name
        subprocess.run(['bash', '-n', str(path)], check=True)
    if path.suffix == '.py':
        ast.parse(data.decode('utf-8'), filename=name, feature_version=(3, 9))
case = Path(os.environ['S02_CASE_FILE'])
frozen = json.loads((root / 'CASE_MANIFEST.json').read_text())
h = hashlib.sha256()
with case.open('rb') as stream:
    for block in iter(lambda: stream.read(1024 * 1024), b''):
        h.update(block)
assert case.stat().st_size == frozen['bytes'] and h.hexdigest() == frozen['sha256']
print(json.dumps(dict(status='SHA_LF_LINUX_SYNTAX_ONLY', files=entries,
    case_path=str(case), case_sha256=h.hexdigest(), case_bytes=case.stat().st_size), indent=2))
PY
# 一次性提交标记；失败也保留，交 S00 按有界包装修复处理。
(set -o noclobber; printf '%s\n' "$PAYLOAD" >"$RUN/submit_once.marker")
dsub -J -q q_hpcai -R 'cpu=38,mem=24576MB' -RL 'mem=24576MB' \
  -a 'numa[count=1,distribution=pack]' -T 900 --env none \
  --cwd "$PAYLOAD" -oo "$RUN/job.log" \
  env S02_CASE_FILE="$CASE" bash "$PAYLOAD/run_s00_job.sh" \
  >"$RUN/submission.json" 2>"$RUN/submission.stderr.txt"
