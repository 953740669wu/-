# S00：S01 / S02 有限集群小试准备

最新（2026-11-05）：总协调已接受R7本地候选作有限启动；本轮job2034247按38核分配/实际36/预留2核、24GiB、900秒完成单域16-pre/dec、B32、HBM0三轮REPS1，child全部0，远端与真实mtime副本离线汇总均PASS。完整线程/库/退出54文件已回传，等待S01及总协调审核；不自动解锁S02/训练内存、正式性能或生产部署。新入口CPU36_R7_STARTUP_REPORT.md。下方旧38/4核/R6/等待记录保留历史时点；旧包仍历史禁用，本轮无后续作业。

最新有限诊断回传：R6小算子job2026725在cn21338成功收齐五组，分配38/实际36/预留2核，24GiB、300秒，实际70秒。完整54文件及原始mtime_ns见CPU36_R6_DIAGNOSTIC_REPORT.md。等待S01分析和总协调审核；旧模型包继续历史禁用，不恢复完整模型、S02或训练内存。下方停止/未提交描述保留各轮时点，最新执行状态以本段及新报告为准。

最新执行约定（2026-11-04）：后续S01/S02模型及算子每域实际36个物理核心，在38核域留末2核；24GiB/15分钟及数值阈值不变。当前旧38核/4核包仅作历史证据，禁止后续执行；按CPU36_POLICY先等S01接受的诊断/修订，再统一换36核包。当前停止、无新作业，详见CPU36_READINESS.md及execution_packages/NEXT_CPU36_EXECUTION.json。下方38/4核记录与命令保留历史身份，不是当前执行入口。

日期：2026-11-04。状态：**S01_ATTEMPT_FAILED_STOPPED / S02_BINDING_FIXED / S02_MODEL_NOT_RUN**。S01 job2026356已按38核/24GiB/900秒实际提交，因S00包装器CRLF在模型前失败，按指令停止、不重提；S02未提交。原失败包与LF修正版分开保存，详见PILOT_EXECUTION_REPORT.md。下列命令是修正后的后续恢复入口，本轮不再执行，不构成新性能基线。

最新执行状态：用户随后明确授权一次LF恢复，job2026450/cn21340按38核/24GiB/900秒完成首轮完整模型，因CPU affinity合同FAIL而停止；child0/job1，无第2/3轮。本轮用户明确暂不提交S02及内存测试。S01_LF_RESTART_REPORT.md及其完整证据包为最新审核入口，旧2026356证据保留。下方仍是方案说明，不是继续提交授权。

## 1. 已完成与执行顺序

1. S01 R4已在Linux完成进程清理和合成协议验证，不重复这些矩阵。本轮job 2026223又在cn21417完成真实torch/numpy导入、输入身份及库加载预检，详见COMPUTE_ENVIRONMENT_REPORT.md和evidence/compute_environment_verified.json。
2. 下一个有限小试先执行S01单域完整启动链：原样候选、16_adjacent/pre+dec、B32、fp32、CKPT0、HBM0。只验证真实进程、输入、前反向/更新、退出及结果协议。三轮REPS1仍是启动小试，不代替正式性能计时长度、稳定性或第二主机验收。
3. S01小试结果复核通过后，执行S02一组完整模型严格等价检查：16_adjacent/pre、有效B64、microbatch32×2、fresh、CKPT0、fp32、实际KML。固定原输入/权重/随机量和原阈值，不自动扩到dec、32电极、CKPT或seeded。
4. **S02训练内存阶段NOT_READY**：Windows完整模型检查已失败，而且尚无已接受的独立训练内存入口。只有严格数值通过并补齐该入口，才准备同主机配对内存小试。不能把equivalence脚本保留参考快照的峰值当训练峰值。

S02 Windows失败记录：loss绝对差3.05176e-5 > 2e-5，诊断194项失败（49梯度、13更新后参数、33增量、98 moments及loss）。C2使用NumPy1.26.4/KML，Windows使用NumPy2.2.6/原生后端，必须作为独立环境记录；C2结果不能覆盖Windows失败。诊断脚本diagnose_same_config.py固定kml=False，不用于KML失败诊断。Windows run_16_representative.py含ctypes.windll，不在Linux使用。

## 2. 连接、环境和独立目录

入口：VPN已连接后的dengqingtian@10.44.9.4:22，交互密码认证，落点login10。文档/包中没有密码。只读共享项目/home/share/songzhenlong/eitfm。S01既有独立目录：

```text
/home/share/dengqingtian/opt/stage4_sessions/S01/R4_LINUX_20261104T123653399272Z/
```

不覆盖该目录。本轮及后续S00代执行都在当前账号S00/PILOT_S01_*/payload或S00/PILOT_S02_*/payload内落包；不写S01/S02任务目录。

可复用Python：

```text
/home/share/dengqingtian/opt/stage4_sessions/S00/ENV_20261104T130730Z_R4/venv/bin/python3
```

Python3.9.9、torch2.7.1+cpu、numpy1.26.4。execution_packages/cluster_runtime.env固定解释器/venv PATH、共享torch、KML/OMP路径与shim。S01会重设PYTHONPATH，venv是已实测的NumPy可见性方案；不能只在外层增加NumPy PYTHONPATH。共享torch/KML仍是外部只读依赖，运行前复核实际路径及SHA。S02使用S02_PAIRED_BELT_V1合成输入，不依赖legacy NPZ，也不声称真实语料/划分已验收。

本机准备包绝对目录：E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S00\execution_packages。S01_pilot_prepared.zip保留8份已接受源码及原样Linux预检；S02_pilot_prepared.zip保留原严格检查/候选/fixture共10份来源文件。源码SHA、包SHA见PACKAGE_MANIFEST.json，每包另有PILOT_MANIFEST_S00.json。新增包装器只完成环境、授权CPU/单NUMA检查、超时及固定小试参数，没有修改模型/候选/阈值。

## 3. 修正版后续上传与准备（本轮不重试）

后续恢复时先校验包SHA与PACKAGE_MANIFEST.json一致，再上传到S00全新目录。S01/S02包装器只接受对应S00/PILOT前缀，模型/候选来源不变。示例S01；S02使用PILOT_S02_前缀及S02包：

```powershell
$runId = 'PILOT_S01_' + (Get-Date -Format 'yyyyMMddTHHmmss')
$remoteRoot = '/home/share/dengqingtian/opt/stage4_sessions/S00/' + $runId
ssh -o PubkeyAuthentication=no -o StrictHostKeyChecking=yes -o UserKnownHostsFile=E:/eitfm_c2_stages2-4_2026-11-03/c2/stage4_sessions/work/S00/evidence/known_hosts_10.44.9.4 dengqingtian@10.44.9.4 "mkdir '$remoteRoot'"
scp -o PubkeyAuthentication=no -o StrictHostKeyChecking=yes -o UserKnownHostsFile=E:/eitfm_c2_stages2-4_2026-11-03/c2/stage4_sessions/work/S00/evidence/known_hosts_10.44.9.4 'E:/eitfm_c2_stages2-4_2026-11-03/c2/stage4_sessions/work/S00/execution_packages/S01_pilot_prepared.zip' "dengqingtian@10.44.9.4:$remoteRoot/"
```

以下在Linux登录节点仅解包、哈希和复制既有小输入，不执行模型。R必须替换为上一步实际唯一目录；mkdir失败就停止，禁止复用旧run目录。不要在共享项目解包。

```bash
set -euo pipefail
R=/home/share/dengqingtian/opt/stage4_sessions/S00/PILOT_S01_<实际runId>
P="$R/payload"
mkdir "$P"
E=/home/share/dengqingtian/opt/stage4_sessions/S00/ENV_20261104T130730Z_R4
sha256sum "$R/S01_pilot_prepared.zip"
/usr/bin/python3 -B -m zipfile -e "$R/S01_pilot_prepared.zip" "$P"
/usr/bin/python3 -B - "$P" <<'PY'
import hashlib, json, sys
from pathlib import Path
root = Path(sys.argv[1])
for name, expected in json.loads((root / 'PILOT_MANIFEST_S00.json').read_text()).items():
    assert hashlib.sha256((root / name).read_bytes()).hexdigest() == expected, name
PY
mkdir "$P/lib" "$P/output"
cp "$E/S01_payload/lib/libkml_sgemm_shim.so" "$P/lib/"
cp -r "$E/S01_payload/output/cases" "$P/output/"
```

输入在远端就地复制，不下载原始NPZ。两份输入SHA和shim SHA会再次由S01原样runtime_preflight检查；只复制cases，不复制旧reports或预检结果。S02在S00/PILOT_S02_*/payload解包，无需lib/output/cases复制，校验后使用其合成fixture。所有sh/env必须字节检查无CR且在真正Linux bash -n成功；不以Git Bash的宽容解析代替。包内shell均用bash显式执行，无需修改源码或执行权限。

## 4. 有限资源和提交命令（排期后使用）

资源请求是**单作业上限建议**，没有从已结束的环境job继承allocation。S01用一个完整38核NUMA域匹配现有线程配置；S02先只用4核做正确性而非性能。两者各用24GiB DDR作保护上限，不能据此宣称真实峰值；若单域可用内存不足，停止等待资源，不能改为跨域后沿用同一配置名称。S01既有32GiB建议尚未分配，本方案缩为24GiB以便设置有限上界，成功与否仍取决于实际模型峰值。不得因超限自动扩大额度。

| 顺序 | 节点/CPU/内存 | wall上限 | 输入/计算 | 状态 |
|---|---|---|---|---|
| S01启动 | 1独占节点；单NUMA域38 CPU；24576MB DDR | 900秒；包装器780+15秒；每轮180秒 | legacy 4帧仅历史计时兼容；16-pre/dec B32，3轮REPS1，HBM0/CKPT0 | job2026356在包装器阶段FAIL，已停止；修正版未重试 |
| S02等价 | 1独占节点；单NUMA域4 CPU；24576MB DDR | 900秒；包装器780+15秒 | 同初权重/固定随机量，有效B64对B32×2，一步AdamW，KML | 精确4核包装器已修正；等待S01完整启动通过 |
| S02训练内存 | 1独占节点；单NUMA域4 CPU；24576MB DDR | 建议600秒 | 严格数值通过后，独立参考/候选各进程配对，先DDR/CKPT0 | NOT_READY，无接受入口 |

前两项合计申请壁时上限0.5节点小时；条件内存项再加约0.167节点小时。不能按核数/608缩小独占节点成本。此前环境四个短作业34秒，加本次包装器失败1秒，累计35秒≈0.00972节点小时；全部计入，不能遗漏失败。

下列命令仅供后续恢复；本轮失败后不再提交。提交前source调度器profile，R取对应全新S00/PILOT目录，P取R/payload。以下Donau参数经现机help核查；最终以djob回执确认CPU、内存、exclusive、节点和时限，资源与请求不一致就取消。-R是资源申请，-RL是显式内存限制请求；不能在cgroup不可读时声称已独立验证内核硬限。若回执/平台不能确认限制生效，先由资源维护方明确限制或提供任务内存保护，不直接启动模型。

```bash
set -euo pipefail
source /etc/profile.d/donaukit_scheduler.sh
P="$R/payload"
# 先S01：R为已核验的新S00/PILOT_S01目录；语法失败必须阻止提交
if ! bash -n "$P/pilot_s01_startup.sh"; then exit 2; fi
 dsub -J -q q_hpcai -R 'cpu=38,mem=24576MB' -RL 'mem=24576MB' \
  -a 'numa[count=1,distribution=pack]' -T 900 --env none --cwd "$P" \
  -oo "$R/job.log" env S01_RUN="$P" bash "$P/pilot_s01_startup.sh"
# 取得该job JSON中的实际ID，记录并查询，不复用下面的占位符
 djob -J -l <S01_JOB_ID>
# S01完整模型小试结果复核通过以后：R改为已核验的新S00/PILOT_S02目录
P="$R/payload"
if ! bash -n "$P/pilot_s02_equivalence.sh"; then exit 2; fi
 dsub -J -q q_hpcai -R 'cpu=4,mem=24576MB' -RL 'mem=24576MB' \
  -a 'numa[count=1,distribution=pack]' -T 900 --env none --cwd "$P" \
  -oo "$R/job.log" env S02_RUN="$P" bash "$P/pilot_s02_equivalence.sh"
 djob -J -l <S02_JOB_ID>
```

调度器会注入CCS_JOB_ID（本轮已实测），包装器拒绝登录节点和错误CPU/NUMA。外层--env none避免隐式继承私人环境。未来每次在实际模型进程记录/proc/self/status、sched_getaffinity、numactl --show、绑定域meminfo/hugepage、解释器/依赖/输入/源码/库SHA和djob分配。S02显式--physcpubind绑定获分配的4核，OMP_PROC_BIND=false；run_s02_checker_bound.py在运行原checker的同一PID内于导入前、torch设线程后和退出时核对CPU集合并记录线程集合。当前Linux微小fixture正负控通过，但实际完整checker未运行。1CPU环境探针不能替代38/4CPU放置验收。HBM尚未在本轮使用，后续须另证hugetlb可用量与DDR/HBM分列方法。

## 5. 停止条件与结果口径

- 排队超过600秒则取消该次确切job，不无限占位/自动重试；遇到共享文件SHA变化、依赖导入失败、非计算节点、授权CPU数量或NUMA域不符、库映射异常，立即停止，保留回执/日志。
- S01包装器780秒TERM、15秒后KILL，调度器900秒；单轮180秒、barrier120秒。非零退出、SIGBUS/OOM、缺域/缺JSON、过期结果、配置不一致或UNSTABLE即失败，不自动补轮、挑最好结果或扩大域数。由于REPS1与legacy输入，仅能判断启动链与协议，不能接受科学等价或新性能基线。
- S02保持原阈值：输出/loss/梯度/更新参数/增量max_abs≤2e-5且L2 relative≤2e-6；参考norm≤1e-8只判绝对；AdamW moments绝对/相对≤2e-6；keys/shape/dtype/step/应有梯度/finite均严格检查。任一失败就停止，不增加配置、不改eps/LR/阈值、不测内存收益。KML失败诊断应由S02提供匹配后端的入口。
- 内存达到调度限制或被保护终止，报告RESOURCE_GUARD_STOP或调度器实际原因；只有系统证据明确OOM才写OOM。若后续增加20GiB预警阈值，必须先有可核验的监视器；当前包装器没有该软阈值，不能虚称已实现。节点可用445GiB仅旧整机观测，不能当作24GiB作业预算。
- 对本轮确切job取消：`dkill -y <实际jobID>`，然后djob核验终态及本任务进程清理；不使用pkill、不取消他人/历史作业。保存FAIL/timeout的原日志，目录不重用。

S01预期每轮1域结果/退出状态齐全，三轮共3份域JSON及summary/manifest；按实际域ID命名，不预设d0。S02输出evidence/c2_<jobID>/equivalence.json，checker退出码和JSON结论一起判读。所有输出含实际host/job/路径/环境指纹；本机语法PASS不等于模型运行PASS。

## 6. S02内存测试待补入口

待S02提供Linux可执行的轻量训练入口与SHA：完整原架构、同有效B64及固定输入/权重/随机量，参考B64和候选B32×2独立新进程；实际前向、反向、AdamW，不能保留另一条路径的参考快照。固定预热/测量更新数，报告DDR RSS/PSS和ru_maxrss采集口径，HBM另测实际占用；同时给出训练阶段总耗时/误差，但不把检查器墙钟换算吞吐。

只有入口及参数经过S02验收、严格等价PASS、资源确认后才能形成完整命令。当前只能给出执行形态，**不可直接复制运行，不是已完成的内存验证包**：在上述600秒/24GiB调度作业内，用同一C2_PYTHON和numactl绑定，timeout --signal=TERM --kill-after=15s 480，先运行S02接受的参考入口，再在全新进程运行接受的候选入口，分别输出原始资源采样与训练结果。S00不替S02实现优化/测量驱动或编造未有的CLI。

当前实际S01尝试已失败并停止，修正版已通过Linux语法/轻量绑核fixture，不做模型重试。正式新性能基线仍等待S01运行器总体验收，按单域→四域→整节点及同主机A/B推进；输入来源和权威subject split等开放项见PENDING_ITEMS.md。
