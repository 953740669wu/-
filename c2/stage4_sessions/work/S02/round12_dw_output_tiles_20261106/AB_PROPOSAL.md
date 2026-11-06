# R12固定两输出列块：同节点有限A/B提案

本轮只准备，未获本提案执行授权。需协调核定后另派S01绑定具体SHA、S00新部署/资源/唯一marker/清理复核。旧2043445/2048959/2049454及marker均不用；不提交、不安装、不默认集成。

候选仅在实际KML、CPU/fp32/contiguous、ta=True/tb=False/beta0/out=None、精确(512,2048,13312)时将C列分成0:1024/1024:2048。每块完整K=13312，A原指针，B/C分别偏移0/4096bytes，lda512/ldb2048/ldc2048。单个最终C，输入无Python侧大复制，不拆batch/K，不作部分梯度累加，不缓存权重。其他shape保持原路径，源baseline e6c5…不变，不加载R10 view候选。

## 可审阅应用命令

S00拟新建`/home/share/dengqingtian/opt/stage4_sessions/S00/S02_DW_R12_<唯一时间>/payload`，解包核SOURCE_SHA256与具体包SHA。S00需另备原生调度/物理核/NUMA/DDR/总截止/所属进程清理门禁；应用包装不代替它们。下列仅计算节点内入口，非提交命令，目录占位必须由S00替换成新审核绑定路径：

```bash
export S02_ENGINEERING_DESCRIPTOR=/home/share/dengqingtian/opt/stage4_sessions/S00/ENGINEERING_PILOT_20261105T154333Z/ENGINEERING_DESCRIPTOR.json
export S02_ENGINEERING_DESCRIPTOR_SHA256=b88ea9745147acf7fa70d51dc27c727f22f14e98af5dff1b80a9047e95648cd6
bash /home/share/dengqingtian/opt/stage4_sessions/S00/S02_DW_R12_NEW_REVIEWED_RUN/payload/run_ab_proposal.sh
```

包装`set -e`单次顺序链：

1. `screen_target.py`在真实KML执行一次原目标和一次候选目标，检查完整K/列偏移/lda-ldb-ldc、输出前后canary及A/B输入不变，使用原比较器比较输出。局部夹具沿预先固定seed2026、randn*0.01，不因失败换数值。guard缓冲和operand快照只为门禁，不能当性能结果或候选内部副本。首次实际数值失败退出并关闭候选。
2. `train_dw_ab.py --phase strict`在同job/节点/CPU和库下完整Encoder配对5次连续更新。仅当目标screen receipt/source/CPU/node/job一致且通过才启动。原seed0/B64/1600帧统计/前320帧顺序mask，比较h/voltage/coarse输出、loss分量和total、输入梯度、全部参数梯度/参数/delta、AdamW step/exp_avg/exp_avg_sq及buffers。原tensor/state/exact比较器门槛全部保留；任一FAIL停止，不转测时。
3. strict receipt SHA及源码/descriptor/host/job/selected36绑定后，分别独立新进程baseline/candidate各单epoch25次更新，前5预热、后20观察。相同1600帧、顺序和原25个mask哈希已固定在REFERENCE_EPOCH25.json；完整数据不重复/填充，不自动缩步。库/framework/env与前置阶段重核相同。没有profiler或输出hook，CPU/梯度状态/有限性、源/库、暴露、日志、保存及零额外更新恢复保留且两侧同样执行，计时分项。

## 计数与预算

逻辑GEMM两侧149/步，目标逻辑12/步；原生直接_sgemm baseline149、candidate161（目标12个整矩阵各变2块、24个native tile）。新runtime_counts同时核逻辑、target和原生计数；实际导入路径/SHA、native签名频数、dispatch命中记录到result/steps，原149不伪装成全部原生调用。恢复小批K416不触发分块。不能把这些计数说成Torch内部全部BLAS调用。

严格门槛两侧各5+性能两侧各25，最多60次完整模型更新、1对性能运行，不做ABBA/多seed/多tile/其它shape搜索。拟单节点单NUMA38分配/实际36、留2、DDR24576MB同limit/exclusive、HBM0、最多900秒，整个链共享840+清理30+收尾30。每入口720秒停新步只是后备，不是各占900秒；S00外层总截止优先。资源或预算不足INCOMPLETE，不缩到5步或扩限/续跑/重提。

原完整模型、fp32/CKPT0/native SDPA、mean双loss、AdamW超参数、KML/OMP36/MKL36/OpenBLAS1/cores/close及原CPU36全部TID守卫保持，不设置interop。新账本位于每阶段outputs，不写旧descriptor runtime ledger/checkpoint。统计所用及训练消费暴露分别保留，subject/split UNKNOWN，无正式val/test或效果结论。

收集target/strict/perf两侧结果、全部逐步loss/frames/masks/CPU/库/导入/native计数与状态、退出/超时/调度/清理、暴露清单及远端checkpoint身份/零更新恢复。权重留远端，数据/权重/ZIP/环境不进Git。内存仅比较独立性能进程中同范围的RSS/采样process-lifetime HWM，不是逐步独占或全job最终峰值。

## 价值判据

只在真实目标和完整strict5均过、同节点/同库/同源/同配置身份一致、baseline/candidate都完成25次后，比较后20步训练调用的中位/范围/波动和同范围内存，并列出wall、诊断/数据/账本/保存恢复等分项。首次5步损失保留旧原件门槛，后20步保留有限性/状态检查和真实loss；不把短训练loss当泛化，不将局部GEMM加速替代训练步收益，不拿旧跨job的诊断时长作对照。

完整K不保证KML因N变化仍逐位相同，也可能重复打包/多一次调用更慢；真实KML首次失败或无同机训练收益就关闭本固定候选，不改阈值/块宽/精度另搜。本轮实际KML/完整Encoder/A/B均未运行，本地native替身通过仅为数学/ABI筛选。
