# R10编码前选择（仅一个候选）

已核R9 job2048959绑定的result/steps/3events/3trace和源码SHA。三份trace各50个_LinearFn、50个_LinearFnBackward：前向50次bias expand→contiguous→clone/copy，12次输入reshape→clone/copy；反向100次reshape没有clone子事件。采样无逐调用shape/stride，不能精确指出最大矩阵。KML包裹不是精确原生内核。

可选局部改法与取舍：

1. bias预填改成GEMM后加bias：改变加法/舍入顺序和beta使用，且总读写并未自然减少；本轮不选。
2. 按物理batch/sequence布局直接做QKV以免前向12次复制：会牵动输出布局、反向转换和dW归约行序，超出安全的小改点；本轮不选。
3. 复用反向第一次reshape的原dtype/stride结果计算gb：仅局部变量，不改GEMM alpha/beta/转置、gb归约布局或顺序，不缓存权重/输出。这是本轮唯一实现。

收益限制：R9的两次反向reshape都是view，没有证据可省矩阵复制。候选只省50次重复视图构造；三份带profiler第二次reshape事件合计约1.79—1.86ms/步，该仪器化事件时间不能当无profiler收益估计。不能称解决copy_热点，也不预设有实质加速。若协调只接受能消除已观测大复制的改动，本轮证据支持“当前未找到满足约束的安全小点”，不升级成其它候选。

数值/alias风险：必须复用原flatten结果gy2，不能改成一律g.sum，因为contiguous可能改变原非连续2D的归约布局。复用期间假定BLAS不修改A/B且输出不alias输入；将核GEMM输入不变、输出/重复调用不共享存储、contiguous/转置/feature slice/padded row/broadcast梯度、bias及输入/权重梯度开关、连续AdamW状态。非fp32保持原分支，不开展bf16试验。保留原比较器/门槛；首次实际数值筛选失败即保留失败关闭本候选，不改阈值或转选其它方案。

本地没有实际KML；native替身只能证明接口/算术和alias性质。真实KML及完整Encoder严格门槛仍须后续新授权验证。本轮无集群提交或默认集成。
