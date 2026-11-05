# 本轮固定交接：00、06、07

日期：2026-11-05。沿用现有独立会话；先读自己的状态/增量与总表，只展开本任务参考。结束更新自己的两份短交接文件，按六行格式回报本轮变化。

## S00

**本轮目标：** 先安排一个已有R6完整B64 CKPT0/1独立首步DDR内存诊断job，首选分配38/实际36留2核、24576MB且limit同值、900秒内。然后安排一个独立干净环境UBSan恢复/新50场景job，同核/内存边界、300秒内。各最多一个新job，不扩大真实HBM、模型规模或两域通信。

**参考文件：** S06_S07_AND_R6_RUNTIME_REVIEW.md已接受job2037034固定case通过。内存使用work/S02/round6_ckpt64_20261105T043038Z/C2_HANDOFF.md的内存节、原memory_gate.py/run_c2_memory.sh及本次真实PASS结果；路径work相对c2/stage4_sessions。S03继续原round2/LINUX_COMMANDS.md和job2037064的实际-lubsan错误，不重跑旧25场景。

**完成标准：** 内存提交前核原包/代码/case及真实PASS引用，两个独立进程记录CKPT0/1的不同PID、相同case/完整训练工作量、CPU36、真实KML、初始化/训练RSS及bytes/MiB/秒、计数reset和退出证据。clear_refs拒绝/hugetlb非0/计数不可信即停，不能放宽门禁。先将结果标首步诊断，不当作内存收益正式接受。

S03先只检查有限的已有GCC/运行库位置（编译器-print-file-name、系统已知库目录和已核实的现有工具链），不全盘搜索或安装包。可在任务自有目录配置匹配的已有库搜索路径/链接名，记录实际编译器/运行库SHA、ELF/依赖及最小正常程序和故意UB程序的预期退出。控制未通过不进入50场景；无匹配库时报告准确阻断，不移除UBSan或换判据。通过后在同一有界job运行原新previous/candidate各50场景与独立库构建，完整回传所有步骤/原件。两项分别记录真实job资源、命令、终态、原mtime_ns/bytes/SHA；不自行加06/07探针。

## S06

**本轮目标：** 在自己的新round保留R1，最小修复线程观测口径及父进程外部中断/异常时的子进程组清理；不做新编译/模型优化。

**参考文件：** 自己的SESSION_STATUS/ROUND_DELTA、本次审核的S06节、candidate/run_linux.sh、probe.py、run_probe.py及既有7项检查。原C组为OMP36/MKL36/OpenBLAS1/cores/close；必要时只读复用已接受CPU36合同接口，不改冻结来源。

**完成标准：** OpenBLAS1、记录并拒绝实际Torch不是36，不用set_num_threads覆盖观测；框架后及各段退出前记录全部可见TID掩码，核对属于S00授权选中36核，可复用冻结合同的snapshot/validate接口。父进程收到TERM/中断、wait异常和超时均只清理本任务创建的子进程/session并有界回收。补针对性正负检查，Linux组清理未实测就明确保留，不声称Windows已证明。新round检查应可搬移，不靠固定祖先目录定位项目源。交最小diff/新包或清单/SHA/修订命令及短状态；不安装环境、不提交集群job、不改R1证据或扩大性能搜索。旧索引包含的可变状态先留当时副本，再按交接约定更新当前状态。

## S07

**本轮目标：** 在新round保留R1，补allocation/manifest与当前作业身份的一致性检查；保持最小2-rank张量探针，暂不排新两域作业。

**参考文件：** 自己的SESSION_STATUS/ROUND_DELTA、本次审核S07节、comm_probe.py的load_allocation/worker、test_probe.py及INTERFACE_FOR_S00.md。当前授权现场字段为CCS_JOB_ID，不能只信JSON里的非空字符串。

**完成标准：** load_allocation在启动worker前拒绝缺失/不匹配的CCS_JOB_ID，worker在导入torch前再次核对当前job与manifest；补匹配通过、旧/缺失job拒绝检查。保留原逐rank授权/调度原件、数值/故障判据及有界清理。交最小diff、来源SHA、修订接口/短状态，不改正式训练batch/LR/schedule，不运行真实通信或申请资源。修订核验后再单独安排76核两域小试。
