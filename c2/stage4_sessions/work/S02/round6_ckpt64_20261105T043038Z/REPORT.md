# S02 R6：完整B64 checkpoint替代候选与独立训练内存入口

日期：2026-11-05，Asia/Shanghai。状态：**PREPARED_LOCAL_ONLY / CKPT64_C2_NOT_RUN / TRAINING_MEMORY_NOT_RUN**。

本轮完成完整B64/CKPT0对完整B64/CKPT1的独立候选、必要checker适配、共享原mean训练步、独立轻量内存入口、25项必要本地检查、最小代码diff、代码包/SHA/来源及S00命令。未提交集群job，未运行完整Windows模型或旧九项实验，未实测训练内存/HBM；不能宣布新数值通过或内存收益。

## 交付与身份

本轮绝对根：`E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S02\round6_ckpt64_20261105T043038Z`。

| 产物 | 本轮根内路径 |
|---|---|
| 本报告 | REPORT.md |
| 新包 | package/S02_CKPT64_R6_CODE.zip |
| 包/逐源SHA、大小、来源 | package/PACKAGE_MANIFEST.json；SOURCE_SHA256.json |
| 标准包校验文件 | package/S02_CKPT64_R6_CODE.zip.sha256 |
| 最小代码/新增文件diff | diff/R5_TO_R6_CODE.patch |
| S00严格对照与条件内存命令 | C2_HANDOFF.md |
| 保存的R5失败分析 | evidence/R5_saved_failure_analysis.json |
| 本地检查 | evidence/checkpoint_tests_after.txt；cpu36_guard_tests.txt；memory_unit_tests.txt；static_validation.json；local_validation.json |
| 包核验及旧输入不变性 | evidence/package_validation.json；inputs_before.json；final_review.json |
| 全产物SHA | ARTIFACT_SHA256.txt |

代码ZIP **62584字节、28个文件**，SHA256 **26e542430f024f60277bdbbbc699b41a203ee74270022806074040a531ac166f**。不含venv、完整旧证据或case。

原case只读沿用 `E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S02\round3_20261104T134939Z\case\fixed_16_pre.pt`，**271979513字节**、SHA256 **4de1fb40eb1c4b43a8747586399f336bf9e37184592d66fdbf711abad8469846**。未复制或重新生成权重/输入；加载后继续核对初始权重及固定张量身份。完整B64与所有原case张量保持。

## 从最新磁盘成果继续

按HANDOFF_PROTOCOL读取自己的SESSION_STATUS/ROUND_DELTA、当前总任务表及POST_S00_S02_S03_NEXT的S02节；按需读取R5现行源码/包、S00原始result和S02_R5_C2_STRICT_REPORT。核对R5包/20个源文件的SHA和磁盘来源后复制到新R6目录，修改前记录身份与mtime。

Get-Process可见列表未显示匹配python/bash/wsl/ssh/codex任务；这不是对旧窗口或远端作业不存在的证明。本轮没有发起远端任务或完整模型计算，不会与已结束的2034953重算。没有修改R5或S00结果。原模型/KML、loader、旧training_step及checkpoint helper、比较器/fixture、case清单、CPU合同、runtime环境等13个关键文件逐字节保持；开始记录的25个受保护来源在检查时均保持SHA/bytes/mtime不变。自己的两份短交接文件按本轮要求更新，其旧内容单独保存于本轮evidence。

## R5已保存失败证据的增量分析

只解析job2034953的已有result，不重跑计算：1063项中95失败，grad9/param18/delta52/state16。9个梯度失败分为7项仅绝对超限、1项仅相对超限、1项两者超限。

- 大梯度也会触发原绝对门槛：mask_tok参考norm约45628.74，max_abs=0.001953125，相对约2.626e-7；仍按原绝对阈值失败。head_v.weight的max_abs约0.01022339、相对约1.1353e-5，两项均失败。不能因量级大或部分相对差小而放宽标准。
- packed bias更新差集中在K段：12层最大K段差约1.9515038e-4，Q/V最大分别约1.25874e-9/2.98314e-10。最坏第4层K坐标梯度约-4.02477e-7对+4.02331e-7，符号相反且约为eps的40倍；fresh AdamW更新接近±9.7575e-5。该原始坐标的float64首步公式与实际更新接近，支持归约残差对近零方向更新敏感的解释；未做新的逐算子因果定位，不能把它写成全部失败的完整证明。

loss/输出组通过不覆盖参数/状态失败；R5仍不接受。完整B64 checkpoint路径保留batch归约形状，避免同时引入拆批和sum损失变化，但新路径是否符合原阈值仍需真实C2检查，未预设PASS。

## 候选与严格checker

唯一新数值组是16_adjacent/pre、kml/checkpoint_strict、fp32/fresh/HBM0：参考完整B64/CKPT0，候选完整B64/CKPT1。两侧使用相同 `candidate/full_batch_step.py`，其mean损失AST与R5参考一致，仅image参数名改为y0；一次zero_grad、一次backward、一次AdamW step。原lr/betas/eps/weight_decay、损失分母、参数集合与严格比较器保持，不调用微批sum路径。

checkpoint直接复用冻结 `candidate/training_step.py::enable_checkpoint`，与baseline中逐encoder层的非重入实现一致，forward参数和关键字参数原样传入。参考先完成并释放实例；候选构造独立实例、开启12层包装，再加载同一固定state。包装不会回写或污染参考模型。未改变模型结构、K bias或训练梯度。

CPU36 C组、框架前同PID授权捕获/选核/绑定、框架后全部可见TID非空子集检查、合法单核calling TID、实际Torch36/OMP API36与KML库路径/SHA/真实GEMM/结束重验保持。新增双方KML调用计数。7个checkpoint仍覆盖参考与候选边界，不把checkpoint之间的瞬间或OpenMP team当作已证明。

原一般tensor max_abs≤2e-5、相对≤2e-6；state绝对/相对≤2e-6、near-zero规则和精确结构/step检查均由原比较器执行。退出0的成功名为PASS_STRICT_CHECKPOINT_SYNTHETIC_ONLY，仅表示这一case；1为原数值失败，2为运行前提错误，超时/信号退出原样保留。

## 独立轻量训练内存入口

`train_memory.py`每次只运行一侧，在独立进程中加载一个完整模型、同一case和fresh AdamW，执行相同完整B64 mean步；CKPT0/CKPT1各启动一个进程。保留同样的输入梯度工作量，模型/optimizer训练必需的梯度和状态正常保留；没有等价checker的参数/梯度/输出比较快照、输出hook或trace。加载初权重后释放case中的重复state，再进入训练。

初始化和训练分别记秒、RSS/高水位bytes及MiB(2**20)。训练前只对自身进程clear_refs写5重置VmHWM，训练后立即读取，排除后置JSON/守卫校验开销；若该功能拒绝或不可用，退出2且不执行训练。初始化高水位另留，不把旧峰值相减当作节省量。[Linux内核proc文档](https://docs.kernel.org/filesystems/proc.html)定义clear_refs=5可重置进程RSS高水位；本轮仅核对设计和拒绝策略，未在Linux实际执行。

指标是HBM0下整个进程RSS，包含共享库页，不是tensor独占量、PSS或物理HBM驻留；要求HugetlbPages为0。单次fresh步包含AdamW首次状态分配，没有warm-up或重复稳态训练，因此仅是独立的首步训练内存/耗时诊断，不能当作吞吐基线或收益接受。

独立 `memory_gate.py`先核本R6严格PASS、完整1063项metrics、当前case/源身份、真实KML双方调用和CPU36证据。R5失败、旧代码、控制PASS或缺失证据不能解锁。实际训练内存仍需总协调另行安排，严格对照脚本不会自动调用内存入口；本轮两者均未运行。

## 本轮必要检查及未运行项

- **2项真实小型Torch检查通过**：原mean/一次fresh AdamW的精确对照；非重入checkpoint模型隔离、kwargs、重计算、输入/参数梯度及optimizer state原标准检查。使用本地原venv、实际Torch intra-op36，非完整模型/固定case/KML验证；单独进程运行，未批量重跑旧实验。先实现前的缺模块失败保留在checkpoint_tests_before.txt。
- **14项CPU36守卫检查本轮重跑通过**，覆盖实际线程元数据、合法单核、CPU/TID边界、证据及来源拒绝；这些含替身接口，非新增C2结果。
- **9项内存计量/门禁/阶段证据检查通过**，覆盖单位、缺失计数、意外hugetlb、拒绝重置、仅自身计数器、缺训练阶段边界、R5/旧源/缺KML/缺metrics拒绝。计量和PASS夹具为明确替身，不是训练内存或数值PASS。
- Python3.9 AST语法、mean表达式AST不变性、13个关键源字节不变、两个入口导入时不加载Torch/NumPy均通过；这是静态/导入检查，不称数值验证。
- 两个入口在Windows显式请求KML均在框架导入前退出2，无native fallback。4份shell/env及S00两段命令的Git Bash bash-n/LF检查通过；命令只做语法检查。真实Linux新包门槛、clear_refs权限/计数、KML与完整checkpoint数值尚未运行。
- 包CRC、成员唯一性、逐源SHA/大小/来源一致。完整模型运行0、C2 job提交0、训练内存/HBM实测0、节点/GPU小时0；没有本轮性能收益结论。

## 下一步与实质阻塞

本地候选和入口准备无实质代码阻塞，交总协调核包后由S00在新目录安排一组完整B64/CKPT0对CKPT1严格对照，沿用每域实际36核、首选分配38留2、24576MB同值limit和900秒边界。命令包含S00已实测的Donau PATH恢复，避免source runtime后丢失dsub。实际队列/身份和资源由S00在执行前核验。

**尚缺新C2数值证据及Linux轻量计量实测。** 数值未通过前不开展训练内存或宣布收益；新数值FAIL完整回传，不改阈值/eps/梯度或扩大矩阵。R5失败继续保留，不扩32电极、decoder数值、多域、长训练或真实HBM。自己的SESSION_STATUS.md和ROUND_DELTA.md指向本轮；六行摘要仅报增量，不替代本报告/源清单。
