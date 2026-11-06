# 首次真实双域Encoder DDP固定约定

本轮约定来源为COORDINATION/REAL_DUAL_DOMAIN_DDP_START_20261106.md，具体SHA见SOURCE_MANIFEST及TRAINING_READY。S07只交候选与证据，不提交job。S00须等S01对同一具体版本的最终审核；本地数值FAIL不可省略或当PASS。

每域32/全局64，原1600帧25批，各批前32/后32分rank，并集恰为原64。原descriptor/manifest/engineering INTERFACE锚点不刷新；subject/split UNKNOWN，无val/test。S02参考包唯一SHA由reference_binding.json绑定，全部18内包文件校验，原loader/归一化及25批frame/mask哈希保留。原37995777参数Encoder及head_v/head_coarse，无解码器训练；fp32/KML/native SDPA/CKPT0，不加载R12 candidate，不集成R10/R12/bf16/compile/HBM。

DDP forward包含原Encoder、两个head和两个平方和。跨rank SUM统计masked/coarse各自元素数；反向为2×(局部电压平方和/全局masked数+局部coarse平方和/全局coarse元素数)，分母/日志collective脱离梯度。局部零mask用可微空sum，全局零分母失败，无重采样/epsilon。日志为全局sum/全局分母。默认DDP已平均参数梯度，不能再除2；原S02 compare只把输入梯度除2。

原AdamW lr1e-4/betas(.9,.999)/eps1e-8/weight_decay.01；无累积、scheduler或混合精度。每rank完整覆盖相同原参数、所有梯度有限；每步按canonical原名/shape/dtype/张量字节hash核两rank模型及AdamW一致，另核step/cursor。DDP固定25MiB bucket、默认reducer，无hook/no_sync/join，详见API_REVIEW。

每rank原seed0初始化后复制post-init Torch RNG到S02独立mask流，不重seed产生mask；DDP构造/额外参考初始化/恢复probe不能影响该流。前5步rank0保留原完整B64参考/AdamW，连续配对输出h/v/coarse、loss分量/total、两输入梯度、全部参数梯度/更新参数/初始delta、AdamW step/一二矩及buffers；比较器原字节/类别/阈值不变。rank1在每个gate广播前不得开始下一更新；rank0失败由父及时清理双方。五门槛全过才以同一DDP/AdamW接着6—25步，step5后释放参考及当前快照。

上限25全局更新/两rank50物理更新/额外5 B64参考更新=55；独特训练1600帧与参考额外320观察分开。每rank独立训练exposure ledger，rank0另建reference ledger；失败时保留in_flight及reference_updates_attempted，不补造已完成更新。恢复probe重用最后已训练32帧，每模型前向一次，不新增optimizer更新或训练独特帧。

最终远端各rank保存canonical原Encoder、AdamW、Torch/Python/NumPy RNG、独立mask RNG/游标、epoch顺序/进度/归一化/数据与源身份，回传仅checkpoint_index的路径/bytes/SHA。恢复核原状态逐字节、独立mask状态、游标、身份、前向原compare及零额外optimizer更新。完整/部分.pt及.pt.tmp留远端，不下载权重。

| rank | 当前授权边界 | 实际允许核 | 预留 |
|---|---|---|---|
| 0 | 原生当前job第一38物理核域D0 | sorted(D0)前36；每个相关TID非空mask属于selected36 | 域末2核不用 |
| 1 | 同节点另一不相交38物理核域D1 | sorted(D1)前36；每个相关TID非空mask属于selected36 | 域末2核不用 |

总76/72/4，DDR总24576MB且limit相同/exclusive/HBM0。CPU号只取当前授权/拓扑，不复制历史job。OMP36/MKL36/OpenBLAS1/cores/close，实际Torch intra-op36；原生CCS_JOB_ID在启动worker前及各worker导入Torch前校验。双方导入、库/KML/CPU36及初始化准备就绪后才建PG。配置不够则停，不缩批/扩资源。

单job同一起点900秒，所有前置/本地方法现场核/应用共同840秒截止，清理至870、收尾至900，不重置阶段预算；训练PG固定120秒，剩余外层预算优先。父仅signal自己创建的两个session，TERM后有界KILL/poll回收，缺失/空/残/旧身份正式rank报告拒绝。原R7小组件复制未改；R7本身pg5/case30及历史失败不动。无重试/补跑/新增训练故障注入或延长预算。

训练每步计forward、含DDP同步的backward、optimizer、分母/状态collective、参考等待/诊断、RSS与lifetime HWM；rank0 HWM包含参考共存，不能称纯DDP峰值。原生DDP采样/平均时间字段原样保留。S08可据两rank取最慢值及分别汇总前5/后20；无同job单域对照，speedup/扩展效率均NOT_MEASURED。训练候选、通信、数值、恢复、训练完成与性能接受分开。
