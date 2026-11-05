# S04 R3：一次无量化fp32路径对齐（实现前冻结）

只在本R3目录工作并更新根短状态，R1/R2完整保留。原B2/M17/D512、16参数初值/输入SHA、loss、fresh AdamW、2线程和83项门槛不改。
这是一项明确的计算路径对齐，不把合法fp32舍入称编码缺陷；无论结果如何，不继续扩搜或追加第二种对齐。

## 唯一改动

- 仅torch_fp32_control分支采用原生F.linear及原生autograd，统一bias epilogue及dX/dW/db的生成/归约路径；bf16仍使用原custom Function。
- 候选自行保留norm1→QKV→SDPA→out projection→residual→norm2→FFN/ReLU→residual。绝不调用整个参考TransformerEncoderLayer.forward，也不调用MultiheadAttention.forward代替显式attention重写。
- 按实际Torch2.7.1源码：norm1输出先转[M,B,D]；F._in_projection_packed作自注意力打包投影；Q/K/V按原view/transpose/view路径到[B,8,M,64]；SDPA输出permute为[M,B,8,64]后contiguous、展平[M*B,D]作原生输出投影，再回[B,M,D]。保留同一反向归约图，不只对齐forward数值。
- FFN仍经候选linear接口，但fp32诊断分支直接返回F.linear；不进custom backward。原ReLU、norm、残差和heads/loss保持，不采用参考gate/参考梯度注入。

## 检查次序和停止规则

先写原生linear/gradient与候选结构检查，保留R2原路径不能满足新增检查的红灯；随后一次性实现上述改动。
用固定原fixture，参考/对齐候选各一次真实loss/backward/AdamW，逐项记录原7FAIL是否变动以及所有新FAIL，完整保留83项。
fp32原门槛：max_abs<=2e-5（exp_avg/exp_avg_sq<=2e-6），ref_norm>1e-8还须rel<=2e-6；keys/shape/dtype/finite/梯度和step严格检查。
用同一夹具对原bf16模式作一次行为核验，83项指标须与R1及R2原记录逐项一致；这是保留旧失败的回归，不是新bf16候选。
若对齐控制仍FAIL，记录未对齐的算子/布局/反传路径或误差缺口后停止，不再改代码追PASS；即便83全过也仅本地fp32控制接受，非bf16/KML或科学等价接受。
另交至多一份精度边界提案，本轮不实现。无KML/CPU36/集群/性能/峰值/完整模型/200步/S05或Git暂存操作。
