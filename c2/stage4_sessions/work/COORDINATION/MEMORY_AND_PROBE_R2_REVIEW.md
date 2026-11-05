# 首步内存与06/07修订复核

2026-11-05；总协调独立复核；机读结果MEMORY_AND_PROBE_R2_REVIEW.json。

## S00

接受2037434的一组同主机、独立进程首步DDR RSS诊断；接受2037491的缺库阻断证据。没有稳态、正式收益、HBM或生产集成接受；新50场景和独立库未运行。

S00本轮索引157项及总索引663项全部核验，顶层报告指针/收尾状态/包清单与本轮结果一致；内存包90文件及UBSan包49文件核验通过；ZIP与解压原件逐字节一致，collection内89/48项大小/SHA一致。远端原mtime_ns保存在collection元数据；本地解压时间不同，不声称本地文件系统保留原mtime。ZIP SHA分别为d2dd91be74c2bba01f529f926d07ab38b184d88b6389bcbae0a1283fd1f51881、08410627941e6249cb10fed875c9204891f6ad9cdc93364880051ae3b9a22754。

2037434/cn21339：CKPT0 PID1428225、CKPT1 PID1429732，完整B64、fp32、fresh AdamW一步，CPU36检查各7个、全部可见TID掩码合法，实际KML149/197。源与case身份、2037034严格1063/1063 PASS原件SHA核验一致。clear_refs重置成功，训练起始HWM等于当前RSS，hugetlb=0。

| 配置 | 训练峰值MiB | 首步秒（约） | 步末RSS MiB |
|---|---:|---:|---:|
| CKPT0 | 5836.0078125 | 2.452639 | 3523.84375 |
| CKPT1 | 4313.87890625 | 3.343522 | 3950.484375 |

峰值降低26.08168%，首步耗时增加36.32346%；步末RSS反而更高。仅固定16_adjacent/pre合成case一个配对；候选峰值约4.21GiB，不能称适配4GiB，也不能换算成真实HBM驻留。原始全精度字段在JSON。下一轮只重复同口径首步计量，不改候选、不自动集成。

2037491仅在获准有限位置未找到libubsan，控制程序、新50场景、新.so均未运行。不重复同一缺库尝试；可在下一个既有job只读记录发行版/编译器包身份，不安装或放宽sanitizer。

## S06 R2

R2索引65项、payload索引12项全部核验；S06_R2_PAYLOAD.zip SHA=62b28092892ac7ed87f1bc8b8c7d773678b9a38ea78d42f621ddc2e72e174975，13文件。Python3.9 AST通过。线程观测/清理修订来源核验通过，但文档指定前置检查有可复现阻断，不能直接上集群。

临时独立副本复跑：普通父解释器26项=23通过/3 Linux跳过；README_R2.md指定的`python -I -S -B -m unittest discover -s tests -v`为22通过/3跳过/1失败。日志S06_R2_REVIEW_TESTS_UNISOLATED.txt、S06_R2_REVIEW_TESTS.txt。

失败位于payload/tests/test_probe.py的test_isolation_requires_I_and_S：直接调用probe.isolate([])，假定父解释器未带-I/-S，文档恰好带了二者。应将负例放到明确不带隔离参数的独立子进程，检查原拒绝原因；同时保留-I/-S正例及全回归。保留R2原包与失败日志，S06只做最小新修订，不改isolate或删断言。实际Torch/C2/Linux组清理/compile仍未测。

## S07 R2

33项交付大小/SHA通过；父入口及worker在CPU/框架前核对现场CCS_JOB_ID。冻结CPU合同/入口未变。临时副本22项=21通过/1 Linux跳过，日志S07_R2_REVIEW_TESTS.txt；Python3.9 AST通过。接受本地准备，未导入真实Torch或运行Gloo。

33项与原SOURCE_MANIFEST.json原样打包为S07_R2_VALIDATION.zip，34文件59801bytes，SHA=9a95a23c14c9b6c65191bc9883abefb0ce0cf52c637ec370a357a02f56f27367；包清单S07_R2_VALIDATION_MANIFEST.json。下一轮只排一次76分配/72实际、总24GiB、300秒的固定小张量通信，不启动训练或4/16域。

## 版本与交接

本地HEAD仍51d4089，未声称远端推送。旧待提交清单含已变的短状态，新Git清单整合旧未提交范围并核当前SHA。06来源和失败证据可归档，不等于运行许可。旧协调短状态已存history/PRE_MEMORY_PROBE_R2_20261105/。下一轮按AFTER_MEMORY_PROBE_R2_NEXT.md。
