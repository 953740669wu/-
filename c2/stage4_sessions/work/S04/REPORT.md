# S04 R1：单 block 跨层 bf16 准备

日期：2026-11-05（Asia/Shanghai）。状态：READY_FOR_REVIEW / LOCAL_ONLY / NUMERICAL_FAIL / CLUSTER_NOT_RUN。

已交 dtype 接口、原规格单 block 最小候选、预先固定的数值协议、检查及失败证据。**准备工作完成；候选未通过数值门槛，不建议集成或扩展性能实验。** 没有实际计时，不能判断是否变快。

## 来源与修改范围

按 AFTER_MEMORY5_AND_S07_DIAGNOSTIC_NEXT.md 的“S04首次启动”，参考 S04_BF16.md、HANDOFF_PROTOCOL.md、总任务表及原计划 C/D 精度章节。
使用 S02/round7_seq5_20261105T082315Z 的 fp32/CKPT0 源：模型 SHA=9ff6417b80c42cee0df02fc52e1892b20cd7cd0abda36c7272bb8957a42fc2c2；kml_ops SHA=e6c5c4411c453c8168939cd51d737a7e9d8232bdfff05da3967805a5e917ff26。
原full_batch_step、比较器、固定case清单、输入协议及数值协议也与 R7 SOURCE_SHA256.json 的7项哈希相符；详 SOURCE_MANIFEST.json。
这些是本轮直接核源码/清单的证据，不冒称独立重审 S00 2040363 的完整远程结果。baseline 两文件为原字节副本。
另核原固定case文件SHA=4de1fb40eb1c4b43a8747586399f336bf9e37184592d66fdbf711abad8469846（271979513 bytes），仅读取权重；本轮原层及heads共16个参数张量与其initial逐位相同，详evidence/reference_weights_check.json。未运行该case完整模型。

只写本目录；生产核心、其他任务目录/状态、HBM分配器、attention内核、Git暂存区未操作。没有集群连接/提交、200步、完整模型运行或环境安装。
candidate 两文件只新增一个 BF16EncoderBlock 和专用 autograd linear/GEMM helper；原始 Encoder/训练loss/默认入口与全局patch函数保持。
diff/S04_BF16_BLOCK.patch 共97行，新增82行；代码及包的精确 SHA 见 ARTIFACT_SHA256.txt 和 package/PACKAGE_MANIFEST.json。

## 实现与权衡

512宽、8头、2048 FFN、pre-norm、ReLU、dropout=0，参数名称/shape与原层一致。激活在block输入/输出及FFN linear1→ReLU→linear2之间保持bf16。
归一化/原SDPA attention/两次残差相加/fp32 heads及loss仍为fp32；不触及decoder/conv。FP32主权重、梯度和AdamW moments/step保留。
KML候选forward/dX用bf16输入、sbgemm fp32 C，bias后量化；dW永远将g/x恢复fp32经原SGEMM。未用bgemm长K累积，也未用未验sbgemm替代dW。
这不是旧逐线性“输入fp32→bf16→输出fp32”路径：跨block和FFN中间保留bf16；但fp32稳定岛、sbgemm C与权重量化仍有转换成本，并未证明总转换量或整步耗时下降。
无跨step权重缓存，不会在AdamW更新后偷用旧bf16权重。原模块参数未增加/改义；不支持的mask/causal/dtype/layout明确拒绝。
原 s4_models.py 为有顶层参数/资源副作用的CLI，测试只编译其原始 Encoder 与新增 block 的类AST；实际forward/backward/AdamW为真实Torch执行。AST加载不是数值验收本身。

## 本轮实际本地检查

使用已有 S02/round2_20261104T114949Z/.venv/Scripts/python.exe，只读使用，不安装/替换包；Windows、Python3.11.9、Torch2.7.1+cpu、Torch intra-op=2。
torch Python入口、_C扩展、torch_cpu.dll 的路径/包版本/文件SHA和构建信息在 evidence/local_environment.json。不是C2/CPU36环境。

先冻结 NUMERICAL_PLAN.md、DTYPE_INTERFACE.md及三个检查文件SHA（evidence/PRE_IMPLEMENTATION_FREEZE.json），再记录红灯：8项中2通过、2失败、4错误，原因是候选符号/类尚未实现。
实现后8项通过；补上改变QKV拆分编排的独立MHA对照后，最终 **9项检查全部通过**：linear前向/dX/dW/db oracle、dtype/state_dict、拒绝错误精度/mask/causal、KML无后端拒绝、无全局patch、fp32复现控制、comparator负控及attention边界。
attention边界针对相同fp32输入/参数，与原nn.MultiheadAttention比较输出、输入及4个参数梯度，6项均满足2e-6；没有实现或验收bf16 attention。

单block数值：固定权重seed=0、输入seed=20261105，B2/M17/512，原fp32 heads和原pre mean loss，fresh AdamW一次更新，两侧同输入/权重/超参。权重与全部输入payload SHA在evidence/block_numeric.json。
这是一层单元夹具，不是原B64/M208固定case，也不是整编码器/真实语料训练。S02的旧fp32门槛完全未改。

| 对象 | 本轮结果 | 相对L2最差值/门槛 |
|---|---|---|
| block输出 | PASS | 0.255623% / 1% |
| 原pre loss | PASS | 0.026614% / 1% |
| 输入梯度 | PASS | 1.127505% / 2% |
| 16个参数梯度 | 4 FAIL | 4.814941% / 2% |
| 16个更新后参数 | 4 FAIL | 70.084369% / 1% |
| 16个参数更新增量 | 12 FAIL | 70.084369% / 5% |
| 16个AdamW exp_avg | 4 FAIL | 4.814941% / 2% |
| 16个AdamW exp_avg_sq | 4 FAIL | 5.651013% / 4% |

合计83项，55 PASS / 28 FAIL；无NaN/Inf、缺失梯度、参数/state dtype或step异常。逐tensor原始误差、近零规则、失败位置完整保留，不以loss通过覆盖梯度/更新失败。
最大相对更新差出现在初值为零的in_proj_bias；70.08%是相对于本次约1e-4尺度更新的差异，不是整个模型权重变了70%。具体因果未定位，不能直接套用S02历史根因。
实际后端明确为 torch_reference_fp32_emulation_of_quantized_sbgemm：fp32 GEMM处理已量化输入，检查精度边界/梯度，不是本地真实bf16计算核或KML实测。

## 未运行项与后续

实际KML/库头文件ABI/OMP-shim映射、sbgemm beta/初始C/累积路径、bgemm长K、C2 fp32 SGEMM dW均未在本轮实测。原库注释与历史行为不是本轮接受证据。
DTYPE_INTERFACE.md给出静态转换及张量字节账；转换耗时、forward/backward/AdamW/总步耗时、DDR/HBM实际峰值、吞吐收益全部NOT_RUN。
候选保持独立；先在原固定协议内分析数值FAIL，不能扩模型/200步/性能或改门槛追PASS。
SMALL_TRIAL_PROPOSAL.md列出以后经协调排期的单域36实际核算子/单block前置、最多1节点×300秒/24576MB及失败即停条件，当前不是执行授权。
200步loss轨迹、完整模型/至少四域/整节点三轮与第二主机、训练质量全部保留为后续门槛。本轮节点小时0。

## 复现与证据

在项目根目录使用上述已有Python运行：

```powershell
& './c2/stage4_sessions/work/S02/round2_20261104T114949Z/.venv/Scripts/python.exe' -B -m unittest discover -s ./c2/stage4_sessions/work/S04/tests -p 'test_*.py' -v
& './c2/stage4_sessions/work/S02/round2_20261104T114949Z/.venv/Scripts/python.exe' -B ./c2/stage4_sessions/work/S04/tests/check_block.py --output evidence/block_numeric.json
python -B ./c2/stage4_sessions/work/S04/verify_delivery.py
```

前两条分别预期exit0和exit1（数值FAIL），最后一条只核语法/来源/预冻结/包身份，不能代替数值通过。
源码路径、包成员与原件SHA、字节数及终检在SOURCE_MANIFEST.json、ARTIFACT_SHA256.txt、package/PACKAGE_MANIFEST.json、evidence/delivery_verification.json。
精度边界、最小diff、数值协议/全部失败指标、环境信息、单域小试提案、短状态与变化摘要均随包交付。
