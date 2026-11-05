# S00：R7独立五步内存测量

2026-11-05，Asia/Shanghai；轮次20261105T093446Z；job2040363/cn21339。

只提交一个新job，SUCCEEDED/jobExitCode=0；CKPT0/1两个不同PID各完整连续五步，原CPU/KML/状态及HWM证据通过，全部正常退出。本轮没有重跑严格数值、S07或S06，没有自动重试。原2040203五步PASS只作引用，经原sequence_gate再次核验；本轮结果仍为一组固定case五步短序列DDR诊断，不能称稳态、收敛、真实HBM、正式收益或生产集成接受。

## 逐步内存及耗时

全部RSS为进程VmRSS/VmHWM，含共享库页；MiB=2**20 bytes，不是tensor独占量、PSS或HBM驻留。表格舍入显示；原bytes、完整小数及每步before_reset/training_start/training均在REVIEW.json和原result.json保留。步末RSS为训练步返回后第一时间采样，位于后置状态/梯度校验、loss.item和JSON之前。

| 步 | CKPT0峰值MiB | CKPT1峰值MiB | 峰值降低 | CKPT0步末MiB | CKPT1步末MiB | 步末降低 |
|---|---:|---:|---:|---:|---:|---:|
| 1（首次） | 5905.29 | 4300.44 | 27.18% | 5308.80 | 3962.71 | 25.36% |
| 2 | 6711.67 | 5389.98 | 19.69% | 6089.75 | 5026.66 | 17.46% |
| 3 | 6789.91 | 5806.46 | 14.48% | 6297.61 | 5468.38 | 13.17% |
| 4 | 6791.18 | 5936.27 | 12.59% | 6116.13 | 5624.72 | 8.03% |
| 5 | 6712.26 | 6040.51 | 10.01% | 6038.16 | 5676.59 | 5.99% |


| 步 | CKPT0训练秒 | CKPT1训练秒 | 耗时增加 |
|---|---:|---:|---:|
| 1（首次） | 2.670740 | 3.356333 | 25.67% |
| 2 | 2.322330 | 3.196592 | 37.65% |
| 3 | 2.296110 | 3.140047 | 36.76% |
| 4 | 2.304459 | 3.058114 | 32.70% |
| 5 | 2.316488 | 3.154700 | 36.18% |


第一步单独比较：候选峰值降低27.18%，步末RSS降低25.36%，训练耗时增加25.67%。这不是把五步当作五次fresh初始化；每个进程只在序列开头初始化一次模型/AdamW。

第2—5步的峰值RSS中位数为CKPT0 6751.08、CKPT1 5871.37 MiB，按两侧中位数比计算降低13.03%；步末RSS中位数为6102.94/5546.55 MiB，降低9.12%；训练耗时中位数为2.310474/3.147373秒，增加36.22%。这些是同一短序列四个不同更新位置的摘要，不是四次独立重复实验，也不是逐步百分比的中位数。

候选第2—5步峰值从5389.98升到6040.51 MiB，步末RSS从5026.66升到5676.59 MiB；相对基线的逐步峰值节省从19.69%收窄到10.01%。当前每一步候选都更低、更慢，但尚未观察到稳定内存平台，不能用首步27.18%外推持续训练。保持实验候选，交S02/总协调评估取舍，不自动集成或扩配置。

## 执行范围与身份

按COORDINATION/AFTER_2040203_NEXT.md的S00节执行。先读自己的短状态与交接，再核当前账号队列、五步内存提交标记/目录及旧严格payload下的memory输出，均无本轮已有执行，未据旧短状态直接重提。2040203实际SUCCEEDED/exit0、PID清空后，才准备新目录并通过原gate。Git开始HEAD=5a22dbe，收口只读HEAD=5a22dbe；未操作共用暂存区、其它任务目录或环境。

原R7包55378bytes/24文件，SHA=bb405ccde523e63ea5db98aa3ab2b5ab622ded3e0f1711ec312ac8d29c014092，在新目录`/home/share/dengqingtian/opt/stage4_sessions/S00/S02_SEQUENCE5_R7_MEMORY_20261105T093446Z`原样解压，24源及LF/语法核验通过；比较器、内存入口、训练算法和阈值未变。固定case仍只读引用S02_CPU36_R5_20261105T034705Z/fixed_16_pre.pt，前后271979513bytes、SHA=4de1fb40eb1c4b43a8747586399f336bf9e37184592d66fdbf711abad8469846及mtime_ns一致。

2040203严格引用SHA=905866e1149ba796652315083d0f79c3a705700c82296c172b962cbd009d4c93，源/case/完整5315项及状态链由原sequence_gate复核。提交前gate、原memory包装器gate、两个内存进程各自原gate均通过，共四处实际引用核验，不是四次模型严格重算。下载后再对同字节源及完整引用运行原标准库gate，exit0，不运行Torch。

实际提交完整参数保存在received/memory_submission.command.json：q_hpcai，单节点单NUMA，38分配/36实际计算留2，总DDR24576MB且limit同值，900秒，--env none；直接执行原`payload/run_s00_seq5_job.sh memory`，保留每进程360秒timeout及15秒kill上限。原生CCS_JOB_ID由调度继承，计算端仅source包内R4环境文件，不source登录profile、不要求C++编译器。候选仍固定16_adjacent/pre、完整B64/fp32、原mean/AdamW、原输入梯度语义、OMP36/MKL36/OpenBLAS1/cores/close、HBM0；无warmup、比较快照或活状态摘要hash。

## 每步证据与退出

- CKPT0 PID=2423892，CKPT1 PID=2427174，各completed_steps=5、exit_code=0、状态DDR_SEQUENCE5_DIAGNOSTIC_ONLY_NOT_STEADY_STATE；两个进程顺序执行，模型/AdamW各只初始化一次，每侧对象ID在五步内不变。
- 每步before/after证明completed_updates及AdamW step依次0→1→2→3→4→5，第一步前无optimizer state，之后153个活跃参数状态持续承接；每步先清输入/参数梯度，后置输入/参数梯度及moment有限性通过。不是每步重建optimizer或重新加载初权重。
- 各15个有序同PID CPU36检查点，共30个；分配0—37、计算0—35、保留36—37，DDR NUMA0；原CPU36合同复核全部可见TID掩码在选核内，实际Torch intra-op=36，不要求瞬时TID数恰为36。
- CKPT0每步实际KML149次，CKPT1每步197次；两侧实际加载库路径/SHA与2040203严格引用完全一致，原case/初权重/源身份一致。
- 共10次clear_refs=5成功，每次重置后的起始VmHWM=VmRSS且不高于重置前HWM；训练峰值在计时结束后、后置验证/JSON之前立即读取。所有原始采样HugetlbPages=0。初始化RSS/HWM及时间另存，没有混入重置后的训练峰值。
- 两侧loss序列均为303.04705810546875、95.03941345214844、58.38131332397461、61.620426177978516、47.85975646972656。这是本次观测，不替代完整输出/梯度/更新/moment的原严格门槛，也不称收敛实验。
- 两个模型进程各正常exit0、原包装器完成memory模式、调度终态PID为`-`，本轮正常退出路径完整；无超时或异常信号清理实测，不据此宣称新的故障路径覆盖。无未完成步、无活动S00 job。

job于2026-11-05 17:37:17—17:38:23中国时间运行，起止66节点秒；调度usage=65秒单列。此前累计19job/898节点秒，本轮后已知20job/964节点秒；不能以训练计时之和替代完整作业墙钟。SSH/SCP均正常退出，认证信息未写项目文件。

## 证据交付及限制

本轮根：`E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S00\evidence\sequence5_memory_20261105T093446Z`。

完整包JOB_2040363_full_evidence.zip：249816bytes/66文件，SHA=6941acb9015876303cf5917ac11c5e601a56d734198806772af76f500094e7dc。JOB_2040363_receipt.json为远端原回执；解压位于received/。COLLECTION_S00.json的65项远端原mtime_ns/bytes/SHA逐项核验，全部66项与ZIP逐字节一致；原mtime以元数据保存，不冒称Windows解压mtime等于远端时间。

原结果：received/payload/evidence/sequence5_2040363_memory/ckpt0|ckpt1/result.json；同目录保留原command/stdout_stderr/exit_code、identity/cpu_allocation/strict_gate及失败字段（本次无失败）。原严格引用全JSON另存strict_reference_result.json，来源/前后SHA/mtime回执齐备；没有复制271MB case或运行严格检查器。

REVIEW.json保留逐步完整bytes/MiB/秒、第一步与第2—5步分组、范围/中位数和各步配对百分比。candidate/audit_sequence5_memory.py只复核原件、原CPU合同及标准库gate，不训练。ROUND_REQUEST.json、PROTECTED_BEFORE.json、before/after短状态、原提交/调度/命令、ARTIFACT_SHA256.txt用于交接。旧严格结果、旧07/06失败、原包及受保护报告SHA未改。新增candidate/sequence5_memory_once.py仅做S00准备/单次提交/观察/收集，未改候选。

本轮没有严格重跑、S07/S06重提、数值阈值调整、真实HBM或正式训练；只交本轮结果与证据给总协调，不自动扩大实验。
