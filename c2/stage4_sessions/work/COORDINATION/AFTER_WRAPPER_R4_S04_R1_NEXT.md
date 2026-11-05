# 本轮短交接：07带事件诊断与04本地失败定位

2026-11-05；优先短状态/变化摘要，必要时才打开相关报告。改代码或提交前仍核最新文件身份与实际活动job。

## S00

**本轮目标**：只提交一次已核S07 R4诊断部署包，捕获2040233所缺的双方阶段时间和监督事件。不是确认原故障已修复的重复性能试验。

**参考文件**：自己的短状态；COORDINATION/WRAPPER_R4_S04_R1_REVIEW.md、S07_R4_S04_R1_TARGETED_REVIEW.json；S00/s07_wrapper_r4_diag_20261105/{COMMANDS.md,DEPLOYMENT_RECEIPT.json,ARTIFACT_SHA256.txt}及其中原样执行文件。

**完成标准**：

1. 执行前核队列/提交记录避免重复。只用S07_S00_DIAGNOSTIC_WRAPPER_R4.zip，62715bytes/14文件+空目录，SHA=b20e248be761db6c645fdbcebbbfc61d083642bb0e1d959eb1a0fcfa9b304284；内包仍31262bytes、SHA=af2725e24d0bd8b2183f1d7bc8b6aae79f801b7b83b640b41645e822e0c23f45。新S07_INIT_DIAG_R4_<UTC>目录，原样prepare/清单/命令，不临时改代码或将新目录当绕过去重的手段。
2. 单节点两个不同38物理核NUMA域，76分配/每域36实际留2，总DDR24576MB且同limit、exclusive、HBM0；job300秒，consumer统一270秒预算含交接/检查。原生job/nonce/raw/ready/30秒交接及逐核拓扑保持，登录publisher在RUNNING后单次及时执行；不需要C++编译器。
3. 同job新增6诊断+6身份+16原检查共28项须全过、无Linux跳过，环境通过后仅一次原run_checks四case顺序执行。pg_timeout=5、case deadline=30不改；normal失败即停，后三项记未运行，不单跑或重试normal。任何非预期失败停止，不增加预算、换环境/后端或改判据。
4. 终态/PID清空后收集双方完整events.jsonl、supervisor.events.jsonl及原JSON/log、manifest、commands、checks/summary、调度原件、逐step退出清理和bytes/SHA/远端mtime。保留TRACE_WRITE_ERROR/缺行/截断和未闭合区间；诊断不完整时仍回传原件，不补跑，不凭缺end称永久卡住。
5. 无论normal成功或失败，都交已观察的两rank导入/库SHA/初始化及清理阶段摘要；阶段间隔含日志I/O，不作纯通信性能结论。若全四case通过，只称固定小张量探针通过，不能据一次未复现认定原根因已修复。
6. 仅本次诊断job，不重跑02/06，不扩训练或性能配置。更新自己的短状态和六行变化摘要，列活动job或终态及节点秒；07原会话等待本轮事件再分析。

## S04

**本轮目标**：在本地定位R1的28项数值失败，先验证候选重写路径的fp32语义，再分辨量化/误差传播。保持原数值失败，不进入C2或性能试验。

**参考文件**：自己的短状态/变化摘要；COORDINATION/WRAPPER_R4_S04_R1_REVIEW.md；S04/NUMERICAL_PLAN.md、DTYPE_INTERFACE.md、candidate/{s4_models.py,kml_ops.py}、tests/{test_contract.py,check_block.py,common.py}及evidence/block_numeric.json的失败项。

**完成标准**：

1. 保留R1夹具/权重/协议/失败JSON、候选及旧包身份，新轮放在S04独立目录。B2/M17/D512、原loss/AdamW/2线程及实现前门槛不改，不重抽seed、改分母/eps或放宽阈值。
2. 当前test_fp32_control仅比较原block与deepcopy。新增覆盖“候选重写结构、关闭量化”的fp32语义对照，检查输出、输入/参数梯度和一次AdamW/状态；使用原fp32控制门槛，不把原模块自我比较当候选验证。控制只作诊断，不修改生产入口或全局patch。
3. 基于同一冻结夹具定位首处分歧，重点检查linear1/norm2和FFN/ReLU误差传播；分别报告参考norm、绝对/相对误差、必要的中间激活/梯度及近零/符号变化统计，避免只用最终loss判断。四项失败梯度参考norm并非协议近零范围，保留这一事实。只做必要局部观测，不扩样本/模型矩阵。
4. 若fp32对照失败，先定位重写语义/实现问题；有确定原因才做最小修复，并用原冻结检查验证。若fp32过而量化路径仍失败，交有证据的敏感边界/精度策略提案，不能通过修改门槛宣称通过；原因未明则列证据缺口。此次不做无界参数/精度组合搜索。
5. 交一份简短归因结论（已证实/尚未证实）、必要检查/最小diff及来源SHA；有候选变化才打新包。实际KML/CPU36、转换耗时/性能/峰值、200步/完整模型均保持未运行。更新短状态/六行变化摘要，待协调评估，不自行提交集群或启动S05。

## 其它会话与归档

02已收尾待命，无需再发收尾任务；07等00新事件；01/03/06/08保留，05接口尚未稳定不启动。已核00新包及02收尾记录提醒唯一Git窗口归档；04的失败证据保留并标NUMERICAL_FAIL，后来改动另行核验，不混入已核范围。
