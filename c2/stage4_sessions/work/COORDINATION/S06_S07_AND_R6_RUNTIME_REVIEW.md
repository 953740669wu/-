# 06/07预备交付及00新回传审核

日期：2026-11-05。先读短状态/变化摘要，仅为本次验收展开新代码和证据。本轮没有新SSH或提交作业。

## 新checkpoint数值结果：接受固定case通过

S00 job2037034/cn21339，33秒、exit0，完整B64/CKPT0对CKPT1的1063项原严格指标全部通过，每项max_abs/relative均0；双方真实KML调用149/197，7项同PID CPU36检查及来源/库身份有效。固定case、原mean、12层非重入checkpoint和独立模型实例记录一致。总协调逐字节/哈希核验48份原件与R6实投包，并独立检查全部指标及CPU合同。

决定为**ACCEPTED_FIXED_CASE_CHECKPOINT_EQUIVALENCE**，只限16_adjacent/pre固定合成case，不覆盖32电极/decoder、训练效果或内存收益。R5拆批95项FAIL保留。可安排已有R6轻量内存入口的有限首次实测。

计量入口对自身进程clear_refs写5以重置RSS高水位，符合[Linux内核proc文档](https://docs.kernel.org/filesystems/proc.html)中该接口的定义。实际权限、reset前后计数与HugetlbPages仍须作业内保存；拒绝/计数不可信就停止，不能用包含初始化/比较快照的旧高水位替代。只测两个独立fresh首步的整个进程RSS/耗时，不接受稳态性能、tensor独占量或HBM驻留结论。

## S03：接受链接阻断证据，不接受新C结果

job2037064/cn21339，2秒、exit1。43份原件与实投源包身份一致；actual build_previous保留-fsanitize=undefined，但链接报cannot find -lubsan，50场景和新.so均未到达。当前准确结论是该干净默认工具链不能链接UBSan，不是候选未通过50场景，也不证明所有现有工具链都不可用。

可先在新有限任务中找已有匹配运行库，冻结编译器/库路径/SHA/ABI，做极小正常/故意UB的编译执行正负控；通过后才在相同环境继续原50场景。不删sanitizer、不安装/修改系统环境、不重跑旧25场景。

## S06：交付检查通过，上集群前需修订

27项交付哈希一致，在保持其原目录层级的独立副本复跑7项检查通过。初次搬移副本因测试硬编码ROOT.parents[3]找到错误项目路径，属复核夹具定位错误，恢复原层级后通过；不把它算成C2或候选执行失败。

代码审查发现两项必须补齐：

- candidate/run_linux.sh将OPENBLAS_NUM_THREADS设36，偏离已接受C组的1；probe.py又无条件torch.set_num_threads，可能覆盖实际配置。应统一OpenBLAS1，观测并核对实际Torch36，不能先强制改值再声称观测通过。
- run_probe.py只在自己的TimeoutExpired分支清理子进程组；收到外部TERM/KeyboardInterrupt或其它wait异常时，没有finally清理已独立建session的编译/探针子进程。需补本任务范围的有界清理和证据，避免父进程退出后子任务残留。

原探针C2未运行；不接受编译可行、卷积数值或性能结论。只安排最小修订，旧历史和失败保留，不安装新Torch。新round的检查定位应显式使用来源或夹具，避免固定祖先层级妨碍可搬移复核。

## S07：交付检查通过，补当前作业身份再排期

17项delivery哈希一致，独立副本复跑16项标准库检查，15通过/1 Linux清理跳过。固定小张量、两rank边界及故障检查均是预备逻辑，不代表真实Gloo已运行。

candidate/comm_probe.py::load_allocation只检查JSON中job_id非空，没有与现场CCS_JOB_ID比对；worker也未在框架导入前核对manifest的job_id与现场值。旧allocation即使CPU集合恰好仍可见，也不应被当作本次job。应补缺失/旧job拒绝与匹配通过的小检查，保留手工核对调度原件和逐rankCPU边界。

两域方案为单节点首选76分配核、72实际计算核、24GiB总内存、300秒；这是方案，不复用单域allocation，本轮未批准新两域作业。正式DDP训练、batch/LR/schedule仍待定。

## Git与后续

独立核实a0b0308的19文件、51d4089的77文件及各自commit内清单，96份Git对象SHA/大小与范围一致，未重复c73b64e。均为本地提交，未声称远端推送。

本轮机读审核S06_S07_AND_R6_RUNTIME_REVIEW.json；复跑输出S06_PREP_REVIEW_TESTS.txt、S07_PREP_REVIEW_TESTS.txt。下一步按AFTER_S06_S07_NEXT.md固定三项交接，任务各自维护短状态。新数值PASS/链接阻断证据可归档；06/07旧代码先修订，不标成可执行版本。
