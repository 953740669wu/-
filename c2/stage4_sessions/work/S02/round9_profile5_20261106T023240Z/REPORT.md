# S02 R9：已有耗时分析与有限剖析包

2026-11-06（Asia/Shanghai）。仅完成AFTER_ENGINEERING_PILOT_20261106任务卡S02节；没有新集群提交、环境安装或生产默认变更。原activation checkpoint候选维持结案。

## 先看已有证据

只读核RUN_COMPLETE绑定的7份原件bytes/SHA、原25行steps及result、RUN_AUDIT和协调运行复核JSON；未SSH实查、未下载权重、未读取NPZ或重跑模型。唯一基线job2043445/cn21341：工程成功、25次连续AdamW/1600帧；程序计时86.690500秒，调度96节点秒另计，不相加。详细身份及重新求和见evidence/BASELINE_TIMING.json、local_validation.json。这里只继承已收原件所能证明的工程结果，不扩大科学/性能验收。

| 原记录范围 | 秒 | 程序wall占比 |
|---|---:|---:|
| 训练步骤合计 | 58.477237 | 67.46% |
| 可区分逐步诊断 | 6.842871 | 7.89% |
| 保存/恢复范围 | 4.092292 | 4.72% |
| 数据读取/归一化范围 | 0.914007 | 1.05% |
| 批物化 | 0.022267 | 0.03% |
| 未归属范围 | 16.341825 | 18.85% |

训练中位2.329944秒，首两步2.830396/2.355097秒；这些只是已记录不同batch的时间，不推导稳态或退化。读取范围含train归一化和加载暴露写入；诊断含mask/更新前账本、CPU前后快照、参数/梯度/AdamW检查；保存恢复范围含其CPU/账本检查，均不称纯I/O或纯内核时间。未归属16.341825秒可能分布在原源码中的框架/库导入、源/数据哈希、模型初始化和权重哈希、其它CPU检查及日志/账本确认等段；这些子段没有独立计时，不能分摊到某一项。程序计时亦不包含末尾最终JSON写出、包装及调度全部开销。

目前attention、KML linear、其它反向和AdamW各占多少均未知；没有operator trace，不把历史233帧/s或其它不同范围数字拿来计算退化/加速。interop=608只是原getter观察值，原59次快照最多36个TID，不能推断实际启动608线程，也不据此调默认。

## 下一项优化应先看哪里

1. **训练路径优先**：67.46%是最大已测范围；先取得forward/loss、backward、optimizer及zero_grad相邻阶段壁钟，再看后3步CPU事件。attention和KML线性/布局/分配、其它反向、AdamW是同级待分辨候选，目前没有证据给它们内部排序。若native SDPA事件突出，再考虑attention路径；若KML包裹突出，再查linear布局/分配/调用边界；若optimizer阶段突出，再查AdamW算子。均须先有本包真实剖析，不先改算法。
2. **启动/未归属范围其次**：18.85%具有工程排查价值，但尚未细分，不能宣称某项导入/哈希慢。本轮不为凑比例删来源门禁。
3. **保留诊断的开销可审视**：7.89%已有边界，不能通过删检查制造提速；日志/账本与快照的后续优化仍需保持证据功能并另作对照。
4. **批物化和读取优先级较低**：本记录合计约1.08%；保存恢复范围4.72%另计。本轮不开展缓存/归一化算法/保存算法或activation checkpoint搜索。

## 本包的最小变化

16份复用文件与冻结工程包字节一致，包括完整Encoder/KML、loss/AdamW/保存恢复、配对/工程门禁、CPU36守卫、运行环境和原阈值比较器。原冻结入口及包没有改动。新train_profile5.py从该入口仅加入固定5步/身份/剖析控制，新profile_probe.py按原表达式及操作顺序给阶段计时/CPU事件；新profile_contract.py绑定原1600帧和前5步参考。最小diff为E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S02\round9_profile5_20261106T023240Z\diff\FROZEN_TO_PROFILE5.patch。原数据/诊断/CPU/KML/保存恢复不删除，不改线程/interop默认。

B64、seed0、前5次连续更新，无重置AdamW、无样本补尾；1—2预热，3—5各采样1次。逐步核原frame顺序/ID哈希、mask/初始权重/归一化/实际KML计数，loss沿用原比较器阈值。读取仍为原1600工程帧，训练确认消费320帧，暴露记录区分加载用于统计和实际消费；旧descriptor/runtime ledger路径只读，新运行账本在新profile_JOB目录。checkpoint算法及工程标签不变，identity绑定新profile源码/配置，恢复额外更新0。

CPU profiler只使用已装Torch能力，缺失则UNSUPPORTED_PROFILER停止。每次最多50000事件（单次采集结束后查上限）；最多256个KML标记、3份<=8MiB trace、3份<=1MiB摘要，trace+摘要总上限27MiB，超限不截断/不重试。现有API无法逐事件硬取消采集，完整采集受单步及整体时限约束，此限制在PROFILE_CONTRACT.json明确记录。raw trace保留父事件/线程ID，摘要最多80个self CPU key；不相加嵌套total或把CPU事件合计当wall占比。

KML标记只说明Python/counter/分配/ctypes/native调用包裹，**不是精确原生内核时间**。profiler setup/start/stop/后处理导出单列，训练内部事件/标记扰动保留在step_seconds且无法凭此次采样精确扣除；全profiler调用wall另记，不能把采样速度当正式吞吐。CPU事件也不是操作系统进程CPU消耗或完整worker采样保证。

## 本地验证和交付身份

6项小型native Torch36夹具检查通过：连续5步对原函数loss/参数/AdamW逐项完全一致、RNG仅由同样mask推进、前2无采集后3各一份trace、五步checkpoint零额外更新恢复；另核能力缺失、CPU阶段事件缺失、乱序、固定身份漂移、KML标记委托/恢复及事件/文件上限拒绝。3种CLI拒绝（缺描述、正式协议混入、B32）在框架前生效；源码Python3.9 AST/LF、Git Bash -n、16文件冻结SHA、7份基线原件SHA及前5参考身份通过。测试没有完整Encoder或实际KML；数值精确一致仅限本地小夹具，不能扩展为C2完整模型已验证。

代码包：E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S02\round9_profile5_20261106T023240Z\package\S02_R9_PROFILE5_CODE.zip
bytes=69674；files=25；SHA256=15621eaa3328e407059c352d86a0f49ee68bfea39f02a68503ded6f94099abe3。
SOURCE_SHA256.json SHA256=2a86fd01cab96a85cb2f0f4c8ed998edb956ef81255dfd5ceb950d41264de741。
ZIP逐项内容核SHA通过，清单package/PACKAGE_MANIFEST.json；实际检查evidence/local_validation.json及日志。

## 未运行与下一步

本轮真实NPZ读取0、完整Encoder执行0、C2/KML剖析0、新job0；attention/linear/backward/optimizer热点仍未知，无性能或泛化结论。拟资源仅下一轮单NUMA38/实际36、24GiB请求同limit/exclusive、最多900秒，入口840+清理30+收尾30，720秒停止新更新、5更新完成即停。源/CPU/KML/数值/能力/采样限额/输出冲突/超时异常即停，不重试、不扩样/资源；无HBM/bf16/compile/decoder搜索，正式门禁不变。

命令、收集和停止条件见E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S02\round9_profile5_20261106T023240Z\README.md及PROFILE_CONTRACT.json。先交协调复核，再另派S01绑定本包具体SHA审核和S00新部署/唯一marker；**旧900秒唯一作业授权已消耗，本包没有新执行授权**。S02无活动job，不查询或猜测其它远端任务。精确可Git归档清单ARCHIVE_FILES.json排除ZIP、真实数据、权重和环境；ZIP作为独立交付保留。没有操作共享Git暂存或提交推送。
