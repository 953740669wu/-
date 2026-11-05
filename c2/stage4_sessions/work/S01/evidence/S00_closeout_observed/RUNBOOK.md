# S00 可复现命令与资源门槛

本地10项检查及获授权的远程版本/历史结果/输入统计核查已完成。没有创建远程文件、构建或提交计算作业。17:00与17:09启动器快照已冻结，详见REMOTE_AUDIT.md。以下构建/性能命令仍是准备稿，正式验收前由S01接受可靠运行器。

## 0. 已接受交接后的恢复条件

总协调已接受S00证据交接；当前文档整理后收尾，不启动新基线。运行器修复由S01负责，输入适配与内存优化由S02负责。待补资料/责任/完成标准见PENDING_ITEMS.md，收尾状态见evidence/closeout_status.json。

恢复时先取得**总协调已接受的S01运行器报告、版本SHA清单和实际启动命令**，同时确认适用的运行环境、S02输入协议/证据及资源排期。然后严格按**单域→四域→整节点**推进；前一级不通过不扩大。原始核查的账号/作业/共享文件/资源信息是2026-11-04快照，恢复时刷新。

下方旧隔离入口和配置继续保留，作为源码/路径与历史计时协议参考，不是直接重建新性能基线的授权或已验收运行器。实际命令和参数接口以S01接受版本为准；不得只改日志标签却继续执行旧入口/共享代码。新的输入协议由S02标明版本，不能静默延续已知的16电极图像错配。

## 1. 本地复核（PowerShell）

```powershell
Set-Location -LiteralPath 'E:\eitfm_c2_stages2-4_2026-11-03'
python -B 'c2\stage4_sessions\work\S00\tests\test_baseline.py'
python -B 'c2\stage4_sessions\work\S00\tests\test_remote_analysis.py'
python -B 'c2\stage4_sessions\work\S00\analyze_remote_results.py'
Get-Content -LiteralPath 'c2\stage4_sessions\work\S00\evidence\source_sha256.txt'
Get-Content -LiteralPath 'c2\stage4_sessions\work\S00\evidence\source_integrity.json'
```

`prepare_baseline.py` 的作用是首次冻结和重新采集本机环境；副本与源文件不同时会拒绝覆盖。无需重跑它来“复核”已经冻结的环境记录。`collect_history.py` 仅重建文档转录表。

## 2. 已核实的连接与后续只读核查（PowerShell）

当前确认账号为dengqingtian，已成功登录10.44.9.4，落点login10。使用交互密码认证，密码不写入脚本／配置。VPN已经连接，无需重复原手册步骤；项目脚本中的songzhenlong是项目拥有者，不是本session登录账号。

```powershell
ssh -o PubkeyAuthentication=no -o ConnectTimeout=12 -o StrictHostKeyChecking=yes -o UserKnownHostsFile=E:/eitfm_c2_stages2-4_2026-11-03/c2/stage4_sessions/work/S00/evidence/known_hosts_10.44.9.4 dengqingtian@10.44.9.4
```

用户已经明确授权限定证据保存，audit_remote_details.py及收紧为摘要/哈希/输入统计的audit_remote_context.py已执行并保存JSON；没有import torch或训练。当前账号既有作业不代表S00资源。真实split仍缺，cases.txt不能代替split。完整日志及辅助/环境脚本正文未返回，不属于当前已完成证据包。

## 3. 冻结远程任务副本（S01验收及资源排期后）

当前账号对共享项目无写权限。后续任务独立路径改为 `/home/share/dengqingtian/opt/stage4_sessions/S00/<unique_run_id>/`；共享项目只作只读来源。本次尚未创建或上传。每个配置／1、4、16域分别使用不同run_id；baseline保留相对导入，candidate放独立入口，lib只放本任务库。没有自动dsub。

在**已分配的 C2 compute job** 中，假设本任务包已复制到唯一目录且路径已核验，运行：

```bash
set -euo pipefail
H=/home/share/songzhenlong/eitfm
export S00_RUN=/home/share/dengqingtian/opt/stage4_sessions/S00/REPLACE_WITH_UNIQUE_RUN_ID
cd "$S00_RUN"
sha256sum -c evidence/baseline_sha256.txt
bash -n candidate/build_isolated.sh
bash -n candidate/run_node16_isolated.sh
bash candidate/build_isolated.sh
gcc --version > lib/gcc_version.txt
sha256sum /opt/HPCKit/kml-lib/sme/kblas/multi/libkblas.so > lib/kml_SHA256.txt
```

build_isolated.sh要求S00_RUN在当前账号自己的S00根下，mkdir lib拒绝覆盖；模型零改动。旧run_hbm_ab/run_hbm_fix/run_kml_shim只作冻结证据，不直接执行其共享sw写入。两个独立shell入口已在远程通过bash -n；本地Git Bash初始化受限。实际编译、动态加载及训练未运行。

## 4. 复制既有 demo 输入并核对实际加载路径

不重跑历史数据适配器，不生成数据；先检查已存在 NPZ 的字段、shape、dtype、finite、分母、帧身份、图像归属与来源哈希。不通过时交协调聊天决定，不静默改 demo。

当前已核实训练字段shape/dtype/finite和非零分母，但16电极demo images确实来自不同的32电极源单元。下列复制只用于保持历史计时兼容；正式科学训练前先由协调明确目标协议，不能静默复制该目标错误继续做效果验证。

```bash
: "${S00_RUN:?}"
: "${S00_INPUT_ROOT:?set the read-only, audited demo root containing cases/}"
mkdir -p "$S00_RUN/output/cases"
for c in s0322p0 s0322p1; do
  mkdir "$S00_RUN/output/cases/$c"
  cp -- "$S00_INPUT_ROOT/cases/$c/frames.npz" "$S00_RUN/output/cases/$c/frames.npz"
done
sha256sum "$S00_RUN"/output/cases/*/frames.npz > "$S00_RUN/output/input_SHA256SUMS"
export PYTHONDONTWRITEBYTECODE=1
export PYTHONPATH="$H/sw/torch_kml:$S00_RUN/baseline"
export LD_LIBRARY_PATH=/opt/HPCKit/kml-lib/sme/kblas/multi:/opt/HPCKit/kml-lib:/opt/HPCKit/bisheng-lib
export KML_BLAS_LIB=/opt/HPCKit/kml-lib/sme/kblas/multi/libkblas.so
LD_PRELOAD="$S00_RUN/lib/libkml_sgemm_shim.so" python3 -B - <<'PY'
import importlib.util, os, sys
import torch, kml_ops
print(sys.executable, sys.version)
print('torch', torch.__version__, torch.__file__)
print('s4', importlib.util.find_spec('s4_models').origin)
print('kml_ops', kml_ops.__file__, 'KML', os.environ['KML_BLAS_LIB'])
assert os.path.realpath(kml_ops.__file__).startswith(os.path.realpath(os.environ['S00_RUN']) + '/')
assert importlib.util.find_spec('s4_models').origin == os.environ['S00_RUN'] + '/baseline/s4_models.py'
print(torch.__config__.show())
for line in open('/proc/self/maps'):
    if any(token in line for token in ('libkblas', 'libgomp', 'libomp', 'libopenblas', 'libkml_sgemm')):
        print(line.rstrip())
PY
```

输入 SHA、torch/依赖库哈希、实际 OMP runtime 加载路径、授权 CPU 集合及 HBM node 映射不齐时，不开始计时。共享 torch_kml 只是只读依赖，仍须冻结版本；独立源码／`.so` 不能替代该检查。

## 5. 显式计时配置（仅在上一门槛通过后）

以下为一域 DDR B32 的**准备命令**。`NDOM` 每个新 run_id 按 1→4→16 单独设置；先完成单域的真实输入、完整 forward/backward/AdamW 检查及 HBM 放置检查再扩大。`baseline_configs.json` 是机器可读版本。这里只准备命令，没有把未运行检查填成通过。

```bash
env DEVICE=cpu AMP=fp32 BATCH=32 CHANNELS_LAST=0 COMPILE=0 MKLDNN=1 \
  KML_CONV=0 KML_LINEAR=1 LINEAR_DTYPE=fp32 CKPT=0 SAMPLING=0 GN=0 \
  BELTS=16_adjacent,32_skip4 PARTS=pre,dec REPS=5 ROUNDS=3 \
  HBM=0 HBM_MB=3800 HBM_MIN_KB=256 HBM_STATS=1 MEMPOL=membind SKIP_BUSY=1 NDOM=1 \
  PYTHONDONTWRITEBYTECODE=1 \
  bash "$S00_RUN/candidate/run_node16_isolated.sh" DDR_B32_N1
```

HBM B32 用独立 run_id，命令仅将 `HBM=1`、tag 改为 `HBM_B32_N1`；B64/preferred 也是独立 run_id，将 `BATCH=64 HBM=0 MEMPOL=preferred`，tag 改为 `DDR_B64_PREFERRED_N1`。三套配置均 CKPT=0；B64+CKPT+HBM 归 S01，不在这里追加实验。

旧入口不接受正确性检查参数；S00 没有新增 torch 数值验收器。S01/S02 必须先准备所需 checks；原 check_linear 不能覆盖完整门槛。正式接受前使用 S01 接受的运行器；S00 隔离版只用于说明固定代码应如何导入和输出，不因打印 NODE16_DONE 即接受。

每次还须从进程 `/proc/<pid>/maps` 核实 HBM、shim、KML、OMP 库，记录实际主机／job、CPU affinity／线程数、每 node hugepages 前后值、DDR/HBM 峰值方法、每域退出码与新 JSON。baseline/candidate 同主机、同输入／有效批量／精度，用 A/B 或 A/B/A 排序。三个有效独立轮才计算稳定性，缺域／过期／超时整轮无效；只有有效轮可报 sum、median、min 和 N_expected×min。S01 接受的稳定性版本需第二主机复测。

## 6. 待协调的有限资源方案

本次实际消耗：**0 作业、0 节点小时**。未发现本 session 已安排的 compute allocation，不新增 dsub。

建议按门槛逐项排期，以下为**预算上限建议，不是时间预测或授权**：

| 门槛 | 配置 | 最大预算建议 | 继续条件 |
|---|---|---|---|
| 只读审计 | 别名、作业、源码、输入、工具链、split | 不分配计算节点 | 证据齐、无并发冲突 |
| 单域 | DDR B32 与 HBM B32，四个 workload；正确性／放置先行 | 1 节点×0.5h | 没有错误／异常内存／缺梯度／输入问题 |
| 四域 | 同两配置，配对，3轮 | 1 节点×2h | 完整结果、退出码及正确性通过 |
| 整节点 | 同两配置，配对，3轮 | 1 节点×3h | 无缺域，波动≤5%；保留失败结果 |
| 独立对照 | B64/preferred，重点32电极；先找原证据 | 仅证据不足时 1 节点×2h | 不改变批量后宣称同配置加速 |

合计上限建议 7.5 节点小时，按阶段释放，不预先批量提交。单域／四域若用独占整节点也按整节点预算，不按核心占比假装免费。正式作业时限按协调排期填入调度器，发生错误、无效输入、库错配、节点页数不足或到达预算即停止扩大；失败等待上限和子进程清理由 S01 先修复。第二主机及所有长训练另外排期。
