# S01 R6：job2026450审核与CPU36线程诊断准备

日期：2026-11-04（Asia/Shanghai）。

状态：**READY_FOR_REVIEW / CPU36_DIAGNOSTIC_PREPARED / C2_DIAGNOSTIC_NOT_RUN / FULL_MODEL_RESTART_STOPPED**。

## 1. 结论

已独立核对S00的S01_LF_RESTART_REPORT及完整19文件：模型首轮确实完成，child exit0、未超时；原summary因调用线程affinity不等于0–37返回FAIL，job exit1，只完成1/3轮。接受失败证据，不接受38核启动/性能结论；不能继续描述为模型未到达。

两个信号分开处理：调用线程[0]不能代表全部工作线程；真实torch intra-op为1也不能被OMP环境38覆盖解释为正确。MKL_NUM_THREADS=1是高优先级隔离项，已有PyTorch版本源码支持其可覆盖OMP默认值，但没有C2单变量结果，不宣称唯一根因。

本轮按新CPU36_POLICY准备五组小型算子对照、全部TID采集和保留授权边界的合同原型。**11项本地正负合同检查通过**；新诊断只完成Python/LF/本地Bash静态检查和Windows拒绝守卫，尚未在Linux/C2执行，没有重跑完整模型或提交作业。

S00执行计划与S00/S01/S02同步单已写好。当前工具没有跨聊天发送能力，因此不能声称另两个聊天已收到通知；请用户/总协调转交本轮同步文件路径。

## 2. 前置条件与执行范围

已读最新STATUS、CPU36_POLICY、AFFINITY_REVIEW、S00重启报告及manifest/r1结果/状态/summary/commands/预检/collection，核对完整证据ZIP SHA `1403bb4c5ba5032eb16df5aab4b3acd7836b6edd692db4ccc2b5626df0cbe87d`和19个received副本逐字节一致。

原候选仍为S01_LOCAL_RUNNER_R2_20261104，5个接受文件逐项SHA一致。没有覆盖R2、根REPORT、R4/R5报告、S00/S02文件、共享源码/库/输入/manifest。所有写入仅在本轮独立目录：

`E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S01\revisions\R6_CPU36_DIAG_20261104T143214257047Z`

新增版本 `S01_CPU36_THREAD_DIAG_V1` 是诊断包/合同原型，不是接受的36核模型运行器。kml_ops.py原样复制自接受版；cluster_runtime.env是S00环境设置的冻结基线，每个worker再明确覆盖本case的OMP/MKL/OPENBLAS配置。详细来源SHA在baseline_audit和SOURCE_MANIFEST。

## 3. 环境、执行与资源

本窗口在Windows Python3.11.9完成准备，当前Python未执行torch；没有SSH或新job。S00已知C2解释器为其独立venv/Python3.9.9、torch2.7.1+cpu、numpy1.26.4，仍须新job复核来源和实际加载。

交S00的范围：新的单计算节点，授权单38核NUMA域，从现场拓扑取前36个物理核心并预留末2核；若只分配36，也必须满足同域及留核。申请预算保留24576MB，不超原900秒；建议诊断时限300秒、外层270+5秒、每case45秒。仅小算子，不运行模型/NPZ/optimizer/HBM，不自动重试。S00负责实际排期，本窗口新增节点小时0。

五个独立worker串行，均绑定同一选中36核：A为MKL1单线程负控，B只移除MKL，C只改MKL36，D相对C仅改OMP绑定false，E相对C仅改OPENBLAS36。固定OMP36/places=cores，不在诊断中调用torch.set_num_threads。A及串行NumPy阶段明确是诊断负控，不冒充正式36线程配置；旧38/4核历史数据不改写。

各阶段采集before_import、torch导入后、Torch算子后、NumPy后、KML首次/重复调用后；另约20ms采集全部TID掩码/CPU tick/状态，记录实际intra/inter-op和已加载OMP/BLAS/KML库API及SHA。不加载新的OpenMP库制造结论，不使用torch.mm替代实际KML。详细命令见DIAGNOSTIC_PLAN_FOR_S00.md。

## 4. 正确性与故障解释

| 检查 | 结果及边界 | 状态 |
|---|---|---|
| S00完整19文件/来源SHA | ZIP和received字节全一致；R2候选5文件未变 | 通过 |
| job2026450逐进程/停止 | child0、timeout=false；summary FAIL；job1；没有r2/r3 | 历史失败被确认 |
| 历史全TID与因果 | 没有全部TID；无MKL单变量结果 | 不推断唯一根因或实际仅用1核 |
| CPU36合同正负 | 11项通过：38→选36/留末2、36精确授权、跨域/不足/37核/SMT重复拒绝；单核TID合法；预留/越界/缺证据/torch1拒绝；总TID不硬限36 | 本地通过 |
| 实施前检查 | 测试先写，模块未创建时失败；实现后11项通过 | contract_before/after |
| 新Python/字节LF/本地Bash -n | Python compile及两个sh/env LF检查通过，Git Bash -n退出0 | 静态通过，不能代替Linux执行 |
| 平台守卫 | Windows上诊断driver非零拒绝，未创建算子worker | 本地通过，非Linux算子验证 |
| C2五组小算子/实际线程/库API | 仅准备交S00 | **未运行** |
| 新36核模型运行器、真实完整启动 | 未修改/部署R2，新模型包装未启用 | **未运行** |
| 输出/loss/梯度/optimizer/state_dict数值对照 | 本轮无EIT模型 | **未运行** |

事实与依据：[PyTorch v2.7.1源码](https://raw.githubusercontent.com/pytorch/pytorch/v2.7.1/aten/src/ATen/ParallelCommon.cpp)显示默认线程数先读OMP、再读MKL；该步骤不要求实际启用Intel MKL。因此不能因为C2为ARM/KML就忽略MKL变量，但实际二进制仍以小算子A/B为准。

[Linux affinity手册](https://man7.org/linux/man-pages/man2/sched_setaffinity.2.html)定义pid=0为调用线程；[OpenMP绑定规范](https://www.openmp.org/spec-html/5.1/openmpse61.html)允许绑定初始线程到首个place。这支持区分主线程与全部TID，不等于已经证明本次所有线程正确。

## 5. 性能、内存和采样限制

没有新性能或内存实测；旧job2026450首轮计时是失败配置诊断值，不与36核候选计算加速比。不同38/36/4核配置分别记账。没有四域、整节点、三有效性能轮、第二主机或DDP。

新探针仅分配小型Torch/NumPy/KML数组，重复约0.5秒以便采样，不输出吞吐。CPU tick推进、TID数、掩码并集与omp_max不是精确in-region team人数的单独证明；记录采样不足，不据此宣称36线程正式接受。DIAGNOSTIC_DATA_COMPLETE只表示5组数据收齐。

归档限制另已确认：原collection没有mtime_ns，本地解包mtime不在旧进程时间窗。直接对received调用R2会先报本地stale/future mtime，不能替代远端原affinity错误。本轮没有改任何原件时间，也不伪造mtime求PASS；新COLLECTION将记录稳定文件原始mtime_ns/bytes/SHA，未来模型回传同样需补齐。

## 6. 最小修复与停止点

最小修复分成两个独立方向，均待诊断复核：

1. 环境：正式worker OMP目标36，MKL不再静默保留1；以B/C决定unset或显式36，以C/E决定OPENBLAS的正式后端设置。继续保留已知OMP绑定，不用改日志或调用线程setter掩盖诊断。
2. 合同：保留框架导入前授权集合、现场38核域/物理拓扑、所选36与预留2核；所有TID非空掩码必须在选中36内，实际torch intra-op须36。不能要求每个已绑单核TID都等于36核全集，也不能只靠并集通过。缺证据/越界/线程数错仍拒绝。原型尚未接入R2，不直接删其检查放行。

MINIMAL_FIX_PLAN.md给出修订边界；S00收到接受诊断结论后统一更新S01/S02包装器、--physcpubind、同PID守卫、OMP与相关环境、manifest/SHA/提交说明，远端LF与真正bash -n门槛继续。S02原4核/--threads4不再是后续正式配置，但其旧失败和包身份保留。

当前停止完整模型。交S00先执行小诊断，回传后再评审是否形成新的36核runner与模型小试包；不扩大资源、不改模型/有效批量/损失/optimizer/阈值，不直接整合S02，不改分配器。原候选与历史记录无须回滚。

## 7. 证据和同步入口

| 产物 | 绝对路径 |
|---|---|
| 本报告 | `E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S01\revisions\R6_CPU36_DIAG_20261104T143214257047Z\REPORT.md` |
| 给S00的诊断方案 | `E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S01\revisions\R6_CPU36_DIAG_20261104T143214257047Z\DIAGNOSTIC_PLAN_FOR_S00.md` |
| 最小修复建议 | `E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S01\revisions\R6_CPU36_DIAG_20261104T143214257047Z\MINIMAL_FIX_PLAN.md` |
| S00/S01/S02同步单 | `E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S01\revisions\R6_CPU36_DIAG_20261104T143214257047Z\SYNC_TO_S00_S02.md` |
| 可传输诊断包 | `E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S01\revisions\R6_CPU36_DIAG_20261104T143214257047Z\S01_CPU36_thread_diagnostic.zip` |
| 授权/全部TID合同原型 | `E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S01\revisions\R6_CPU36_DIAG_20261104T143214257047Z\diagnostic\cpu36_contract.py` |
| 诊断入口/worker | `E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S01\revisions\R6_CPU36_DIAG_20261104T143214257047Z\diagnostic\run_thread_diagnostics.sh`；`E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S01\revisions\R6_CPU36_DIAG_20261104T143214257047Z\diagnostic\run_diagnostics.py`；`E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S01\revisions\R6_CPU36_DIAG_20261104T143214257047Z\diagnostic\thread_worker.py` |
| 包内固定源SHA | `E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S01\revisions\R6_CPU36_DIAG_20261104T143214257047Z\diagnostic\SOURCE_MANIFEST.json` |
| 11项本地检查 | `E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S01\revisions\R6_CPU36_DIAG_20261104T143214257047Z\tests\test_cpu36_contract.py`；`E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S01\revisions\R6_CPU36_DIAG_20261104T143214257047Z\evidence\contract_before.txt`；`E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S01\revisions\R6_CPU36_DIAG_20261104T143214257047Z\evidence\contract_after.txt` |
| 来源审查 | `E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S01\revisions\R6_CPU36_DIAG_20261104T143214257047Z\evidence\baseline_audit.json` |
| job独立复核/mtime区别 | `E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S01\revisions\R6_CPU36_DIAG_20261104T143214257047Z\evidence\independent_job_review.json` |
| 本地平台拒绝/Bash静态 | `E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S01\revisions\R6_CPU36_DIAG_20261104T143214257047Z\evidence\platform_guard.json`；`E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S01\revisions\R6_CPU36_DIAG_20261104T143214257047Z\evidence\bash_syntax.json` |
| 本轮全SHA | `E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S01\revisions\R6_CPU36_DIAG_20261104T143214257047Z\ARTIFACT_SHA256.txt` |

当前无C2诊断结果可索引，不创建模型PASS。跨聊天工具在本会话不可用，无法直接投递S00/S02；同步单可由用户/总协调原样转交。没有自动发送消息或修改其他任务目录。
