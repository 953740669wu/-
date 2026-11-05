# S01_CPU36_MODEL_R7：提交前与回传接口

这是新模型运行器候选，**尚未在Linux/C2执行，未获准自动恢复模型**。R2与R6均保留。执行前必须由总协调审核新候选，再由S00安排新job，不复用2026725或旧模型作业allocation。

## 明确环境与CPU合同

本候选固定诊断C组：OMP_NUM_THREADS=36、MKL_NUM_THREADS=36、OPENBLAS_NUM_THREADS=1、OMP_PLACES=cores、OMP_PROC_BIND=close。run_node16.sh与新环境包装共同显式设置；不继承MKL1，不调用torch.set_num_threads改变诊断结论。CORES_PER_DOM只能为36，旧4/38配置会拒绝。

调度授权集合在框架初始化前捕获；按现场单域38物理核心拓扑选择前36核并预留末2核。授权不足、37核、跨域不完整、占用末2核或SMT重复均拒绝。允许调度只分配正确前36核。manifest分别保存allocated/domain_cpus/selected/reserved/physical_siblings；分配38不虚报为36。

worker使用--physcpubind=<确切36核>和相应--membind。父监督器也缩到所选核心并集。模型中调用线程可被close固定为单核；每个已记录TID必须非空且在selected36内，真实torch intra-op必须36。interop照实记录（诊断中608，不等于实际启动608线程），不人为改为36。

## 1. 打包与远端提交门槛

包根布局：candidate/、interfaces/、SOURCE_MANIFEST.json、此接口说明。依赖lib/、output/cases/由S00从已核验来源原样复制，不包含在交付ZIP；不得改legacy NPZ或共享库。

- 将包放到当前账号自有的新S00或S01目录；不要覆盖旧目录/旧结果。设置S01_RUN为该包根，保留candidate相对导入。
- 必须核对整个ZIP和SOURCE_MANIFEST每项SHA；远端实际全部.sh/.env无CR，运行真正Linux bash -n。Python>=3.9语法也须检查。本地Git Bash检查不代替远端门槛。
- interfaces/cluster_runtime.env冻结当前已核验venv路径及C组环境。S00核对实际Python、torch/numpy/KML/OMP来源、调度授权与内存限制；变更外部环境须新记录，不沿用旧库SHA。
- 下一次范围仍不超过24GiB/900秒，HBM0、单域、16电极pre/dec、B32、三轮REPS1；本文件不提交或授权扩大。预检在同一job进行；读不到cgroup不宣称已经独立验证硬限。
- 在新job内以 `bash "$S01_RUN/interfaces/run_s01_startup36.sh"` 调用。一次性marker拒绝同目录重复启动；失败停止，不重提或扩大。

## 2. 新鲜同job预检引用

新入口支持 `bash "$S01_RUN/candidate/run_node16.sh" --preflight`。需要新job身份、NDOM=1和实际候选/库/输入路径；只导入numpy/torch/kml_ops及模型定义，不执行模型forward/backward。导入后采集实际线程、所有TID及实际已加载库，要求Torch36，shim和KML确已加载且身份匹配。

成功只向stdout打印 `evidence/CPU36_PREFLIGHT_<ns>.json` 绝对路径。包装器将其设为CPU36_RUNTIME_REFERENCE，再调用相同入口启动模型。正式runner要求该引用位于本包evidence目录、status=PASS_IMPORT_ONLY，且job/host/source四文件SHA/输入和基础库SHA/CPU合同/C组环境完全一致。旧job2026223或R3/R4旧预检不能直接复用。

该预检PASS仍不等于完整模型通过。它没有修改权重/随机变量/优化器，也没有自动生成正式数据划分。

## 3. 新字段与失败行为

- manifest.cpu36_version=`CPU36_MODEL_V1`；cpu_contracts记录授权/selected/reserved；worker_environment固定C组；runtime_reference冻结本job真实模块/库身份；cpu_contexts逐rank/round记录身份。
- sync_r<r>/cpu36_d<rank>.json为父进程写的轮次上下文。worker在before_framework、after_framework、每belt预热后、每个已选择part计时后和publish采集全部TID；检查均在计时区间之外。
- sync_r<r>/thread_rank<rank>.json原子保留全部checkpoint及错误；结果run.cpu36携带同样证据。run.affinity保留为调用线程值，不能将它改写为36核全集。
- 父监督器在worker有效身份握手后约50ms采集全部TID，保存rank<rank>.threads.jsonl；状态thread_monitor保存完整样本数、缺失/越界、TID及掩码历史。观察到越界或活进程缺证据就发ABORT并有界清理本任务session。
- 发布与汇总都核验真实Torch36/完整TID边界，汇总额外要求完整checkpoint、正确顺序/PID/时间窗、同context、相同环境/模块/实际库SHA以及父监测证据。任何缺证据、越界或实际线程数错误均FAIL；不会通过删除旧检查放行。
- 原缺域、错误/损坏/重复键/旧JSON、退出非零、超时、配置或源身份不一致的拒绝逻辑保留；只完整三轮才算旧A1波动，UNSTABLE保持非零。

TID总数、mask并集、omp_max都不是单独的通过判据；checkpoint和50ms采样也不能证明每个线程生命期的每个瞬间或精确team成员。新采样有成本，REPS1启动结果不作为正式性能，后续A/B需统一观测配置。

## 4. S02同PID守卫适配

S02不能继续用原4核/--threads4或“导入后主线程等于完整集合”的守卫。新的checker进程应先在框架导入前捕获自己的授权/receipt（可用cpu36_contract.select_cpus/discover_contracts），显式缩到selected36，然后在**同PID**内导入框架并调用validate_snapshot检查所有TID，核对torch.get_num_threads()==36。

保留selected36与全部TID子集的组合边界，记录环境/模块/库API和缺证据，不能只检查主线程或总TID数。cpu36_contract.py可作为冻结接口来源；模型/loader/有效批量/数值阈值不改。本S01包不直接执行或整合S02 checker，S02包装器由S00与S02在新清单中适配后另审核。

## 5. 完整回传

回传本次job终态/资源/实际命令、一次性marker、ZIP/source清单、预检原件、完整reports/run目录（manifest、逐轮JSON/状态、summary及sync全部文件），包括父线程JSONL和失败ABORT。原始NPZ无需下载。

COLLECTION应在稳定文件上保存原始mtime_ns、bytes和SHA，包括失败时已有文件；不要截断线程日志/伪造缺失结果。离线汇总若需恢复mtime，仅在独立副本按真实远端元数据恢复，不能改received原件或以进程结束时间伪造mtime。

保留LEGACY_TIMING_ONLY，已知16电极目标错配仍未修；此包不解锁科学效果、正式数值等价、HBM、内存收益或生产部署。
