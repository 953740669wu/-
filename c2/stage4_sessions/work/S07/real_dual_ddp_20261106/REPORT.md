# S07 首次真实双域DDP候选

日期2026-11-06；代码实现完成，交S01专项审核，C2完整模型训练未运行。**本地严格fp32小B64配对FAIL保留，不能称全部本地检查通过或训练就绪已放行。** 只写新real_dual_ddp_20261106目录和自身短状态；S02/R7/历史失败/共享Git不改。

本轮新增完整Encoder及两个head的DDP forward、全局分母和正确平均系数、顺序32+32分片与原mask哈希、连续完整B64前5门槛、同状态接续25步、逐步canonical模型/AdamW字节hash、分rank/参考暴露、远端checkpoint及零更新恢复。复用S02冻结参考与原比较器，无数据/优化或阈值变化。精确训练/资源/退出约定见TRAINING_CONTRACT.md，运行及收集见INTERFACE_FOR_S00.md。

先写全局加权反例、重缺样拒绝、当前job/绝对截止/单rank失败清理及结果身份检查，再实现相应代码；红灯原件在evidence。R7只复制CPU36及七个小函数，函数文本SHA/原行号记录R7_COMPONENTS；未修改原R7。所有本轮运行源为新增，minimal.diff给新运行源/测试；共享参考/原模型无修改。

独立检查实际19方法。最终Windows标准库17方法16过1 Linux后代清理skip；已有Torch2.7.1+cpu实际数学/图/RNG/空mask检查过。小DDP到达Gloo/DDP/backward且两rank参数梯度逐项相同，输入梯度按2缩放也通过，但完整fp32小B64参考的13项中3项未过原门槛：val.weight与pos.weight相对9.410191e-5，tf.weight绝对3.723800e-5、相对1.142869e-4。因此合计17过/1失败/1skip，**早期18过1skip日志不是最终结果**。新增严格检查原样保留，不修改数据、参考或阈值以求PASS。

本地原FileStore停before_pg到25秒监督截止，原因缺证，原件保留；沙箱TCP连接实际10013/10049，同代码原预算在沙箱外可完成DDP。不能说FileStore根因已证或C2初始化已解决。小模型失败体现fp32 B64/分片路径的数值风险；完整实际模型、C2/KML和原始初始化/数据均未在本窗口运行，不能外推其通过或失败。S01应独立核本轮失败与版本门槛，S00只按最终具体SHA结论执行，不靠候选READY跳过失败。

默认Python无Torch/NumPy，后来依S02 READY发现既有venv并只读借用，未装依赖；本地平台/解释器/API SHA、旧失败与最终误差原件都有记录。本地只创建短受控子进程且均回收；无SSH、调度、训练job或真实数据更新。原数值标准/原R7 FAIL历史不动；正式性能/扩展效率NOT_MEASURED，工程subject/split UNKNOWN。

本轮冻结包与来源身份/实际方法/失败边界由SOURCE_MANIFEST、SHA256SUMS、TRAINING_READY绑定。Git仅由唯一窗口选择ARCHIVE_SCOPE列明路径；不把包、环境、实际数据、checkpoint/权重或原始临时副本纳入Git。核验通过后再提醒其精确归档，不自动stage/commit/push。
