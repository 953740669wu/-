# S00：新增三组首步内存配对与S07 R2启动失败

日期：2026-11-05（Asia/Shanghai）。
状态：READY_FOR_REVIEW / THREE_MEMORY_PAIRS_COMPLETE / S07_STARTUP_BLOCKED。

## 1. 结论

内存job2039061完成三个有效新增配对、六个不同PID，各完整B64/fresh一步，全部退出0。新增CKPT0/1训练峰值中位数5837.0234375/4835.3515625 MiB，步末RSS中位数3492.65234375/4498.19140625 MiB，首步时间中位数4.396932111587375/6.127788343001157秒。只接受为首步DDR RSS重复性诊断；候选峰值较低、步末RSS和单步时间更高，未接受稳态、真实HBM或生产收益。

其成功终态后才提交S07 job2039114。该job在S00自己的执行包装器第5行失败：计算节点没有所引用的登录节点调度环境文件。22项标准库检查、环境检查、逐rank授权验证及通信四项全部未启动。该错误由S00执行层引入，不是S07候选或Gloo测试失败。严格停止，没有重提、替换候选、改变资源方案或运行正式训练。

## 2. 前置条件与执行范围

按自己的短状态/增量、COORDINATION/STATUS.md相关行及AFTER_MEMORY_PROBE_R2_NEXT.md的S00节执行。必要参考为MEMORY_AND_PROBE_R2_REVIEW.md/.json、S02 R6 C2_HANDOFF.md内存节及原memory入口/门禁，S07 R2接口及其冻结R1接口、S07_R2_VALIDATION_MANIFEST.json。只展开当前任务必要文件。

| 原样包 | SHA256 | 份数/文件数 |
|---|---|---|
| S02_CKPT64_R6_CODE.zip | `26e542430f024f60277bdbbbc699b41a203ee74270022806074040a531ac166f` | 3份，各28文件 |
| S07_R2_VALIDATION.zip | `9a95a23c14c9b6c65191bc9883abefb0ce0cf52c637ec370a357a02f56f27367` | 1份，34文件，59801bytes |

三份R6源码/文档均由原ZIP解压，84项前后字节未变，各只调用一次原run_s00_job.sh memory，保留原run_c2_memory.sh内每进程360秒+15秒timeout。新增外层仅编排、核证和有界清理，没有更改训练代码、比较器、门禁、阈值或输入。S07原34项与SOURCE_MANIFEST内33项全部核验；候选、模板及冻结R1副本未改。

固定case只读沿用`/home/share/dengqingtian/opt/stage4_sessions/S00/S02_CPU36_R5_20261105T034705Z/fixed_16_pre.pt`：271979513bytes，SHA=`4de1fb40eb1c4b43a8747586399f336bf9e37184592d66fdbf711abad8469846`，前后mtime_ns均1793850592308132590。严格PASS仍引用2037034，原result SHA=`1f2aac7dee498cd839b696d1305e80236227c445da69e26ffd38f5c80c9aba17`，1063项全部通过。本轮不重跑该严格数值对照，不复制/上传/生成case，不覆盖2037434。

本地仅work/S00新增执行层bounded_round_step.py、prepare_memory3_s07.py、run_memory_three_pairs.py/.sh、run_s07_r2_job.py/.sh、收集/数据复核脚本及本轮证据。远端新目录为：

- `/home/share/dengqingtian/opt/stage4_sessions/S00/S02_R6_MEMORY3_20261105T072600Z/`，pair1/2/3各有独立payload和输出。
- `/home/share/dengqingtian/opt/stage4_sessions/S00/S07_R2_TWODOMAIN_20261105T072600Z/`，独立S07 payload。

阶段二/三、共享运行环境及其他任务状态未写入；上一轮报告/完整ZIP与既有包逐项SHA复核不变。旧状态先保存在本轮before快照，再更新当前短状态。

## 3. 环境、复现方式与成本

| 任务 | job/节点 | 北京时间起止 | 调度终态/退出 | 分配/限制与时限 | 实际墙钟 |
|---|---|---|---|---|---|
| 新增3内存配对 | 2039061/cn21340 | 15:32:21—15:37:01 | SUCCEEDED/0 | 38核；24576MB且同值limit；900秒 | 280秒 |
| S07 R2尝试 | 2039114/cn21340 | 15:38:32—15:38:33 | FAILED/1 | 76核；总24576MB且同值limit；300秒 | 1秒 |

内存调度原件0–37，实际每模型选0–35、保留36–37，38个不同物理核由冻结合同核验。S07调度原件分配0–75，申请numa count=2/pack；因包装器提前退出，逐域物理拓扑/逐rank的72实际核验证未到达，实际worker数0，不能称“两域通信已验证”。两job最终PID字段均`-`，无活动子进程；SSH及下载连接已退出。

外层内存执行截止850秒，清理预算最多15秒，保留原内部timeout。每次原入口在自有新session启动，外层跟踪其后代session，命令结束后记录exit、remaining_live及清理动作；本次三个入口均exit0、remaining_live=[]、没有发送TERM/KILL。超时/中断清理分支本轮未触发，不声称此次验证了所有故障清理分支。S07自己的Linux组清理检查也尚未运行。

原内存Python为R4 venv/bin/python3（Python3.9.9），torch2.7.1+cpu来自`/home/share/songzhenlong/eitfm/sw/torch_kml/torch`，numpy1.26.4来自该venv。OMP36/MKL36/OpenBLAS1/cores/close；HBM0。实际KML与shim路径/库SHA/结束重验见六个result.json，调用各149/197。每个完整pre步encoder37995777、decoder29416449参数存在，decoder本步不活跃；fp32、B64、原mean、fresh AdamW一次，预热0，输入梯度保留，无比较张量快照。

附带只读平台身份：Kylin Linux Advanced Server V10(Jasmine)，glibc2.34，aarch64-linux-gnu，GCC10.3.1；真实`/usr/bin/gcc`为1120960bytes，SHA=`69e9ed93cb21ec931eaad471cf1b6e940ee0c762b4c71eecef7ac0b30d22f999`，RPM=`gcc-10.3.1-66.p02.ky10p.aarch64`。`rpm -q libubsan`预期查询失败exit1，原文`package libubsan is not installed`，不是恢复成功或C测试失败。所有查询各设5秒执行上限；没有全盘搜索、联网、安装或环境修改，没有重复缺库job。

可复核的实际提交命令、资源及环境在received/submit_memory3.sh、submit_s07.sh、submission.json、djob_final.json；三个原入口命令与六个原进程命令、stdout/exit均保留。S07提交前memory_dependency.json及原始调度查询证明内存已成功且六PID有效，没有复用单域授权。

总时限预计1200节点秒，实际281节点秒（含S07失败1秒），约0.078056节点小时；累计S00十六job共764节点秒。不能将280秒作业墙钟替代下面的单步计时。一次文件传输认证阶段连接关闭后恢复同字节上传，未重试任何job或实验；原件/数值未改变。

## 4. 正确性

| 门槛 | 实际结果 | 结论 |
|---|---|---|
| 原包/文件SHA、LF及Linux语法 | R6三份84项、S07 34项全部通过 | 通过；语法检查不证明外部profile存在 |
| 严格PASS引用与memory_gate | 每份提交前、作业内原门禁各一次，共6次；均引用同一2037034原件 | 通过；未新增1063项数值重算 |
| 完整独立训练工作量 | 六不同PID，三次CKPT0→1；每进程完整B64/fresh一步，原梯度/AdamW检查通过 | 通过 |
| CPU36/KML/源与case | 每进程7检查，共42；errors=[]，全部可见TID在选中36核；每对KML149/197 | 通过 |
| clear_refs/HWM/hugetlb | 六进程重置可用；训练起始HWM=当时RSS且不高于初始化HWM；HugetlbPages=0 | 通过 |
| 退出清理 | 六模型exit0，三个入口exit0；无剩余live进程；调度终态PID清空 | 通过本次正常路径 |
| S07标准库22项/导入环境 | 包装器第5行在Python入口之前退出 | 未运行 |
| S07 normal/crash/collective-timeout/watchdog | 无allocation、environment_current、checks输出或worker | 全部未运行，不把非零当故障注入通过 |

六个loss均303.04705810546875。时间波动未被单独判作数值失败；原门禁与阈值没有调整。

## 5. 性能与内存

只统计**新增三个配对**，同一节点cn21340；bytes及MiB（2**20bytes）并存。为整个模型进程RSS/HWM，包含共享运行库页，不是tensor独占量/PSS/HBM驻留。训练峰值在后置校验/JSON之前读取，重置前初始化峰值、重置后起始RSS和完整未舍入时间均在原JSON及review.json单列。

| 新配对 | CKPT/PID | 训练峰值bytes | 训练峰值MiB | 步末RSS bytes | 步末RSS MiB | 一步秒 |
|---|---|---:|---:|---:|---:|---:|
| 1 | 0/2061672 | 6085783552 | 5803.85546875 | 3662311424 | 3492.65234375 | 4.749420389067382 |
| 1 | 1/2065777 | 5070233600 | 4835.3515625 | 4797898752 | 4575.6328125 | 6.127788343001157 |
| 2 | 0/2069454 | 6121635840 | 5838.046875 | 3642273792 | 3473.54296875 | 4.396932111587375 |
| 2 | 1/2072708 | 5125173248 | 4887.74609375 | 4716695552 | 4498.19140625 | 5.959001389332116 |
| 3 | 0/2076756 | 6120562688 | 5837.0234375 | 3668377600 | 3498.4375 | 4.396816019900143 |
| 3 | 1/2080003 | 5070069760 | 4835.1953125 | 4715880448 | 4497.4140625 | 6.208228330127895 |

| 配置 | 峰值MiB：中位数 [最小,最大] | 步末RSS MiB：中位数 [最小,最大] | 一步秒：中位数 [最小,最大] |
|---|---|---|---|
| CKPT0 | 5837.0234375 [5803.85546875,5838.046875] | 3492.65234375 [3473.54296875,3498.4375] | 4.396932111587375 [4.396816019900143,4.749420389067382] |
| CKPT1 | 4835.3515625 [4835.1953125,4887.74609375] | 4498.19140625 [4497.4140625,4575.6328125] | 6.127788343001157 [5.959001389332116,6.208228330127895] |

旧首组**单列，不并入新增统计**：job2037434/cn21339，CKPT0/1分别为峰值5836.0078125/4313.87890625 MiB、步末RSS3523.84375/3950.484375 MiB、首步2.4526388668455184/3.3435222790576518秒；来源R6_MEMORY_UBSAN_REPORT.md与原90文件ZIP。旧组节点不同，不能挑选旧候选峰值拼接新基线或当作相同主机配对。

三次新增观测都呈现CKPT1峰值较低、步末RSS及训练时间较高。没有长训练、重复稳态步、多域模型同步、有效全局batch/LR/schedule或真实HBM；这些数据不证明4GiB适配、真实HBM驻留或正式训练收益。S07没有数值、带宽或吞吐结果。

## 6. 接受条件与限制

内存新增三配对符合本轮门槛，可交S02和总协调复核空间/时间取舍；既有严格数值PASS、四个首步配对的诊断和收益接受仍须区分。

S07未达到执行验收：S00包装器错误地假定计算节点也有`/etc/profile.d/donaukit_scheduler.sh`。原job.log完整错误为：

```text
run_s07_r2_job.sh: line 5: /etc/profile.d/donaukit_scheduler.sh: No such file or directory
```

错误发生在现场调度查询及Python入口之前，没有现场逐rank allocation或Torch/Gloo能力结论；R2 22项、四个通信case及Linux组清理全部保持未运行。预检SHA/LF/bash-n通过不覆盖外部运行环境依赖，不能替代它们。

后续需S00先修正登录/计算节点间的原始调度证据交接，保留现场CCS_JOB_ID并在计算端核对当前job、真实授权与sysfs拓扑；复核新的执行包装层及启动前提后另行安排一个新job。不得静默重提本次作业、换R2候选或删身份/物理核检查。本轮没有改写失败包装器或执行修复后的版本，没有新运行许可推断。

UBSan缺库结论没有解决；只新增平台/RPM身份，未重跑恢复/C任务。旧失败原件及其他会话状态均保留，无生产部署。

## 7. 证据索引

报告绝对路径：`E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S00\MEMORY3_S07_R2_REPORT.md`。

完整证据绝对根：`E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S00\evidence\memory3_s07_r2_20261105\`。

| 完整原件包 | bytes/文件数 | SHA256 |
|---|---|---|
| JOB_2039061_full_evidence.zip | 320351/168 | `cd6be5d0aaf6a690524f465598f3a79df29c2b838ba35479437e4bce4d6f7613` |
| JOB_2039114_full_evidence.zip | 83313/52 | `6e3f10538532c3455e9a0f021466c16d25fa2b4968e81d31b8e39c0b9bab6563` |

解压在S02/received、S07/received；各COLLECTION_S00.json保留167/51项远端原始mtime_ns/bytes/SHA，ZIP与解压原件逐项核验。原mtime以JSON元数据保存，不声称Windows解压后的文件系统时间即远端原时间。

S02包含三份原包解压文件、全部六进程result/command/stdout/exit、六门禁、每份CPU授权、外层逐命令退出/清理、平台查询和严格PASS完整引用；S07包含原包、执行包装器、提交/依赖/调度终态及失败job.log。空目录不入ZIP。S07专用terminal收集器只修正“提交与实际执行”的证据标签，未改已投包装器或候选；real_S07_probe=false。

ROUND_REQUEST.json冻结资源/范围及旧产物SHA；review.json保留全精度新增配对、统计及旧首组，明确S07未运行。candidate/audit_memory3_s07_delivery.py仅做原件数据复核，不重新运行模型/通信。前后短状态快照、本轮ARTIFACT_SHA256.txt及顶层总索引用于交接。没有凭据写入文件。
