# S01 R7：36核模型运行器修订候选

日期：2026-11-05（Asia/Shanghai）；候选目录创建于2026-11-04 UTC。

状态：**READY_FOR_REVIEW / LOCAL_ONLY_NEW_RUNNER / C2_MODEL_NOT_RUN**。
版本：`S01_CPU36_MODEL_R7_20261104`；线程合同：`CPU36_MODEL_V1`。

## 1. 结论

已按实测C组固定OMP36/MKL36/OpenBLAS1/cores/close；将“调用线程掩码等于全集”修正为“初始化前授权与selected36、所有已记录TID非空子集、实际PyTorch intra-op=36”的组合合同。新合同接入真实模型checkpoint、原子发布、父进程监督和汇总路径；没有删除越界、缺证据或线程错误拒绝检查。

本地48项回归：47通过、1项Linux进程组清理跳过。模型计算AST与冻结S00源码一致；新三份shell/env本机Git Bash语法通过、LF检查通过，真正Linux语法与原生线程采集/清理尚待S00在新job验证。本轮没有SSH、作业提交、模型前后向、S02或训练内存执行，没有新性能结论。建议审核本候选；尚未集成或部署。

## 2. 前置条件与执行范围

先读取STATUS、CPU36_POLICY、CPU36_DIAGNOSTIC_RESULT_REVIEW及S00诊断报告/就绪记录，复核保存的原始回传。复核指令：`E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\COORDINATION\CPU36_DIAGNOSTIC_RESULT_REVIEW.md`，SHA256 `49ccf5e82741f67fd821a14b269ad7d0f5e488f63bb6f2fae065bb1f65108a14`。

独立核对job2026725/cn21338完整ZIP SHA256 `af5b01f9a7890d0bcaeb8c989e30a12ad64f65a6c40c5e7663d8d2f05d5b22b1`；54文件与received一致，2737采样行和30阶段快照的非空掩码均在0–35内，预留36/37。内层COLLECTION的39项SHA/bytes及原始mtime_ns字段有效；没有修改received文件时间。

| 五组历史诊断 | 末阶段Torch intra-op | inter-op元数据 | 调用线程掩码 | 用途 |
|---|---:|---:|---|---|
| A MKL1 | 1 | 608 | [0] | 负对照，不能采用 |
| B MKL unset | 36 | 608 | [0] | 可说明MKL影响，本候选不用隐式unset |
| C MKL36/close | 36 | 608 | [0] | 采用的明确环境 |
| D MKL36/false | 36 | 608 | 0–35 | 证明单主线程掩码不能作为36线程判据 |
| E OpenBLAS36/close | 36 | 608 | [0] | NumPy库API仍为1，无新增收益证据 |

这些是已保存的小算子诊断，不是本轮模型结果。MKL1是该二进制/环境中Torch1的原因之一；不推广为所有运行时唯一根因。608不等于实际608工作线程，omp_max也不是独立接受依据。

修订全部位于 `E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S01\revisions\R7_CPU36_RUNNER_20261104T151540967239Z`。`candidate/runner.py`、`s4_models.py`、`run_node16.sh`修改；新增`cpu36_contract.py`，模型仅增加计时外观测；kml_ops与legacy_inputs逐字节保留。`minimal.diff`以原S01 R2为基线，只含上述必要变化，`git -c core.whitespace=cr-at-eol apply --check`通过；两份interfaces为新的独立交接包装文件。

原S01 REPORT、R2、R6与历史失败证据不改写。原S01索引1607项重新核对全部匹配，原REPORT SHA仍为`e0a840aa4552fc52f5d6748591c6d3b8c5b4d1d651540a178ca29b1059fb8420`。本窗口仅写S01新目录；阶段二/三、S00/S02和冻结输入未改；未声称核验整个真实corpus。

## 3. 环境、复现方式与成本

本地Windows/Python3.11.9，测试约4秒，测试子进程只运行stdlib协议；使用mock替代原生procfs与框架接口的案例明确为合成。Python以3.9语法规则静态解析通过，Git Bash仅`-n`，Windows执行正式入口按预期exit1。节点小时0，本轮新增作业0；真实torch/numpy/KML模型未运行。

本地复现：

```powershell
python -B "E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S01\revisions\R7_CPU36_RUNNER_20261104T151540967239Z\tests\test_cpu36_pipeline.py" CPU36Pipeline
```

S00执行前须审核ZIP及SOURCE_MANIFEST中9项payload SHA、实际远端LF、Linux bash -n、实际解释器/库、38核域授权、选前36留末2与24GiB/900秒调度上限。包装器只准备了NDOM1/HBM0/B32/16电极pre+dec/三轮REPS1，内存membind，GN和sampling关闭。没有本轮远端目录或job。

包装器先在同job导入框架/模型定义而不执行forward/backward，形成实际模块/库SHA、全部TID和Torch线程引用；正式入口校验同job/host/CPU/source/input/env再启动。每轮仍校验冻结文件及退出状态。实际库API和采集证据必须来自新模型PID，不能把旧诊断引用当作模型证据。

## 4. 正确性

| 检查 | 接受规则 | 结果与证据 |
|---|---|---|
| 模型计算AST | 去除新增观测/原发布与barrier后与冻结源一致 | PASS，tests_after.txt中的AST回归 |
| 单核TID正例 | 每个TID非空且均在selected36、Torch36 | PASS，真实发布到汇总路径的合成证据 |
| 越界/预留/缺证据/错误线程 | 任意项错误即拒绝 | PASS，checkpoint与父监测负例；Torch1/None、MKL1、缺checkpoint/monitor均拒绝 |
| 身份和完整性 | 同PID/context/job/host、顺序/时间窗、模块及库SHA | PASS，含实际预检生产者schema到汇总回归 |
| 原失败保护 | 缺域/旧JSON/损坏或重复键/非零退出/超时/部分结果均FAIL | PASS，继承回归；UNSTABLE非零规则保留 |
| Linux进程组清理 | TERM/KILL仅本任务且有界 | 本轮Windows跳过，未声称原生验收 |
| 输出/loss、梯度、optimizer、state_dict | 科学数值等价 | NOT_RUN，本任务不改变也不验收模型数值 |

详见 `E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S01\revisions\R7_CPU36_RUNNER_20261104T151540967239Z\evidence\tests_after.txt`。初始缺新合同模块的失败日志保留在tests_before.txt；最终结果覆盖所有当前修改。

## 5. 性能与内存

| 配置 | 新模型有效结果数 | 步秒/吞吐 | DDR/HBM峰值 | 退出 |
|---|---:|---|---|---|
| R7候选36核 | 0 | NOT_RUN | NOT_RUN | 未提交 |

没有同主机配对、加速比、内存收益或同步训练结论。父监督器约50ms采样、模型计时外checkpoint和库SHA核验增加观测成本，单步计时之外仍影响整链壁钟。后续配对须统一观测配置。legacy输入已知16电极目标错配依旧存在，固定LEGACY_TIMING_ONLY；不作效果训练证据。

## 6. 接受条件与限制

已完成：明确C组环境、36核选择/2核预留、实际Torch36、全部TID采样及阶段证据、错误拒绝、真实发布/汇总接入、回归、静态语法/LF/hash与最小diff检查。总TID数或mask并集均不单独作为通过判据。

采样无法证明线程全部生命周期每个瞬间或精确in-region team成员。采样中活进程消失TID/读失败作为缺证据拒绝，可能保守失败，不能因此直接删检查。跨域、多域扩展、真实Linux动态库API/原生采集、模型整链和清理仍未验证。读不到cgroup不能宣称已验证24GiB硬限。

本轮请总协调审核候选身份与合同。审核后由S00用新job执行一次原限额小试，不能复用旧38/4核包或历史结果；当前不重跑。S02同PID守卫改为导入前36核授权与导入后全TID子集+实际Torch36，数值阈值/输入/模型不改；S00/S02包装器实际整合需另核新清单。本交付不解锁S02执行或训练内存。回退保留R2/R6原目录，不覆盖旧证据。

交接接口全文：`E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S01\revisions\R7_CPU36_RUNNER_20261104T151540967239Z\INTERFACE_FOR_S00_S02.md`，包括远端提交门槛、预检引用、全部回传字段和mtime处理要求。

## 7. 证据索引

交付根绝对路径：`E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S01\revisions\R7_CPU36_RUNNER_20261104T151540967239Z`。

| 文件（相对此根） | SHA256 |
|---|---|
| candidate/cpu36_contract.py | `3990bb6ba40e7d4e47037aef245c6bc971191e7ae2c4be8701dd329c408a179d` |
| candidate/kml_ops.py | `e6c5c4411c453c8168939cd51d737a7e9d8232bdfff05da3967805a5e917ff26` |
| candidate/legacy_inputs.json | `24df1ad655fa3263efaf1ec8a721074fdfbae15fcb1d054b30d88bf5b9734835` |
| candidate/run_node16.sh | `8910b84fd8cd0b1c7df64d6c61ea0a0027291aac92e9c327eb197d3c8d20752d` |
| candidate/runner.py | `e04a703b7da429e3d85607f66b2c4d18cb3306b9a6320f92d7fd3be41539674a` |
| candidate/s4_models.py | `ebc31ca6f726df886e147da7ff4766b32142a6b83c7336f15e6c1a52e25e1461` |
| INTERFACE_FOR_S00_S02.md | `d2172e0a92307e92fe6a69a09bcc6daf1d7ba44cea7a074fc55a7219f4448f46` |
| interfaces/cluster_runtime.env | `32248af7857b7fd1616b19899c1411a4a59f9378c9231f0ec56f6c922ec2866d` |
| interfaces/run_s01_startup36.sh | `eae64b092b9a62525a6362f6ea93a96019266a79bb2070e36fb107eb8d91fde1` |
| SOURCE_MANIFEST.json | `45ce97a9159a8e071e0dac83a44590505bcf5e229389658600c181f40ec648b7` |
| SOURCE_SHA256.txt | `278d5cf1f7424e0e35a0c76120a121ce2a77a4286d2e651b874bdd8529d95b03` |
| minimal.diff | `cbb26cb29d08c2d0164fe1109b647932d6ca9a89733eefa7e0542912578aa8a2` |
| S01_CPU36_MODEL_R7.zip | `288a74181c36ec87b3953be5cde7e26575e45c219e9f446a21fca0683659119c` |

ZIP 30493字节、11成员，全部payload SHA与源一致且CRC通过；不含NPZ、共享库或完整依赖。测试和证据留在本修订目录，不伪装成可脱离冻结基线运行的远端模型包。

证据绝对路径：

- `E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S01\revisions\R7_CPU36_RUNNER_20261104T151540967239Z\evidence\baseline_audit.json`：54文件/2737采样/30阶段及原版本哈希。
- `E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S01\revisions\R7_CPU36_RUNNER_20261104T151540967239Z\evidence\diagnostic_collection_verification.json`：39项原始collection核对。
- `E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S01\revisions\R7_CPU36_RUNNER_20261104T151540967239Z\evidence\tests_after.txt`：48测试47通过1跳过。
- `E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S01\revisions\R7_CPU36_RUNNER_20261104T151540967239Z\evidence\local_checks.json`：语法、LF、Windows拒绝、diff、1607旧项哈希。
- `E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S01\revisions\R7_CPU36_RUNNER_20261104T151540967239Z\evidence\bash_syntax.json`：3份Git Bash -n，scope明确。
- `E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S01\revisions\R7_CPU36_RUNNER_20261104T151540967239Z\evidence\package_verification.json`：ZIP身份及逐项一致性。
- `E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S01\revisions\R7_CPU36_RUNNER_20261104T151540967239Z\ARTIFACT_SHA256.txt`：本R7全部交付/测试/证据逐文件索引（排除自身），REPORT也在其中。
