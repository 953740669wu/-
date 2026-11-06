# S00 夜间真实语料工程小试：唯一2043445成功终态

2026-11-06（Asia/Shanghai），任务卡/目录沿用20261105。
`ENGINEERING_PILOT_COMPLETE_NOT_SCIENTIFIC_ACCEPTANCE`；job2043445/cn21341 SUCCEEDED/exit0，
1epoch、25次AdamW更新、1600真实帧完成。无重试，无活动S00 job，未重提05/07。
已发布RUN_COMPLETE.json，供S01/S08直接读取本轮唯一原始证据与索引。

## 冻结输入、来源和放行

原正式REALDATA_SOURCE_AUDIT.json仍DATA_NOT_READY，旧正式门禁未改。
本次按用户新授权，仅工程采用14300版manifest，SHA
`bdd146040bddf2ddd47fb9d571d5d2f40e5fa20fbd30d0c0d11239893e647032`，读取前后及训练结束保持一致。
case不是subject；formal_split_status和subject_mapping_status均UNKNOWN，
validation_status=NOT_RUN_NO_FORMAL_SPLIT，未创建/使用正式val/test或伪造subject映射。

seed2026从原119-case工程范围确定s0285和s0593各8个16_adjacent单元，共16单元/1600帧。
原cases.txt仅限制工程选样范围；manifest未替换/过滤成另一个版本。
NPZ/同stem sidecar逐文件bytes/SHA/前后读取一致；schema、dtype、finite、
有序drives/meas、base_of_pair/states同row和正有限参考分母检查全部通过。
所有电压与images均取同belt/unit/row，无旧demo/跨belt目标复用。
image absmax=0.03546142578125，只从固定工程训练单元拟合一次。

S02接口先发布并保持不变；00按接口发布DATA_READY.json。
冻结前的描述文件环境变量接线问题已纠正，实际S02 ZIP入口参与的模拟传递检查通过。
本地12项、C2登录侧12项包装检查、LF/AST3.9/Linux bash-n、解包SHA及
真实ENGINEERING_METADATA_HASH_GATE_PASS完成，登录节点未运行模型。

S01在16:03:21UTC发布完整PASS_FOR_ENGINEERING_PILOT，review_complete=true；
S00再次核对完整审核原件、所有绑定SHA、原包/manifest、实际队列、原目录marker及所有部署源。
S01原件SHA=`da7e84289a905466bc5bfdaa1e9cf7a1b80c41ace0cfaae63488d11ae8f6e408`。

| 具体交付 | SHA256 |
|---|---|
| S02代码包，71182bytes | add690cf983d5902c78586101ee6250358380786a8c13aa209b0a024735835a7 |
| S02源码清单 | e4acbbcb604dc3afd22b462bbfc2c3e348108c32e004557b891de7e14978b7d2 |
| S00部署包，135582bytes/27条目 | 938f7df81f3f7fa8c61239f8041950e4eb47043e869bbbd5aad7be8e6d27359e |
| descriptor | b88ea9745147acf7fa70d51dc27c727f22f14e98af5dff1b80a9047e95648cd6 |
| 接口 | 8b1b540b8adeb4f4e49233c262b113c7c437f7a6e30b9f6d13113a96891dc669 |

## 实际执行与边界

单节点单NUMA，38物理核授权/前36实际/末2预留，DDR24576MB同limit、exclusive、HBM0，
job900/全入口840/统一后代清理30/留30收尾；原生job、nonce/raw/ready、主机及sysfs/DDR核验通过。
只调用一次dsub，maxRetryCnt/currentRetryTimes均0；用户其它任务未取消/修改/借用。

完整Encoder 37995777参数，fp32/CKPT0、既有KML linear和native SDPA；
原mean双loss、AdamW lr1e-4/betas0.9,0.999/eps1e-8/decay0.01不变。
无decoder/微批/bf16/compile/HBM/新attention；未更改旧数值阈值或其它候选。

- 25个batch各64帧，cursor64→1600、AdamW步号1→25连续，1epoch结束。
- 1600个实际frame索引恰好覆盖0..1599；按unit/pair_index也无重复或填充，
  每帧NPZ/sidecar SHA、case/placement/contact/belt/row/baseline与固定描述一致。
- 25个mask SHA各不相同，mask非空，逐步两个分量与total均finite。
- 59次完整CPU快照无错误，所有已采样TID均在selected0..35内，最多观察到36个TID。
  实际Torch intraop36、interop608是未加setter的现场观察值；interop设置值不等于实际活跃线程数。
  这是完整TID快照证据，不宣称连续线程监控。
- 训练步实际KML调用3725次；含恢复前向等的进程记录3823次，实际加载库路径/SHA及OMP记录均保留。
- initial/runtime暴露清单分别保存；runtime25个confirmed_updates逐帧等于steps原件，
  无in_flight，16单元均CONSUMED_CONFIRMED，恢复探针另有记录。
  后续必须解析真实subject映射并排除工程暴露subject进入最终test，当前不保证未触碰未知测试对象。

## 观察值与checkpoint

| 记录 | 本次值 |
|---|---:|
| 进程wall | 86.6905秒 |
| 所有训练step合计 | 58.4772秒 |
| step中位数/范围 | 2.32994 / 2.24288—2.83040秒 |
| 数据读取/批物化 | 0.9140 / 0.0223秒 |
| 诊断/暴露/状态检查已区分部分 | 6.8429秒 |
| 保存与恢复核验 | 4.0923秒 |
| 未归属setup/logging等 | 16.3418秒 |
| 逐步采样中的进程生命周期HWM最大记录 | 7258705920bytes，约6.76GiB |
| 原调度起止/usage | 96节点秒 / 95秒，分别记账 |

RSS/HWM是进程生命周期量的逐步采样，不是单步独占内存，也不替代保存/恢复后的全job峰值。
上述计时包含各自所注明的开销，只是单次工程运行，不能据此给稳态性能、候选加速或优化收益结论。
首/末batch的total为15.21107/5.69206；两batch不同，记录训练波动，不把下降当质量/泛化接受。

checkpoint仍在远端：
`/home/share/dengqingtian/opt/stage4_sessions/S00/ENGINEERING_PILOT_20261105T154333Z/payload/outputs/engineering_2043445/checkpoints/final.pt`

456135327bytes，SHA256=`ec491c46c06f94a7fac54d5f80010866311743e1f722947cb680cdaf3579e403`。
模型/AdamW/RNG/cursor/身份精确恢复，固定前向h/voltage/coarse差异均0，extra_updates=0；
未自动续训，未下载/加载权重进行额外更新。

## 终态与交接原件

UTC16:06:18—16:07:54（中国时间00:06:18—00:07:54）。所有所属后代自然退出，
原生subreaper/后代身份追踪已运行；cleanup all_reaped=true、remaining_live/processes均空，调度pids='-'。
本次无需发TERM/KILL，**未现场触发信号故障清理分支**，不能把12项模拟检查说成真实故障注入。

证据包evidence/JOB_2043445_evidence.zip：543118bytes/102文件，SHA256
`53feb1041cc17472d8ec6777ec8ec64e2d8fd4a286a518be42f2d49298e82b00`。
全部归档原件bytes/SHA与COLLECTION_S00.json的远端mtime_ns索引一致，missing=[]、source_status=UNCHANGED。
checkpoint只回传路径/bytes/SHA及恢复证据，权重仍远端保留；数据/权重未进Git。
RUN_AUDIT.json及audit_completed_run.py仅只读原JSON/原字节核查，没有重跑模型。

RUN_COMPLETE.json已绑定本地received目录、原始索引SHA、analysis_inputs，S08无需用户转发即可整理。
原正式门禁及旧05/07包/失败保留；精确待归档名单见ARCHIVE_FILES.txt，不操作共享Git暂存/提交推送。
