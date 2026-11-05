# S02 R5 CPU36：S00 一组严格数值对照交付

日期：2026-11-05，Asia/Shanghai。**PREPARED_LOCAL_ONLY / C2_KML_NOT_RUN / MEMORY_NOT_RUN**。

R7/job2034247 已通过协调和 S01 审核，NO_S01_BLOCKER_FOR_S02；不再提交环境/完整启动测试。本包只运行一次 `16_adjacent/pre --backend kml --mode strict`，有效 B64 对 micro32×2，fp32/CKPT0/fresh/HBM0。不循环九项因果模式，不开展训练内存/HBM测试。

## 载荷与冻结身份

- 本轮代码 ZIP：`package/S02_CPU36_R5_CODE.zip`。ZIP、逐项 SHA/大小/来源见同目录 `PACKAGE_MANIFEST.json`；标准校验文件为 `S02_CPU36_R5_CODE.zip.sha256`。不能使用 R3/旧 S00 包 SHA。
- case 独立于代码包，**不重新生成、不在本地再复制**：`E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S02\round3_20261104T134939Z\case\fixed_16_pre.pt`。
  大小 **271979513** 字节；SHA256 **4de1fb40eb1c4b43a8747586399f336bf9e37184592d66fdbf711abad8469846**。
  若远端已有同一文件，核验后可直接设置 `S02_CASE_FILE` 引用；否则由 S00 上传同一原文件到新的账号自有目录。
- `CASE_MANIFEST.json` 保持 R3 原字节；模型、training_step、loader、原比较器、配对协议与阈值原字节不变。加载后再次核对初始权重和固定张量身份。
- `cpu36_contract.py` 原样来自 S01 R7，SHA256 **3990bb6ba40e7d4e47037aef245c6bc971191e7ae2c4be8701dd329c408a179d**。
- `interfaces/cluster_runtime.env` 原样来自 S01 R7，SHA256 **32248af7857b7fd1616b19899c1411a4a59f9378c9231f0ec56f6c922ec2866d**。复用已核验的 R4 venv、KML、BiSheng OMP 与原 shim；S00 在实际节点核对其仍可用，不安装新环境。

## CPU36 包装与同 PID 守卫

固定环境 `OMP_NUM_THREADS=36 MKL_NUM_THREADS=36 OPENBLAS_NUM_THREADS=1 OMP_PLACES=cores OMP_PROC_BIND=close`。不调用 `torch.set_num_threads` 覆盖观测值；实际 Torch intra-op 必须为36，否则退出2。

包装器先用标准库读取本次继承授权及 NUMA/物理核拓扑，写 `cpu_allocation.json`。要求单一38物理核域：分配38时选择该域前36、预留末2；分配36时必须恰好为该域前36。37核、跨域、含预留核的错误36核集合均拒绝。若继承掩码没有体现调度分配，不凭整机608核推断授权，由 S00 纠正本次作业外层绑定；不得扩大权限。

`numactl --physcpubind=<原授权集合> --membind=<实际域>` 保留授权直到 checker 启动。**checker 在同一 PID、Torch/NumPy/候选模块导入前重读授权和拓扑，核对同 job/host/receipt；随即用 sched_setaffinity 收窄到选中36核。** 模型只在该36核边界中执行。分配38与实际使用36分别记录，不把初始38核掩码误报为模型计算掩码。

同 PID 的7个有序 checkpoint：before_framework、after_framework、after_backend、before_reference、after_reference、after_candidate、publish。各次枚举全部可见 TID，拒绝空/重复/缺失/不完整/越界证据；框架导入后核对实际 Torch36、interop、parallel_info，以及已加载 OpenMP max API=36。允许 close 下调用线程为合法单核子集。证据含 PID、时间、所有 TID 掩码、tick/state/last_cpu、实际模块路径、库 SHA/API；TID 总数不被当作 Torch 线程配置。

保留原 kml_ops 真实加载/直接 GEMM 计数和形状，记录 KML/shim/OpenMP 映射路径和 SHA，结束重验库身份。缺库、缺 GEMM、库漂移、CPU/线程错误均为运行前提错误，不静默回退 native。这里是7个 checkpoint 的全部可见 TID 证据，没有新增常驻采样线程；不能证明 checkpoint 之间每个瞬间或精确 OpenMP in-region team。R7 的50ms父采样只属于其启动证据，不冒充本次结果。

## S00 的实际命令

以下供 S00 在现有登录会话执行，**S02 没有执行提交命令**。总协调核验本包后，S00 先确认自己的队列中尚无这一组任务。最多一组对照，首选申请38核/实际计算36核，24576MB且 resLimit.mem 同值，900秒上限。内部为780秒+15秒强制结束宽限。

将 ZIP、ZIP.sha256、PACKAGE_MANIFEST.json 放入全新的 `/home/share/dengqingtian/opt/stage4_sessions/S00/S02_CPU36_R5_20261105T032617Z`；固定文件可放在此目录 `fixed_16_pre.pt`。旧 R3 四核入口不再执行，不覆盖旧 payload。

```bash
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
```

实际 job 内 run_s00_job.sh source 冻结 runtime.env 后只执行 `bash run_c2_diagnostic.sh strict`。资源/时限与状态由 S00 保存原始调度回执；包装器不凭节点总内存推断作业额度，也不把24GiB申请当作已独立证明内存硬限。不得附加到已结束 job2034247。

## 判读、回传与停止条件

- 退出0：`PASS_STRICT_SYNTHETIC_ONLY`，仅该合成 case 原严格判据通过。
- 退出1且 result.status=`FAIL_ORIGINAL_CRITERIA`：数值不通过；保留全部 metrics/failures，不改阈值/eps/梯度求PASS，不追加控制矩阵。
- 退出2：`ERROR_RUNTIME_OR_INPUT` 或包装前提错误；缺 result/metrics 不能解释成数值通过。检查 identity_error/allocation_error/stdout。
- 124/137等：超时或信号终止，记录真实退出，不作数值结论；调度 SUCCEEDED 不能代替 checker/result 一致性。

回传 job.log、submission 原件、实际资源/终态/命令、pre_submit_checks、全部 `payload/evidence/c2_<新job>_strict/`，包括失败残留：identity_check、cpu_allocation、placement、command、stdout_stderr、checker_exit_code、result。result 要求具备 case/源身份、实际 KML调用与库 SHA、7项 CPU36证据、原阈值全部数值指标和结束状态，数值FAIL也完整回传。运行前提失败只报告错误，不扩大或重跑Windows模型。

Windows 严格194项失败和九项因果实验保留在 R3；C2结果独立记账。M2仍未通过，训练内存/HBM未解锁，没有性能/内存收益接受结论。
