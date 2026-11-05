# S02 R7：三组首步内存评估与连续五次更新入口

2026-11-05，Asia/Shanghai。状态：**LOCAL_PREPARED_FOR_REVIEW / SEQUENCE5_C2_NOT_RUN / SEQUENCE5_MEMORY_NOT_RUN**。

**建议保留checkpoint实验候选，暂不集成。** 三个新增首步配对在同一主机稳定呈现“峰值较低、首步更慢、步末RSS更高”；不足以证明连续训练省内存或稳态收益。本轮已完成五步严格门槛、独立五步内存入口、本地必要检查及新包；没有提交集群、运行完整模型/训练内存或改变checkpoint算法。

## 三组结果：独立重算，旧主机单列

新增数据为job2039061/cn21340、六个不同PID、三个CKPT0→CKPT1独立fresh首步配对。下表“0→1”均为同一配对中的CKPT0与CKPT1，RSS单位MiB，时间单位秒。

| 配对 | 训练峰值0→1 | 峰值降低 | 首步秒0→1 | 首步变慢 | 步末RSS 0→1 |
|---|---|---:|---|---:|---|
| 1 | 5803.8555→4835.3516 | 16.6873% | 4.749420→6.127788 | 29.0218% | 3492.6523→4575.6328 |
| 2 | 5838.0469→4887.7461 | 16.2777% | 4.396932→5.959001 | 35.5263% | 3473.5430→4498.1914 |
| 3 | 5837.0234→4835.1953 | 17.1633% | 4.396816→6.208228 | 41.1983% | 3498.4375→4497.4141 |

峰值中位数5837.0234/4835.3516 MiB，步末RSS中位数3492.6523/4498.1914 MiB，首步秒中位数4.396932/6.127788。配对步末RSS分别增加31.0074%、29.4987%、28.5549%。候选峰值约4.72—4.77 GiB，不能声称适配4 GiB或真实HBM驻留。不同主机的旧2037434/cn21339按旧审核单列：首步峰值降低26.08168%、耗时增加36.32346%；本轮不并入新三组统计，也不把旧26.1%沿用为本轮结果。

本轮只读原始六result、严格PASS引用、collection及必要源码，重新计算三配对与中位数，和协调MEMORY3_S06R3_REVIEW.json一致。7份保存的result（六内存+原严格）逐项匹配collection SHA/bytes、固定case/权重身份和R6代码声明，49项保存CPU36 checkpoint按原合同复核；远端原mtime只按collection元数据记录，不把本地解压时间称原时间。六内存的HWM重置成功、起始HWM=RSS、hugetlb=0、KML149/197均保持。没有重跑模型、旧一步对照或三组内存。

认知更新：原R6/job2037034的1063/1063严格PASS已完成，引用原件SHA=`1f2aac7dee498cd839b696d1305e80236227c445da69e26ffd38f5c80c9aba17`；本轮复核保存证据，不冒充新增数值执行。旧R5拆批95项FAIL和Windows旧失败不改写。

## 新五步严格入口

配置仍为16_adjacent/pre、完整B64、fp32、原mean/AdamW及输入梯度语义、CPU36/KML/HBM0。两侧各建一个隔离模型/AdamW，仅序列开始加载一次同一固定state，随后连续更新五次。checkpoint仍直接使用原逐层非重入包装，无算法/模型/容差改动。重复同一冻结case五次，不是新训练数据或收敛实验。

`sequence_core.py::SequenceState`负责一次初始化、梯度清理和真实AdamW状态承接。每步forward前清除上一轮模型和输入梯度，继续调用原字节的full_batch_step；该原helper内部forward后的zero_grad保留。每次只一次backward/step。真实optimizer step必须0→1→2→3→4→5，活跃状态键/梯度集合和输入/参数/moments有效性均检查；重建model/optimizer、跳步或重复步号拒绝。

`check_sequence5.py`逐步用原比较器检查输出、输入/参数梯度、更新后参数、相对各自上一步参数的增量、AdamW moments及精确step。每步1063项数字指标，固定八组覆盖为loss1/input_v1/input_y0 1/output3/grad153/param299/delta299/state306；精确step等另查。五步共5315项才可能完整PASS，不只比较loss。任一步原阈值失败保存完整当前metrics/failures和前序结果，立即停止，不更新下一步。

每步记录case/源清单SHA、前后model/optimizer对象标识、真实步号、清梯度信息、完整参数+optimizer状态摘要。两侧起点摘要必须相同；下一步before必须与各自前一步after精确衔接。比较快照和全状态摘要仅存在于严格入口，绝不拿其RSS当训练内存。

同PID框架前授权/拓扑/绑定、实际Torch36、全部可见TID非空子集、合法单核caller、KML/shim/OMP来源/SHA与实际调用保持。每步双侧KML增量记录，5步共24个有序CPU checkpoint；不把离散checkpoint解释为每个瞬间或精确OpenMP team已验证。

## 独立五步内存入口与门禁

`train_sequence5.py`每侧独立进程，一次模型/AdamW初始化，释放重复初权重后连续五次更新。没有比较张量快照、输出hook/trace或全状态哈希。逐步验证真实step=1..5和梯度/状态有效性，每步记录KML调用、case/源身份、CPU36和前后RSS。

初始化及每步前后分开记录bytes/MiB(2**20)/秒。每步清梯度后读before_reset，按原memory_metrics重置自身HWM、读training_start、计时原训练步，计时结束立即读取训练RSS/HWM，再做有限性/步号校验、loss.item和CPU检查。重置失败时该步不运行；任何异常停止后续并保留当前局部记录。后置检查可能影响下一步allocator驻留，因此据实记录前后RSS；不称无观测开销的稳态训练。

`sequence_gate.py`要求当前新包的完整五步严格PASS，各步完整原指标、连续状态链/对象/清梯度、当前case/源SHA和全部CPU/KML证据；旧单步PASS无效。每个内存进程也自行验证门禁，并核实际库SHA与新五步严格引用一致。只有通过新门槛且协调另行安排才执行，不自动串联。此入口只测五步短序列、HBM0进程RSS（含共享页），非PSS、tensor独占量、物理HBM驻留或正式收益。

## 本轮验证与证据边界

- **3项小型真实Torch36检查通过**：连续五步与手工承接参数/moments/输入梯度的精确对照；CKPT0/1五步原比较器对照；重建optimizer/跳步拒绝。旧梯度用大哨兵值覆盖后确认清除，不靠重新构造训练状态求通过。为小模型Windows/Python3.11.9/Torch2.7.1+cpu检查，不是完整固定case或C2结果。
- **11项标准库协议/替身检查通过**：五步完整门禁、旧一步PASS拒绝、状态摘要/计数/对象断链、缺/重复/失败指标、KML缺失、错误来源、HWM/计时/采样/后置校验顺序、重置失败不更新、第二步失败停止、数值失败保留当前并停止、24/15 CPU序列覆盖与无框架导入。替身不是Linux计量或实际CPU验证。
- **真实旧PASS负控1项**：直接把磁盘2037034的1063/1063 PASS送入新五步门禁，明确拒绝，未导入框架或训练。内存CLI同样以退出2拒绝该旧引用；严格CLI在Windows请求实际KML明确退出2，无fallback。
- Python3.9 AST语法、13项R6基础源原字节、42项既有来源SHA/bytes/mtime不变、包CRC/成员唯一/逐源SHA/大小一致均通过。两份shell/env加S00两段命令共5项Git Bash bash-n/LF检查通过，命令未执行。这些不是数值验证或Linux实际执行。

收尾来源检查识别出先前拒绝测试沿用已有输出路径、读到了旧版本JSON；入口正确拒绝覆盖。本轮保留旧记录，改用全新rejected_final_*路径重新运行并核对最终源/清单SHA。更正只涉及核验脚本/证据，未改候选包；过程见evidence/entry_receipt_version_note.json，最终引用见local_validation.json的final_entry_rejections。

本轮完整模型/C2/五步训练内存/HBM执行均0、集群提交0、节点/GPU小时0。可见Get-Process未显示匹配计算任务；远端队列本轮未查询，不据可见列表断言所有旧任务不存在。写入仅本R7目录及自己的两份短交接文件，不改S00、协调、R6或旧结果，不操作Git/共享环境。

## 交付与下一步

绝对根：`E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S02\round7_seq5_20261105T082315Z`。

| 产物 | 本根内位置 |
|---|---|
| 新代码包 | package/S02_SEQUENCE5_R7_CODE.zip |
| SHA/大小/逐文件绝对来源 | package/PACKAGE_MANIFEST.json；SOURCE_SHA256.json；package/S02_SEQUENCE5_R7_CODE.zip.sha256 |
| 最小新增代码和相对原内存入口diff | diff/SEQUENCE5_ADDITIONS.patch；diff/R6_MEMORY_TO_SEQUENCE5.patch |
| S00命令、资源、退出、停止与回传 | C2_HANDOFF.md |
| 三组重算与保存原件身份复核 | evidence/memory3_assessment.json；saved_result_identity_review.json |
| 本地实际检查日志 | evidence/native_tests_after.txt；protocol_tests.txt；real_one_step_pass_rejected.json；local_validation.json |
| 旧来源起点/终检、包核验与全索引 | evidence/inputs_before.json；final_review.json；package_validation.json；ARTIFACT_SHA256.txt |

新ZIP **55378字节、24文件**，SHA256 **bb405ccde523e63ea5db98aa3ab2b5ab622ded3e0f1711ec312ac8d29c014092**。固定case只读沿用R3原绝对路径 `E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S02\round3_20261104T134939Z\case\fixed_16_pre.pt`，271979513字节，SHA=`4de1fb40eb1c4b43a8747586399f336bf9e37184592d66fdbf711abad8469846`；无复制/重新导出或生成输入。

本地准备无实质代码阻塞。待总协调核包后，由S00另行安排单域38分配/36实际、24576MB且limit同值、最长900秒的一组五步严格对照；完整通过后才另行安排两个独立五步内存进程。严格内层780+15秒，内存各360+15秒；触及预算就停止回报，不扩大。登录侧才恢复Donau CLI，计算侧不引用缺失的登录profile。

**尚缺新五步C2严格数值和五步独立内存实测。** 即使五步完成，也只能扩大到这段固定case短序列的证据；不称稳态/收敛、4GiB适配或生产接受，不自动集成、扩大模型矩阵或开展真实HBM。
