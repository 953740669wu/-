# S04 R3：一次无量化fp32计算路径对齐

2026-11-05（Asia/Shanghai）。状态：**PASS_LOCAL_FP32_CONTROL_ONLY / BF16_NUMERICAL_FAIL / NOT_INTEGRATED**。

按本轮交接只进行了一次预先明确的路径对齐。新fp32控制83/83通过，并且全部83个输出/梯度/参数/增量/moments张量与参考逐位相同；原7项FAIL全部消失，无新增FAIL。**这是固定本地夹具上的fp32控制通过，不是bf16、KML、完整模型或训练质量接受。** 原bf16模式83项指标与R1/R2逐项完全一致，仍55PASS/28FAIL。

## 改动与保留

- 仅本R3目录及S04根短状态；R1/R2的71个既有文件SHA保持不变，原根R2短状态另存evidence/ROOT_R2_*.md。旧包原件及成员身份已核。
- 原fixture/common.py及baseline逐字节复制；运行时核所有输入及16参数初值payload SHA，与R1一致。B2/M17/D512/8头/FFN2048、原heads/loss、fresh AdamW(lr1e-4,betas0.9/0.999,eps1e-8,decay0.01)、2线程及原83项门槛不变。
- candidate仅改torch_fp32_control分支：FFN调用F.linear及原生autograd；attention显式按已安装Torch2.7.1源码对齐packed QKV投影、布局和输出投影的原生反向归约图。
- 候选仍自行执行norm1、QKV、SDPA、输出投影、两次残差、norm2、FFN/ReLU；**实际控制forward禁止调用TransformerEncoderLayer.forward和MultiheadAttention.forward**，因此不是换回整个参考block或整个attention模块跳过重写验证。
- 不读取参考gate/梯度，未在更新后覆盖参数或状态。双方仅在计算前加载同一冻结初权重，各自独立backward/AdamW一步。
- gemm、_chain_gemm、_ChainBF16LinearFn、旧_attention的AST保持相同；原bf16执行同时用原83项记录实证核验。未实现P1或多套bf16候选。
- 最小diff：diff/R2_TO_R3_FP32_ALIGNMENT.patch，共48行。代码/来源/包SHA见SOURCE_MANIFEST.json、ARTIFACT_SHA256.txt、package/PACKAGE_MANIFEST.json。

## 这一次对齐具体做了什么

R2使用mm后add bias以及custom backward，而参考用原生linear/autograd。二者数学同义，但舍入、bias归约以及packed QKV反传布局不同；不能直接据此称编码错误。

R3唯一诊断改动同时对齐这组路径：

1. FFN fp32 linear由原生F.linear生成原生autograd图，不走_ChainBF16LinearFn。匹配bias epilogue及dX/dW/db路径。
2. attention从原[B,M,D]先转[M,B,D]，调用F._in_projection_packed作自注意力投影；Q/K/V按原view→transpose→view转[B,8,M,64]，保留packed拆分的contiguous及原生归约路径。
3. SDPA输出按原permute(2,0,1,3)→contiguous→[M*B,D]，做原生F.linear输出投影后回[B,M,D]。没有改变SDPA内核或模型结构。

实际本地Torch的MultiheadAttention.forward、multi_head_attention_forward、_in_projection_packed和TransformerEncoderLayer.forward的源路径/行号/函数及文件SHA在evidence/torch_source_identity.json。F._in_projection_packed是本地私有接口依赖，未据此宣称其它Torch版本或C2可用。
此次将bias epilogue、原生autograd和布局作为**一组**对齐，所以只能确认原7项差异在这组对齐后消失，不能把每项改善分别归功于某一个改动，也未追加分拆搜索。

## 实际检查与83项结果

先冻结ALIGNMENT_PLAN.md、common.py及targeted tests的SHA，保存R2旧路径的2项红灯；一次性实现后，这2项检查通过：

- 原生linear的forward及输入/权重/bias梯度与F.linear逐位一致，不进入custom backward。
- 禁止whole block/whole MHA调用时，候选仍完成真实forward/backward；packed投影确实只调用一次，Q/K/V为同一[M,B,D]输入，shape/stride与原路径一致。

原严格fp32控制协议完整复用R2的compare/limits实现（AST相同）：max_abs<=2e-5，moments<=2e-6；ref_norm>1e-8还须rel<=2e-6，小范数仅用max_abs。结构、dtype、finite、应有梯度、step=1仍严格检查。
输出、loss、输入梯度各1项，16个参数各检查gradient/更新后参数/增量/exp_avg/exp_avg_sq，共83项，**全部max_abs=0、rel=0**。原7项的变化如下：

| 原失败项 | R2 rel | R3 rel | R3结果 |
|---|---:|---:|---|
| update.block.self_attn.in_proj_weight | 2.2201026e-5 | 0 | PASS |
| parameter.block.self_attn.in_proj_bias | 1.5127494e-2 | 0 | PASS |
| update.block.self_attn.in_proj_bias | 1.5127494e-2 | 0 | PASS |
| update.block.self_attn.out_proj.weight | 6.6949772e-6 | 0 | PASS |
| update.block.linear1.weight | 4.9861114e-5 | 0 | PASS |
| update.block.linear2.weight | 7.9573863e-6 | 0 | PASS |
| update.head_coarse.weight | 9.6871890e-6 | 0 | PASS |

新增失败=0。evidence/fp32_aligned.json给出完整83项；failure_transitions.json给出原7项前后完整误差、全部83项状态及空的新增失败列表。
bf16模式只做一次旧行为核验，没有新精度配置或新候选：evidence/bf16_unchanged.json全部指标与R1原记录及R2复现记录相同，仍28FAIL；保留R2已定位的ReLU gate/QKV梯度量化风险，未称其解决。

## 唯一后续提案与停止边界

仅交PRECISION_BOUNDARY_PROPOSAL.md中的P1，未实现：保留bf16 block接口，内部attention/QKV反传与bias归约、norm2→FFN1→ReLU保留fp32，仅FFN2 GEMM内部使用bf16 operands、fp32输入输出/梯度/累积。
入口及出口量化仍会扰动gate和更新；扩大fp32稳定计算范围还可能抵消带宽目标。文档列出dtype/布局、静态转换账和原83项通过/否决条件，没有保证数值或性能收益。任一旧/新失败即否决该有限提案，不再自动枚举其它精度组合。
本轮对齐已按一次尝试完成，不继续改舍入路径；后续是否安排P1由协调评审，不自动执行。

## 环境与复现

只读使用已有S02/round2_20261104T114949Z/.venv，Python3.11.9/Torch2.7.1+cpu/Windows，Torch intra-op=2。bf16旧行为仍是量化输入上的fp32 GEMM模拟，不是实际bf16/KML计算核。
无KML/CPU36/SSH/集群job、性能计时/峰值、完整模型、200步/S05、Git暂存操作；新增job与节点小时均0。本轮本地检查进程已结束。

项目根目录运行：

```powershell
& './c2/stage4_sessions/work/S02/round2_20261104T114949Z/.venv/Scripts/python.exe' -B -m unittest discover -s ./c2/stage4_sessions/work/S04/round3_fp32_alignment_20261105/tests -p test_alignment.py -v
& './c2/stage4_sessions/work/S02/round2_20261104T114949Z/.venv/Scripts/python.exe' -B ./c2/stage4_sessions/work/S04/round3_fp32_alignment_20261105/tests/check_alignment.py
python -B ./c2/stage4_sessions/work/S04/round3_fp32_alignment_20261105/verify_delivery.py
```

前两条本轮exit0；第二条仅表示该本地fp32控制PASS，同时明确记录bf16 28FAIL。最后一条仅核来源/旧证据保留/包与保存结果关系，不是新的数值实测。
更新后的根短状态与R3内部状态均明确本轮R3；R1/R2的独立目录、原报告/失败及旧包原件保留。
