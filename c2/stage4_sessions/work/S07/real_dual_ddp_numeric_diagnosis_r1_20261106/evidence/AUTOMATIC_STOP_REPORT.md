# S07 本地数值诊断R1

状态：STOPPED_DDP_PERMISSION_FAILURE。冻结训练包和原FAIL保持；本轮无训练PASS、无集群job。

运行次数：{"full": 1, "sequence": 1, "ddp": 1, "fp64": 1}；总本地壁钟11.609秒。每路径60秒/清理最多15秒/总300秒，首次路径前独占标记；没有重试、安装、提权或切换后端。

先读HYPOTHESES_AND_CHECKS.md。只读抽取原TinyEncoder类、原training_graph及02原compare；seed7、输入、初值、mask与原门槛固定。完整B64为参考，顺序32+32只定位，不替换正式参考。浮点误差统计使用原compare的float64 norm；可选float64原因对照另计一次，不产生新模型forward/backward。

回传依赖顺序上最早参数越阈值：parameter.tf.weight。前向/adjoint首次逐位差异与首次原阈值失败、全部输出/两loss/11参数梯度/两输入梯度指标见DIAGNOSIS.json。最早参数分支不是实际GPU/CPU指令trace，不得据此指定某个系统库内部指令为根因。

假设结论：{
  "forward_sharding": "EXCLUDED_IN_CURRENT_FULL_VS_SEQUENCE",
  "denominator_and_scaling": "Full/sequential denominators4/16384, objective1x; DDP source backward2x/default averaging, input divide2. Runtime DDP verification requires completed path.",
  "accumulation": "SUPPORTED_IDENTICAL_OPERANDS_DIFFERENT_FP32_WEIGHT_CONTRACTION",
  "ddp_additional_effect": "UNKNOWN_NEW_DDP_NOT_COMPLETED",
  "historical_environment": "Original actual thread counts, initial tensor digest and intermediate tensors not retained; exact historical comparability remains limited."
}

若DDP权限或通信失败，则该路径立即停止并回收本任务Popen进程，后续不再数值计算。此时旧DDP13标量指标可核，但没有原中间张量，不能排除DDP额外误差。本轮是否复现同样13项标量误差及float64原因对照由JSON原件判定，不把未运行部分补为PASS。

未定位实现缺陷，暂不建议热改。最小下一动作是01核操作数/归约对照与证据缺口；任何后续候选须另定版本，保留原完整B64、原阈值、全部13失败检查及默认DDP缩放。回归至少应覆盖相同固定样本完整B64/分片/DDP的全部输出、loss、参数/输入梯度，并保留初始化/分母/原名与原比较器覆盖；本轮不继续运行这些回归。

需要02回答的具体接口/数学疑点：无。若仍有DDP中间量缺口，这是通信/权限停点，不能转嫁为02重做参考。17来源bytes/SHA末次未变：True。

raw/仅保存诊断激活/adjoint/梯度，无模型初值权重或真实语料；归档清单排除raw张量、环境、数据和权重。JSON指标及脚本/原日志可直接交01。
