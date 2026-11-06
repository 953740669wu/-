# R12 job2049894：真实A/B无训练收益结案摘要

处置：R12_CLOSED_NO_TRAINING_GAIN。目标与strict数值门槛通过，但这一次同节点A/B没有训练耗时或采样内存下降证据；保留原fp32基线，不集成候选、不换tile、不再搜索或追加运行。此为单对探索，不宣称稳定回退或科学/生产接受。

来源：严格读取RUN_COMPLETE.analysis_inputs指定的target→strict→perf_baseline→perf_candidate四阶段；32项交接/bytes/SHA/收集索引核对通过。原始各阶段结果、steps、暴露清单及原审计已锚定，输入前后SHA一致；未修改原件、读取权重或重新训练。详细核对见INPUT_VERIFICATION.json和VALIDATION.json。

实际KML目标输出比较1项、完整Encoder两侧strict各5更新共3895项、两侧perf首次5步各15项原loss比较均通过且记录差0。strict是10次实际优化更新；两perf各25次，总60完整模型更新；不把strict5个配对循环误记为只有5次更新。所有比较是原记录复核，S08未重新计算模型。

同job2049894/cn21338的baseline与candidate为两个独立新进程，顺序执行baseline后candidate，均完整25更新、B64、1600帧；前5预热，观察step6—25共20步。初始化、scale、源/descriptor、逐帧顺序、mask、库/环境/CPU36核对一致。无Torch profiler，原计数/诊断/暴露检查保留，不与R9/R11诊断或旧跨job耗时作对照。

| 同范围观察 | baseline | candidate |
| --- | --- | --- |
| 后20步中位 seconds | 4.5102391038 | 4.6280611481 |
| 后20步 min–max seconds | 4.320208–4.618458 | 4.481312–4.926456 |
| 全25步训练合计 seconds | 113.435457 | 117.833010 |
| perf进程wall seconds | 167.404845 | 170.552771 |
| 相同25步范围采样HWM最大 MiB | 6820.117188 | 6923.132812 |
| 训练期采样数 | 50 | 50 |

变化公式：(candidate后20步中位 / baseline后20步中位 − 1)×100 = **+2.6123237%**，即本次候选耗时增加约117.822ms；不是提速百分比。范围交集为4.481312–4.618458秒。范围重叠不抵消本次中位更慢的事实，也不构成稳定性能回退/显著性的推断；没有重复试验或交错A/B/A。

HWM来自每个独立perf进程25步前后各一次、共50次相同时点采样，均为采样时刻的process-lifetime高水位；候选本次高103.015625MiB，没有观察到内存下降。不称单步独占内存、整个job最终峰值或稳定内存回退。

分项wall（seconds；保留原记录测量边界，未归因项不补来源）：

| 分项 | baseline | candidate |
| --- | --- | --- |
| data_loading_seconds | 1.341383 | 1.704422 |
| batch_materialization_seconds | 0.024948 | 0.024870 |
| mask_and_attempt_ledger_seconds | 2.272581 | 2.171816 |
| training_step_seconds | 113.435457 | 117.833010 |
| diagnostic_seconds | 10.014091 | 9.756072 |
| strict_comparison_seconds | 0.000000 | 0.000000 |
| checkpoint_recovery_seconds | 7.351268 | 7.375798 |
| unattributed_seconds | 32.965115 | 31.686782 |
| wall_seconds | 167.404845 | 170.552771 |

上述是两个perf进程的分项，非整个job墙钟。strict阶段wall94.508650秒，训练两侧合计46.028333秒、严格比较11.448724秒另记，不混入perf样本。调度整个target/strict/perf链为471节点秒（usage470秒），不与单个perf进程wall混称。未归因项是原记录差额，分项对账不证明已精准归因所有开销。

计数核对：每步逻辑KML均149；baseline原生149、目标完整dW12/分块0；candidate原生161、目标分块24/完整0、dispatch12。target局部原生1对2；strict两侧各5步与perf首次5步frame/mask一致。计数改变已显式记录，没有让候选沿用旧原生149的门禁。

四阶段共139个CPU完整快照（7+24+54+54），所有采样TID在selected36；两侧perf同一授权38/实际36/预留2与库身份。两侧checkpoint保存/恢复原记录均参数/AdamW/RNG/cursor/身份一致、固定前向差0、额外更新0；权重只留远端，S08未下载、读取或重新验证权重。

边界：只接受“该单对探索未获训练收益”的结论；数值通过不等于性能通过，更不构成科学/生产接受。正式split/subject映射UNKNOWN，无val/test；工程暴露的16单元/1600帧范围及未来按真实subject排除最终test的要求保持。旧基线/候选/阈值均未修改。

交付与复核：AB_SUMMARY.json保留两侧全部25步及后20步原始计时、内存范围、分项及恢复记录，并锚定source result/steps的path/bytes/SHA；4个LOCAL_FIXTURE只验证精确warm5-observe20、缺步/重复/标记错误、非有限数和百分比正负号。未重跑旧套件或产生新实验。R12原交接显示SUCCEEDED/exit0且所属进程清理完成；S08无活动job，不介入S07部署或通信接受。
