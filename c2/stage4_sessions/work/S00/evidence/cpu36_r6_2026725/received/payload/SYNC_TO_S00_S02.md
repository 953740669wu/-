# 同步给S00/S01/S02：CPU36_POLICY已生效

权威约定：`E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\COORDINATION\CPU36_POLICY.md`。

**后续每个计算域/训练进程实际计算集合为36个物理CPU核心。旧38核及S02的4核配置只保留为历史，不能直接重投。** 此决定不改变模型、有效批量、损失、optimizer、数值阈值、24GiB预算或原小试时限，不授权扩大规模或自动提交。

## 给S00

先执行本轮DIAGNOSTIC_PLAN_FOR_S00中的有限小型线程诊断，不重跑完整模型。申请完整38核域时，显式选该域前36核，末2核预留；allocated/selected/reserved分别记录，不虚报调度分配。若只分到36，必须确认同域、物理核心和留核要求。

收到线程诊断评审后的修订，再统一更新S01/S02包装器、精确--physcpubind、CPU数量守卫、实际Torch/OMP线程设置、manifest、提交说明与SHA。远端LF/无CR/bash -n门槛保留。不能只把CORES_PER_DOM改成36、其余MKL_NUM_THREADS=1或旧4/38断言不动就重新提交。

## 给S01（本窗口已落实）

保留job2026450原FAIL及全部历史证据；先核对MKL/OMP/OPENBLAS优先关系、调用线程与全部TID。新CPU36合同原型保留越界、空/缺TID、核心不足、跨域、实际torch线程数不符的拒绝检查，允许合法的单核TID掩码；不通过删除affinity检查求PASS。当前交诊断与修复建议，不修改接受R2或运行模型。

## 给S02

原C2等价检查的--threads 4、4CPU断言和同PID守卫都改成经审查的36核版本；数值/内存测试实际绑定所选36核，核验真实torch intra-op与全部TID边界，记录分配/选用/预留集合。不要用--cpunodebind替代精确36核绑定，不改原严格数值阈值、有效B64或microbatch语义。Windows失败与旧4核准备包保持原身份，不覆盖成36核结果；S01线程问题尚未接受前继续等待C2模型执行。

## 交付与通知状态

当前会话未提供list/read/send thread工具，无法直接向另外两个聊天发送通知，也不能改写work/S00或work/S02来冒充同步。以上是可原样转交的同步单；协调STATUS已引用相同CPU36_POLICY。请由用户/总协调转发本文件路径给S00、S02。本窗口不宣称跨聊天消息已经送达。
