# S00 R9五步CPU剖析：唯一2048959成功终态

2026-11-06（Asia/Shanghai）。新job2048959/cn21338 SUCCEEDED/exit0，
PROFILE5_COMPLETE_NOT_PERFORMANCE_ACCEPTANCE；仅5次连续更新/320帧，前2预热、后3采样。
无重试、无活动S00 job，完整交接已发布RUN_COMPLETE.json。

## 身份、授权与独立部署

新根 `/home/share/dengqingtian/opt/stage4_sessions/S00/S02_PROFILE5_20261106T030149Z`，
新包/marker/输出均独立；不复用2043445的执行授权、marker或输出。
两次SSH连接超时后用户确认入口恢复，新入口指纹按此前对该C2入口所有指纹的明确持续信任另存，
旧记录保留，严格校验仍启用；见evidence/HOST_KEY_CONTINUITY.json。

恢复后实际只读查当前队列、R9提交/marker，未发现已有本轮job；其它用户作业不动。
原manifest、descriptor、旧runtime ledger及checkpoint前后SHA一致。
全部固定16单元/1600帧仍用于原工程scale，实际训练仅同seed0前320帧，不另选数据，
不读旧checkpoint，不改变完整Encoder、fp32/CKPT0/KML/native SDPA、mean双loss及AdamW。

S00新协议针对性标准库夹具8项本地、8项Linux登录侧通过；
LF/AST3.9/bash-n/25成员ZIP/24项源SHA及真实descriptor metadata gate通过。
未在登录节点运行模型或profiler，也未重复旧完整runner检查/模型矩阵。

S01于03:19:04UTC发布完整PASS_FOR_ENGINEERING_PROFILE5，review_complete=true，
审核原件SHA=`596b45e77308f5aca05799a5a613d43048e294f9db70411069ca3e2135a6a5da`。
提交前八份实物SHA、审核原件、实际队列和唯一marker再次核对；一次dsub/原生授权交接完成。

| 实物 | SHA256 |
|---|---|
| 原02 R9代码ZIP，69674bytes/25成员 | 15621eaa3328e407059c352d86a0f49ee68bfea39f02a68503ded6f94099abe3 |
| 原02源码清单 | 2a86fd01cab96a85cb2f0f4c8ed998edb956ef81255dfd5ceb950d41264de741 |
| 新S00部署ZIP，125441bytes/27条目 | e73c3def84745ce62981c0f17f097d3d8bd3aa270423083e32e49700116c96ee |
| 新S00部署索引 | 0b632e9ebb238317346ac7f74682d8f7f66f9ac0ec78cd8c1a446a5d9a43abc9 |
| 原descriptor | b88ea9745147acf7fa70d51dc27c727f22f14e98af5dff1b80a9047e95648cd6 |
| 原interface | 8b1b540b8adeb4f4e49233c262b113c7c437f7a6e30b9f6d13113a96891dc669 |
| PROFILE_CONTRACT | 35878e1bfff4fab8f85ad84b540d927570fb09858e300ba664e605080fc8c978 |
| REFERENCE_FIRST5 | 2c901021046e0c8ba8adf5a3d461a40fa2a61413bc4c39db8929b840e675e5f8 |

## 实际五步/采样/数值证据

38物理核授权、实际selected36/预留2，单节点单NUMA、DDR24576MB同limit/exclusive/HBM0；
job900、全入口840、清理30、收尾30、内部720秒停止新更新均保持。
实际达到5步即停，未延长为完整epoch或跑满900秒，重试计数0。

- 原初始化权重、scale、固定单元身份和前5步frame顺序/ID SHA/mask SHA与2043445参照一致。
- AdamW1..5连续、每步64帧、cursor64..320，无重复或填充；5个mask按原参照变化。
- 原比较器下5步×3项loss共15/15通过，max_abs和relative L2均0。
  这是本卡要求的loss回放及身份核验，不挪作完整旧5315项梯度/参数跨实现证明。
- 所有原阶段事件、KML包裹和文件齐备；8MiB/1MiB文件上限、50000事件/256标记单次上限均未触发。

| 步 | 用途 | CPU事件 | KML包裹 | trace bytes | events bytes |
|---:|---|---:|---:|---:|---:|
| 1 | 预热，无采样 | — | 0 | — | — |
| 2 | 预热，无采样 | — | 0 | — | — |
| 3 | CPU采样 | 10845 | 149 | 1533488 | 9122 |
| 4 | CPU采样 | 10845 | 149 | 1556905 | 9119 |
| 5 | CPU采样 | 10845 | 149 | 1555946 | 9120 |

6份采样总4673700bytes；每份原bytes/SHA与result记录及收集索引一致，没有截断或丢弃。
trace保留CPU时间区间、线程及父事件ID；events保留至多80个self CPU key和嵌套total。
每步事件上限在捕获结束检查，不声称采集中实时截断或覆盖全部OS线程CPU消耗。

## 时间与观测边界

| 步 | forward_loss wall秒 | backward wall秒 | optimizer wall秒 |
|---:|---:|---:|---:|
| 1（预热） | 1.691317 | 3.348911 | 0.157520 |
| 2（预热） | 1.532610 | 3.010924 | 0.141917 |
| 3（采样） | 1.571089 | 3.480861 | 0.173312 |
| 4（采样） | 1.515943 | 3.485786 | 0.173939 |
| 5（采样） | 1.400948 | 3.171818 | 0.172542 |

完整原phase_seconds还包含两次zero_grad。上述是带原标记的wall观察，
KML包裹含Python/计数/分配/ctypes/native，不称精确KML内核时间。
嵌套inclusive不相加、self与total不重复相加、跨线程CPU和不直接除wall作占比。

应用wall82.124880秒；训练调用内25.088423、独立profiler setup/stop/export外层开销16.014551、
诊断2.180670、读取1.084086、批物化0.005013、保存恢复7.453861、其余30.298275秒。
采集内部事件/标记扰动仍包含在step内，不能由本次无配对控制精确扣除；
不能把预热步当性能对照，不能用不同节点旧25步给加速百分比，也不称三步稳态吞吐或收益。
RSS原件仍为process-lifetime HWM采样，不作本轮训练内存/全job最终峰值验收。

19次完整TID快照均在selected36内，无CPU守卫错误；最多观察到37个TID（含剖析相关线程），
不是37个物理核。实际Torch intra36/interop608为未加setter的观察值。
训练KML调用745次、进程含恢复前向843次；库路径/SHA及OMP原件齐全。
这些CPU36证据是完整快照，不宣称连续监控或profiler事件覆盖所有工作线程。

## 暴露、恢复、终态与原件

新账本只写 `payload/outputs/profile_2048959/EXPOSURE_LEDGER.json`；
5个confirmed_updates逐帧等于steps原件，in_flight=null；全部1600帧用于工程统计的暴露语义保留，
恢复探针单列且extra_updates=0。无正式split/subject映射/val/test；
未来仍须将两case实际subject追溯排除最终test，不能保证未知测试对象未暴露。

新checkpoint仅留远端：
`/home/share/dengqingtian/opt/stage4_sessions/S00/S02_PROFILE5_20261106T030149Z/payload/outputs/profile_2048959/checkpoints/final.pt`

456134879bytes，SHA=`2d7dfb1ac8846f4101107924d7f4810b142285dd831b55628d55d686b6e6e64a`。
模型/AdamW/RNG/cursor/身份精确恢复，固定前向h/voltage/coarse差0，额外optimizer更新0。
checkpoint沿用未改工程保存协议，result以独立PROFILE5协议绑定本包源码/配置；不是复用旧权重。

UTC03:21:22—03:22:56（中国时间11:21:22—11:22:56），起止94节点秒、usage93秒分别记账。
所属进程自然退出，all_reaped=true、remaining_live/processes为空，调度PID清空。
本次未触发TERM/KILL故障分支，不能把本地mock或自然退出说成现场信号故障注入已验。

证据包 `evidence/JOB_2048959_evidence.zip`：1066705bytes/105文件，SHA
`bb17a1ff559ffe328ae95f23db9f3126158a771052e3350ef435166755a88f5c`。
所有归档bytes/SHA及原始远端mtime_ns索引核验通过，missing=[]、source_status=UNCHANGED；
原manifest/descriptor、旧runtime ledger和旧checkpoint的前后SHA完全不变，见OLD_INPUTS_AFTER.sha256。
权重未下载，原正式审计和旧结果保留，不操作Git暂存/提交推送。
RUN_COMPLETE.json已绑定原始目录、索引及6份采样SHA，供01/02/协调直接读取，后续按本轮新证据定向分析。
