# S02 R5：CPU36 严格数值对照包装交付

日期：2026-11-05，Asia/Shanghai。

状态：**LOCAL_WRAPPER_READY_FOR_COORDINATION_REVIEW / C2_KML_NOT_RUN / ORIGINAL_WINDOWS_STRICT_FAIL / MEMORY_NOT_RUN**。

## 1. 结论与交付

已从 R3 完整成果恢复，完成36核最小包装修改、同 PID 框架前授权捕获/选核/绑定和框架后全可见 TID 守卫、14项本地正负策略检查、源码与旧证据不变性核验、新代码包、SHA/大小/来源清单、最小 diff，以及 S00 一次性提交与回传命令。

本地包装准备没有尚存的实质代码阻塞，可交总协调核验后由 S00 排期执行一组 C2/KML 严格数值对照。R7/job2034247 的启动门槛已关闭，不等待或重跑；本窗口未上传、SSH 或提交作业。C2数值结果尚不存在，不能写成通过；Windows194项失败及原阈值保留，训练内存/HBM未解锁。

绝对交付根：`E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S02\round5_cpu36_20261105T032617Z`。

| 交付物 | 本根下位置 |
|---|---|
| 本报告 | REPORT.md |
| 可交 S00 的新代码包 | package/S02_CPU36_R5_CODE.zip |
| ZIP及20文件逐项SHA、大小、绝对来源 | package/PACKAGE_MANIFEST.json |
| 标准 ZIP 校验文件 | package/S02_CPU36_R5_CODE.zip.sha256 |
| 19项源文件 SHA | SOURCE_SHA256.json |
| 完整 Linux/S00 命令、资源与退出判读 | C2_HANDOFF.md |
| 三个既有执行文件的最小 diff | diff/R3_WRAPPER_ONLY.patch |
| 新增/省略文件说明 | diff/ADDED_FILES.md |
| 全交付文件哈希索引 | ARTIFACT_SHA256.txt |

ZIP：**50873字节 / 20文件**，SHA256 **64605deb9a08de087a42f9026272a18bfed1d1896acdd449852ed2837aa43003**。CRC、成员唯一性、ZIP与磁盘源逐项SHA一致。包不含 venv、完整历史结果或259MiB case。

固定 case 沿用原绝对路径：`E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S02\round3_20261104T134939Z\case\fixed_16_pre.pt`；**271979513字节**，SHA256 **4de1fb40eb1c4b43a8747586399f336bf9e37184592d66fdbf711abad8469846**。已重读原文件核验，不复制、不重新导出或重新生成权重/输入。远端可引用同一已核验原文件。

## 2. 恢复、可见任务与写入隔离

完整阅读 S02_RESTART_HANDOFF_20261105、STATUS、R7_PASS_NEXT_S02、CPU36_POLICY、S01 的 R7_STARTUP_AUDIT 报告、R3 REPORT/C2_HANDOFF，以及 R7 CPU 合同及接口；确认 NO_S01_BLOCKER_FOR_S02。

R3 ZIP SHA仍为37357ae80c9278a5fc6d9f080ae94b7259610a19693cfbc9913141a4d8997918，17个文件和磁盘源逐项一致；另2个ZIP条目仅为空目录 case/ 与 evidence/。旧 round4 只有 coordination_notice.json，未发现完成的新36核包。没有向旧目录补文件。

CIM进程查询返回“无法从客户端中访问 CIM 资源”；两次 Get-Process 可见列表未显示 python/bash/wsl/ssh/codex。**不能据此证明旧窗口/远端任务已停止**。本窗口因此只做新目录中的标准库检查与包装，不启动完整模型计算；没有查询或取消不明远端作业，S00 在自己的实际队列中做最终去重。

开始记录78个既有文件的SHA、bytes及mtime_ns；终检77个保持完全不变，包括全部被记录的 R3 源/证据/case、旧 round4、R7合同及其它交接文件。唯一变化是总协调在11:29更新了自己维护的 STATUS.md，内容为本R5正在写入、门槛/任务不变；已完整重读并单独保留其前后身份，未把共享文件变化说成本窗口修改。见 evidence/inputs_before.json、inputs_integrity.json、recovery.json。

所有新增写入限定本 R5。未修改 R3、旧 round4、S00/S01、协调文件、原始项目或正式 manifest。本地复用 `round2_20261104T114949Z/.venv/Scripts/python.exe`，没有安装环境或重跑已完成的九项 Windows 模型实验。

## 3. 最小实现与保持不变的计算

三个既有执行文件的改变仅为：延迟 Torch/NumPy/候选模块导入直至同 PID 绑定后；移除 torch.set_num_threads(4)；采用实际 Torch36检查；将主线程必须等于四核全集改为全部可见TID非空且属于selected36；新增有序CPU checkpoint及case身份核对；将shell改成C组36核与单一strict入口。

新增 cpu36_guard 直接调用原样 R7 CPU36_MODEL_V1 合同。先捕获实际授权和现场38物理核域拓扑，38核申请留末2核、选择前36；36核申请只接受正确前36集合，跨域/37核/预留核重叠拒绝。包装授权receipt与checker同PID的job/host/拓扑必须相同；同PID在框架导入前显式绑定selected36并读回确认。numactl保持原授权直到该捕获点，并绑定同一内存域；任何模型计算均在收窄之后。

环境为 OMP36/MKL36/OpenBLAS1/cores/close。不用set_num_threads把错误实际值改成36；Torch1明确拒绝。框架后每次记录真实intra/interop、parallel_info、模块路径、库SHA及OpenMP线程API。允许合法单核calling TID，但所有可见TID必须留在selected36，缺失/不完整/空/重复/越界证据拒绝。7个checkpoint包含参考和候选两侧执行边界，结果内保留全部证据及错误。

原KML实际加载/映射检查、direct GEMM计数/形状和结束库身份重验保留；无KML/shim/OpenMP或无实际调用即错误，不静默fallback。Windows显式KML请求在导入Torch前以退出2拒绝。

10个关键文件逐字节保持R3：baseline模型/KML、candidate训练/loader、原比较器/fixture、projection_trace、VALIDATION_PLAN、INPUT_PAIRING_PROTOCOL、CASE_MANIFEST。run、compare_snapshots、optimizer_details、case_identity、errors、first_update、tensor_sha七个计算/比较函数AST保持不变；这是静态不变性证据，**不是数值验证**。

第一组严格限定16_adjacent/pre、backend=kml、mode=strict、B64对micro32×2、fp32/CKPT0/fresh。AdamW仍为lr1e-4、betas(0.9,0.999)、eps1e-8、weight_decay0.01；原loss分母、一个effective batch一次step及随机张量保持。原tensor max_abs≤2e-5且L2 relative≤2e-6、moments绝对/相对≤2e-6，norm≤1e-8只判绝对差及精确step/keys/shape/dtype等检查均未改动。不删K bias、不归零梯度、不改阈值求PASS。

## 4. 本地验证和证据边界

| 检查 | 结果与原件 |
|---|---|
| 先写守卫测试 | guard_tests_before.txt保留新增模块尚不存在时的失败 |
| CPU36策略正负测试 | **14/14通过**，evidence/guard_tests_after.txt |
| 框架前导入与绑定顺序 | 测试确认checker模块导入不加载Torch/NumPy；mock验证实际绑定调用与receipt拒绝 |
| 错平台拒绝 | 退出2 / ERROR_RUNTIME_OR_INPUT，evidence/wrong_platform.json及stdout |
| Python3.9语法 | 通过；只做AST语法，不称为Linux ABI或真实运行 |
| 三项shell/env LF与Git Bash bash -n | 全部通过，evidence/local_validation.json |
| S00说明中的命令 | 提取后Git Bash bash -n通过，嵌入Python3.9语法通过；未执行命令，evidence/commands_validation.json |
| 冻结计算源与历史证据 | local_validation.json、inputs_integrity.json |
| 包CRC/SHA/大小/来源 | evidence/package_validation.json、PACKAGE_MANIFEST.json |

14项测试覆盖合法单核调用线程、实际Torch1、预留/未授权核、错误selected数量、空/重复/缺失/不完整TID、缺失caller/OMP证据、错误环境、first36合法分配、错误分配大小/预留重叠、跨域授权、缺GEMM、库漂移、延迟框架导入、绑定顺序、缺失/旧job收据。系统接口与Torch元数据的替身仅验证拒绝策略；没有伪装为实际C2/NUMA/KML验证。

本地Git Bash最初受Windows对象权限限制无法启动，获准的本地语法检查已成功完成；没有执行shell中的模型/提交动作。集群Linux bash -n、现场实际CPU/库/ABI与完整参考/候选计算由S00保存新job证据。7个checkpoint不等于连续线程生命周期证明，也不证明精确OpenMP team；没有增加常驻采样线程或把R7旧采样冒充本次结果。

## 5. S00执行、实质未决项与停止条件

完整命令在 C2_HANDOFF.md，使用新账号自有目录、新包SHA和一次性标记；单job首选cpu38、实际selected36/reserved2，mem24576MB且-RL同值，-T900，HBM0。run_s00_job.sh source冻结R7 runtime后只运行一次strict；内部timeout780秒/kill-after15秒。实际资源/终态由S00收据确认，不能由节点总资源推断。

退出0仅为固定合成case的PASS_STRICT_SYNTHETIC_ONLY；退出1且FAIL_ORIGINAL_CRITERIA为数值失败；退出2为运行前提错误；124/137等保留超时/信号状态。原阈值FAIL完整保留全部metrics和日志，不扩矩阵、不重跑九项Windows模型实验。回传需要实际job资源/命令/终态、源码/case身份、真实KML调用/库SHA、7个CPU checkpoint、全metrics/failures及退出的一致证据。

**本地交付无实质阻塞。仍缺的是总协调的新包核验及S00这一组实际C2/KML数值结果；S02本窗口按分工不代提交。** Windows严格194项失败未改变，C2结论未运行，M2数值门槛仍未通过。训练内存/HBM测试、收益接受、32电极、decoder数值扩展、多域/整节点、长训练均未开展。新增集群job/节点小时/GPU小时均为0，没有本轮吞吐或内存收益结论。
