# S02 R10：唯一fp32线性反向视图复用候选

2026-11-06，Asia/Shanghai；LOCAL_NATIVE_INTERFACE_PASS，实际KML/完整Encoder严格验证和A/B待执行。仅本轮S02任务，不提交集群、不默认集成，不接回bf16/checkpoint/HBM/compile/decoder搜索。

## 从真实R9对应到代码

只读核job2048959/cn21338的RUN_COMPLETE、其绑定的result/steps/audit/3events/3trace/profile contract/reference（11份bytes/SHA）及协调复核JSON。没有SSH、NPZ或权重读取。R9后3采样forward_loss/backward/optimizer阶段wall中位1.515943/3.480861/0.173312秒；KML包裹每次149调用，copy_1003次。不能与旧cn21341的2.33秒作性能对照，不能称KML包裹为精确内核时间，也没有逐调用矩阵shape/stride定位。

本轮针对_LinearFn父子事件核三份trace：每步50次前向、50次反向。前向bias expand→contiguous→clone/copy为50次，输入reshape→clone/copy为12次；反向100次reshape均无clone子事件，反向该函数内没有观测到copy_。因此大量copy_不能全部归KML，更不能把删除to(fp32)/contiguous空操作当搬运收益。weights当前普通连续fp32时to/contiguous通常直接返回同一Tensor；reshape是否复制由输入stride决定。原代码bias展开后materialize是实际写出C，后续gemm(out=y)复用它，没有第二个C分配。

关键结论：当前没有证据支持安全删除前向12次QKV相关布局复制或50次bias预填。改变行序牵动dW归约，后加bias会改变舍入/beta使用；两者本轮均未实现。编码前取舍见DECISION_BEFORE_CODE.md，原始对应见evidence/PROFILE_CODE_MAPPING.json。采样中第二次反向reshape事件合计约1.79—1.86ms/步，含profiler扰动，不能当无profiler可省时间。

## 唯一候选与风险

只在LINEAR_DTYPE和gy.dtype均为fp32时，把第一次gy.reshape结果保存在局部gy2；g仍沿原to/contiguous路径供GEMM使用；gb沿gy2原dtype/stride归约。没有改forward、GEMM alpha/beta/ta/tb、bias顺序、模型/loss/AdamW/精度/attention/线程/数据/门槛。非fp32走原分支。补丁只有1行新增、2行替换：E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S02\round10_linear_reuse_20261106T034306Z\diff\CANDIDATE_ONLY.patch。

不能直接改成g.sum：如果原flatten结果是非连续2D view，g.contiguous会改变归约布局。gy2复用原flatten结果，保持原sum布局；若flatten本就复制，才有可能省第二次复制，但这不属于R9已观测反向路径。R9中只减少50次重复视图构造，**未证明任何矩阵复制减少，不能称解决copy热点或有实质性能收益**。候选很小、预期收益空间有限；协调可据此选择不安排A/B并关闭，不另找第二候选。

alias前提是KML只读A/B且输出不与操作数共享存储。gy2没有跨调用/跨步缓存；没有缓存会被AdamW更新的权重或复用autograd持有的输出。若真实KML写输入或数值越门槛，保留失败并关闭这一个候选，不放宽、不转选其它方案。

## 已完成必要本地检查

7项通过：4项线性native替身检查覆盖相关特征512/1536/2048、实际13312行embedding/head及416行QKV/FFN计算、B64 contiguous/sequence-batch swap/feature-slice/padded-row布局与bias归约、bias有无/输入及权重梯度开关、GEMM输入不变和输出不alias、重复调用及连续5次原AdamW；3项A/B夹具验证完整参数梯度/delta/状态比较、失配或缺梯度拒绝、receipt源码/数据/node/job/selected36绑定，以及候选计数函数与冻结KML shape诊断AST一致。原冻结比较器未改，115项数值metrics全部通过/max_abs=0。并非本地执行了全部13312行QKV/FFN的全矩阵/全模型验证。

实际导入路径/SHA见evidence/linear_metrics.json；baseline SHA=e6c5c4411c453c8168939cd51d737a7e9d8232bdfff05da3967805a5e917ff26；candidate SHA=27646c0df40b1dd02d3f27c931e0e72d5e7ec9fea2c7eba2c5beaf76d0553f44。本地_lib=None，检查直接用_LinearFn.apply的native gemm替身，不能称实际KML数值通过。额外2种预期CLI平台/路径拒绝在框架/模型之前停止，属于拒绝分支验证，不是候选数值FAIL。Python3.9 AST/LF/Git Bash -n、14份冻结复用文件和R9原件SHA、ZIP逐文件SHA通过。C2 full runner仅做必要小夹具/静态检查，真实完整运行未验收。

## 有限同节点A/B提案与停止

详见E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S02\round10_linear_reuse_20261106T034306Z\AB_PROPOSAL.md，附实际可审阅入口screen_linear.py、train_linear_ab.py、run_ab_proposal.sh。顺序必须为实际KML局部筛选→完整Encoder5步严格A/B→同一新节点/job内分别新进程baseline/candidate性能5步（2预热/后3观察），全程无profiler；某阶段失败则后续不运行。严格门槛沿原tensor/state/exact比较，涵盖输出、loss、输入/参数梯度、参数/delta和AdamW状态。perf receipt绑定同源码/descriptor/host/job/selected36，不允许用旧跨节点结果放行。

原完整Encoder37995777/fp32/CKPT0/mean双loss/AdamW、同1600帧工程统计和原前320帧/seed0/mask/库/CPU36路径保持。性能两侧同样计数/shape日志/CPU/有限性/暴露检查和保存/恢复，不删诊断；diagnostic、mask/账本、读取/批物化、保存恢复、比较及未归属时间单列。独立进程RSS/HWM仍是process-lifetime采样，不是逐步独占或整个job最终峰值。只是一对3样本探索，不构成稳态/生产加速接受。

拟单NUMA38分配/实际36、24GiB请求同limit/exclusive、最多900秒整个链；840全入口+清理30+收尾30，任一入口720秒后停新步。最多完整Encoder20次更新，1对性能A/B，无ABBA/矩阵/重试。数值、来源、CPU/KML、内存、超时或输出冲突即停；资源不够不扩限、不改拆批。本包不替代S00新原生调度/资源/唯一marker/后代清理复核，旧授权已消耗，须协调后另派01/00。

## 冻结交付与尚存边界

包：E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S02\round10_linear_reuse_20261106T034306Z\package\S02_R10_LINEAR_VIEW_REUSE.zip；65631bytes/24文件；SHA256=e5cd839c95560f1cd5bd613b01018d590791f3e8bd51a24f98a336a72326f809。
SOURCE_SHA256.json SHA256=bf0dca30aececca6ced8f0d2fcb2b0e8116e4883b38e8fdb7e122a1f532280b4。
包清单package/PACKAGE_MANIFEST.json；就绪索引R10_READY.json；本地证据evidence/local_validation.json、native_final.log、ab_contract_final.log及导入/布局metrics。

本轮实际KML数值0、完整Encoder0、同节点A/B0、新job0。主要实质待验证：真实KML输入只读/数值及完整5步严格门槛；候选极小且未证明矩阵搬运节省，是否值得A/B由协调判断。原工程/R9源码/包/正式门禁/历史失败及checkpoint可选结案不变；正式subject/split仍UNKNOWN，无val/test或科学接受。归档候选精确列ARCHIVE_FILES.json，排除ZIP/数据/权重/环境；不操作共享Git暂存/提交/推送。
