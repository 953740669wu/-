# S02 R7：连续五次更新的严格门槛与独立内存入口

2026-11-05，Asia/Shanghai。**本轮仅准备，不提交集群，不运行完整模型或训练内存。** R6单步1063/1063 PASS和三个首步配对均是已完成的旧证据，不重复这些实验。新五步尚未C2通过。

## 包与不可变来源

代码包 `package/S02_SEQUENCE5_R7_CODE.zip`，ZIP标准SHA文件 `.zip.sha256`；逐文件大小/SHA/绝对来源见 `package/PACKAGE_MANIFEST.json`。13项R6基础源/环境/标准原字节复制：模型、KML、full_batch_step、原training_step/checkpoint、原比较器、CPU合同/守卫、RSS计量、runtime.env、case清单及协议。旧R6目录及结果不改写；新包不包含旧首步启动器或case/venv。

固定case仍为R3原文件，271979513字节，SHA256=`4de1fb40eb1c4b43a8747586399f336bf9e37184592d66fdbf711abad8469846`。Windows原绝对路径：`E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S02\round3_20261104T134939Z\case\fixed_16_pre.pt`。远端沿用S00已核原文件，只读引用，不复制/重抽权重或输入。

唯一配置：16_adjacent/pre，完整B64/fp32、原mean、原AdamW(lr1e-4/betas0.9,0.999/eps1e-8/wd0.01)、输入梯度保留，CKPT0对原encoder逐层非重入CKPT1。CPU36/KML/HBM0；OMP36/MKL36/OpenBLAS1/cores/close。不改模型、checkpoint算法、阈值或BLAS后端。

## 严格入口：不是五次fresh一步

`check_sequence5.py`在同一进程创建两个隔离模型和各自AdamW，序列开始只加载一次原state。两侧各连续更新5次；每步清理模型和输入梯度，随后调用原R6 mean步。原helper内部的forward后zero_grad仍保留；序列额外在forward前释放上一轮梯度，不改变损失/梯度定义。固定case重复5次，不是新训练数据、长训练或收敛实验。

每步用原比较器检查完整输出、输入/参数梯度、更新后参数、**相对各自上一步参数的增量**、AdamW moments和精确step。每步1063项数字指标，5步全部通过才是5315项；精确state step等额外检查不计入1063。任一步数值失败保留该步完整metrics/failures及先前步骤，立即停止，不执行下一步。

逐步lineage记录原case/SOURCE清单SHA、同一model/optimizer对象标识、真实AdamW步号0→1→…→5、梯度清理、全参数及optimizer状态摘要哈希。下一步before摘要必须等于上一步after，不能靠每步重建optimizer或重装初权重伪造承接。该完整哈希与比较快照只用于严格入口。

每步两侧记录真实KML调用；CPU36保持框架前同PID授权/拓扑/绑定与框架后全部可见TID检查，5步共24个有序checkpoint（3个起点、每步4个、publish）。仍允许close下主线程单核子集，实际Torch必须36。没有新增连续线程采样，不声称所有瞬间或精确OpenMP team已证明。

## 独立内存入口

`train_sequence5.py --checkpoint 0|1`每个进程只建一个模型和一个AdamW、加载一次state；初始化后释放case中的重复初权重。连续5次更新承接参数/moments/步号。没有数值比较快照、输出hook、trace或全状态哈希，两个配置由包装器启动为两个独立进程。

初始化记录RSS/HWM/秒；每步先验证既有步号并清梯度、记录before_reset，按原R6 clear_refs=5机制重置自身HWM，记录training_start，计时原训练步，**计时结束立即读取训练RSS/HWM，然后才校验、读取loss、写入结果元数据和检查线程**。每步验证全部活跃参数及输入梯度、moment有效性和真实AdamW step=1..5，记录实际KML/CPU36。每进程15个有序CPU checkpoint（3起点、initialized、每步2个、publish）。

重置不支持/拒绝则该步不执行；任何状态/梯度/后端/CPU错误立即停止并保留已有及当前局部记录。所有RSS给bytes/MiB(2**20)及秒；是HBM0下进程RSS，包括共享页，不是tensor独占量、PSS或实际HBM驻留。逐步后置验证在计时/HWM读取之外，但可能影响后续allocator驻留；前后RSS据实记录。本五步只称短序列，不能称稳态或正式收益。

`sequence_gate.py`和每个内存进程都要求**当前新包五步严格PASS**：5个完整步骤、各1063项原指标、连续摘要/步号/对象、清梯度、当前case/源SHA、每步双侧KML、24项CPU证据。旧R6单步PASS会在框架/训练前被拒绝。本地已用真实2037034旧PASS原件验证拒绝。内存进程的实际KML/OMP/shim库SHA还须与新五步严格引用一致；不静默换库或fallback。

## 将来交S00的严格命令

先经总协调核新包和有限排期；本轮没有执行以下命令。S00在当前账号全新目录上传ZIP/SHA/清单，核自己的实际队列去重。建议单NUMA申请38物理核、实际36/留末2、总24576MB且limit同值、job最多900秒/HBM0。严格进程780秒+15秒kill；未来内存两个进程各360秒+15秒，合计仍在900秒资源边界内，超限就停并回报，不自动扩预算。

```bash
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
```

输出：`payload/evidence/sequence5_<新job>_strict/checker/result.json`。退出0只接受`PASS_STRICT_SEQUENCE5_SYNTHETIC_ONLY`、completed_steps=5、五步全部原指标通过；1为原判据失败；2为ERROR_RUNTIME_OR_STATE（含连续性/梯度有效性/CPU/库前提错误）；124/137等保留超时/信号终态。失败不改容差、输入、参数、eps或追加控制矩阵。

## 五步PASS后另行安排的内存命令

不与严格job自动串联，不用旧2037034单步PASS替代。新五步通过且总协调明确安排内存job后，沿用上面的RUN/PAYLOAD/CASE，在登录端执行：

```bash
set -euo pipefail
STRICT_JOB=$("$C2_PYTHON" -B -c 'import json,sys;print(json.load(sys.stdin)["data"]["jobId"])' <"$RUN/strict_submission.json")
STRICT_RESULT="$PAYLOAD/evidence/sequence5_${STRICT_JOB}_strict/checker/result.json"
"$C2_PYTHON" -B "$PAYLOAD/sequence_gate.py" "$STRICT_RESULT" >"$RUN/five_step_gate_before_submit.json"
source /etc/profile.d/donaukit_scheduler.sh
(set -o noclobber; printf '%s\n' "$STRICT_RESULT" >"$RUN/memory_submit_once.marker")
dsub -J -q q_hpcai -R 'cpu=38,mem=24576MB' -RL 'mem=24576MB' \
  -a 'numa[count=1,distribution=pack]' -T 900 --env none \
  --cwd "$PAYLOAD" -oo "$RUN/memory_job.log" \
  env S02_CASE_FILE="$CASE" S02_SEQUENCE5_RESULT="$STRICT_RESULT" \
    bash "$PAYLOAD/run_s00_seq5_job.sh" memory \
  >"$RUN/memory_submission.json" 2>"$RUN/memory_submission.stderr.txt"
```

输出：`payload/evidence/sequence5_<新job>_memory/ckpt0|ckpt1/`各自result/command/stdout/exit。只完整两个独立进程、各5步才形成一组短序列诊断；首个失败即停。回传调度原件/实际资源/环境/主机/job/PID、提交与源码清单、CPU授权、全部checker或memory目录，含失败局部记录、门禁引用SHA与退出/清理证据。严格checker的RSS永不作为训练内存。

不修改共享环境、不安装、不重复三组fresh首步、不扩32电极/decoder/多域/长训练或真实HBM。候选保留实验用途、暂不集成；即使五步通过也不自动提升为稳态/生产接受。
