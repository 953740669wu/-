# S02 R6：完整B64 / CKPT0对CKPT1

2026-11-05，Asia/Shanghai。**仅候选和入口准备；本轮没有集群提交、完整模型验证或训练内存实测。**

## 包、来源与配置

代码包 `package/S02_CKPT64_R6_CODE.zip`；校验文件 `.zip.sha256`；逐文件SHA/大小/来源见 `package/PACKAGE_MANIFEST.json`，执行源SHA见 `SOURCE_SHA256.json`。新包不包含venv、旧结果或固定case。

原固定case：`E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S02\round3_20261104T134939Z\case\fixed_16_pre.pt`，271979513字节，SHA256=`4de1fb40eb1c4b43a8747586399f336bf9e37184592d66fdbf711abad8469846`。沿用同一原文件，不重新生成输入或权重。S00上一轮已上传到 `/home/share/dengqingtian/opt/stage4_sessions/S00/S02_CPU36_R5_20261105T034705Z/fixed_16_pre.pt`，可核验后直接只读引用。

唯一数值组：16_adjacent/pre，完整B64×1参考CKPT0对完整B64×1候选CKPT1，backend=kml/mode=checkpoint_strict，fp32/fresh/HBM0。保留原mean表达式、mask/随机张量、AdamW(lr1e-4, betas0.9/0.999, eps1e-8, weight_decay0.01)和单次step，原严格比较器/阈值逐字节保留。候选仅使用冻结 `candidate/training_step.py::enable_checkpoint`，即原encoder逐层 `use_reentrant=False` 包装。两个模型实例隔离，参考完成后释放实例，再构造候选并加载同一state；参考实例未被包装。

R5的B32×2原记录保持FAIL（C2为95/1063项），不再作为新候选。新checker mode/config/status均明确CKPT0/1与B64，不把新结果改写成R5通过。两个路径均须观测真实KML调用；CPU36、全可见TID、实际库路径/SHA及结束重验保持。

## 将来由S00执行的严格对照命令

总协调核验新包并明确安排执行后才执行本节。本轮S02未运行以下命令，不重跑R7/九项Windows实验或环境安装。只一组，首选申请38核、实际36物理核/留末2核，24576MB且内存limit同值，900秒/HBM0；内层780秒+15秒kill宽限。

将ZIP、ZIP.sha256和PACKAGE_MANIFEST上传到全新 `RUN`。以下命令只在S00账号自有新目录操作：

```bash
set -euo pipefail
RUN=/home/share/dengqingtian/opt/stage4_sessions/S00/S02_CKPT64_R6_20261105T043038Z
PAYLOAD="$RUN/payload"
CASE=/home/share/dengqingtian/opt/stage4_sessions/S00/S02_CPU36_R5_20261105T034705Z/fixed_16_pre.pt
cd "$RUN"
sha256sum -c S02_CKPT64_R6_CODE.zip.sha256
mkdir "$PAYLOAD"
unzip -q S02_CKPT64_R6_CODE.zip -d "$PAYLOAD"
source "$PAYLOAD/interfaces/cluster_runtime.env"
export S02_PAYLOAD="$PAYLOAD" S02_CASE_FILE="$CASE"
# 只检查文件/语法，不导入框架、不运行启动测试。
"$C2_PYTHON" -B - >"$RUN/pre_submit_checks.json" <<'PY'
import ast, hashlib, json, os, subprocess
from pathlib import Path
root = Path(os.environ['S02_PAYLOAD'])
sources = json.loads((root / 'SOURCE_SHA256.json').read_text())
for name, expected in sources.items():
    path = root / name
    data = path.read_bytes()
    assert hashlib.sha256(data).hexdigest() == expected, name
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
assert h.hexdigest() == frozen['sha256'] and case.stat().st_size == frozen['bytes']
print(json.dumps(dict(status='SHA_LF_SYNTAX_ONLY', source_sha256=sources,
                     case_sha256=h.hexdigest(), case_bytes=case.stat().st_size), indent=2))
PY
# runtime.env会重设PATH；沿用S00实测修正，恢复调度CLI后才提交。
source /etc/profile.d/donaukit_scheduler.sh
command -v dsub
(set -o noclobber; printf '%s\n' "$PAYLOAD" >"$RUN/strict_submit_once.marker")
dsub -J -q q_hpcai -R 'cpu=38,mem=24576MB' -RL 'mem=24576MB' \
  -a 'numa[count=1,distribution=pack]' -T 900 --env none \
  --cwd "$PAYLOAD" -oo "$RUN/strict_job.log" \
  env S02_CASE_FILE="$CASE" bash "$PAYLOAD/run_s00_job.sh" equivalence \
  >"$RUN/strict_submission.json" 2>"$RUN/strict_submission.stderr.txt"
```

新job同PID捕获授权、比对receipt并在框架导入前绑定36核；实际Torch必须36，OMP36/MKL36/OpenBLAS1/cores/close。7个有序CPU checkpoint保持。输出为 `payload/evidence/c2_<新job>_checkpoint_strict/`。真实Linux bash-n、实际ABI/KML/TID和完整数值结果仍待S00；本地语法/替身检查不能替代它们。

退出0且result.status=`PASS_STRICT_CHECKPOINT_SYNTHETIC_ONLY`仅为本固定case通过；退出1且`FAIL_ORIGINAL_CRITERIA`保留所有失败；退出2为运行前提错误；124/137等为超时/信号。不得更改阈值、eps、梯度、模型、样本或自动追加矩阵。

## 独立轻量内存入口：待数值通过及另行安排

`train_memory.py --checkpoint 0|1`每次仅构造一个完整模型，读取同一case，核对身份并释放重复初权重；原mean前向/反向和一次fresh AdamW由与checker相同的 `candidate/full_batch_step.py` 执行。保留相同输入梯度工作量，decoder参数存在且保持不活跃。没有逐参数/梯度/输出比较快照，没有输出hook/trace、预热或累计训练。

`run_c2_memory.sh`分别启动两个独立Python进程（CKPT0、CKPT1），各有CPU36同PID守卫及真实KML身份；每个进程360秒+15秒kill，总job仍900秒/24576MB/HBM0。两个result的PID、阶段及输入身份独立记录，首个失败即停。

阶段测量：初始化从守卫/框架导入至模型/case/optimizer准备结束，记录初始化elapsed和RSS高水位；训练前对**自身进程** `/proc/self/clear_refs` 写5以重置RSS高水位，再记录一次训练步elapsed及VmHWM。若不支持或权限拒绝，退出2且不执行训练，不能拿生命周期高水位冒充独立训练峰值。行为依据[Linux内核proc文档](https://docs.kernel.org/filesystems/proc.html)的clear_refs=5定义；Linux真实计数重置本轮未运行。

字段同时给bytes与MiB(2**20 bytes)、秒；是HBM0下整个进程RSS，包括共享库页，非tensor独占量、PSS或物理HBM驻留。HugetlbPages要求0。训练峰值在后置校验/JSON/线程库检查前读取，初始化峰值单独保留。单次fresh步包含AdamW首次状态分配，不能当作稳态吞吐或已接受的内存收益。

门禁 `memory_gate.py`要求本R6严格PASS、完整1063项原metrics、当前case/源SHA、两个路径实际KML调用和完整CPU36证据；R5 FAIL、控制PASS、旧源码或缺证据均拒绝。该门禁不授权提交。本轮不自动运行它或内存job。

仅在新严格结果完成且总协调另行安排轻量内存执行后，S00可在同一已核验payload使用：

```bash
# 以上RUN/PAYLOAD/CASE沿用；此段不与严格job自动串联。
set -euo pipefail
STRICT_JOB=$("$C2_PYTHON" -B -c 'import json,sys; print(json.load(sys.stdin)["data"]["jobId"])' <"$RUN/strict_submission.json")
STRICT_RESULT="$PAYLOAD/evidence/c2_${STRICT_JOB}_checkpoint_strict/result.json"
"$C2_PYTHON" -B "$PAYLOAD/memory_gate.py" "$STRICT_RESULT" >"$RUN/memory_gate_before_submit.json"
source /etc/profile.d/donaukit_scheduler.sh
(set -o noclobber; printf '%s\n' "$STRICT_RESULT" >"$RUN/memory_submit_once.marker")
dsub -J -q q_hpcai -R 'cpu=38,mem=24576MB' -RL 'mem=24576MB' \
  -a 'numa[count=1,distribution=pack]' -T 900 --env none \
  --cwd "$PAYLOAD" -oo "$RUN/memory_job.log" \
  env S02_CASE_FILE="$CASE" S02_EQUIVALENCE_RESULT="$STRICT_RESULT" \
    bash "$PAYLOAD/run_s00_job.sh" memory \
  >"$RUN/memory_submission.json" 2>"$RUN/memory_submission.stderr.txt"
```

回传本次job调度命令/资源/终态/日志、全部pre-submit身份和payload证据目录；strict包括全部metrics/failures、optimizer_details、双方KML调用和CPU证据。未来memory包括门禁引用、两个独立进程的命令/退出/stdout/result及分阶段RSS/时间。不扩32电极、decoder数值、多域、长训练或真实HBM。候选准备、C2数值通过、内存测量和收益接受分别记录。
