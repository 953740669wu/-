# 诊断R1既有证据收尾：只读补证与缺口定稿

总协调已发布，未确认原07/01窗口接收或启动。原数值阈值、训练FAIL及所有冻结包保持；无新诊断/模型/通信/集群执行授权。本轮目的为处置55份暂缓诊断材料的记录完整性，不是数值放行。

## 07：既有原件核查

本轮目标：按01 DIAGNOSIS_REVIEW的E02等证据不足项，只从现存原件判断是否能补齐真实compute PID、Popen PID、父子身份和退出时序；找不到则形成有证据边界的缺口声明。
参考文件：自己的SESSION_STATUS/ROUND_DELTA；S01/real_dual_ddp_numeric_diagnosis_r1_20261106/DIAGNOSIS_REVIEW.json及CURRENT_PID_CHECK.json；自身诊断目录DIAGNOSIS_READY、RUN_*.json、evidence/*supervision.json、*_initial.json、controller及worker日志；本卡。所有相对路径以c2/stage4_sessions/work为根。详细报告按疑点打开。
完成标准：
1. 只写S07/real_dual_ddp_evidence_closeout_r1_20261106/及自己的两个短状态。源代码、原报告/READY/FAIL不覆盖。
2. 在已有诊断证据及其明确引用的本地原件中做一次定向检索；不扫描整个磁盘/环境/远端、不重启worker或运行测试/模型/通信、不提权或安装。
3. 对Popen与计算PID差异、实际后代归属、15秒清理证据分别列原件路径/bytes/SHA/原字段和结论。现时PID不存在不能证明当时15秒内回收；缺时间戳或身份链明确UNKNOWN。
4. 若现存原件还可回答fp64实际线程、历史初态等01其它缺口，可并列引用；否则保持原限制。新DDP因权限失败未完成仍是NOT_RUN，不尝试补跑。
5. 输出EVIDENCE_CLOSEOUT.json、简短REPORT.md及EVIDENCE_CLOSEOUT_READY.json，含每项SUPPORTED/UNSUPPORTED/NOT_RECORDED、原始SHA、未能恢复的历史证据和对结论的影响。无法恢复也是本轮完成结果，不能无界等待或伪造。
6. 给精确归档清单，更新SESSION_STATUS/六行ROUND_DELTA；不将旧目录改写为完全PASS。无需运行新的进程检查来冒充历史证据。

## 01：收尾独立复核

本轮目标：07完成后核补充原件是否真实解决缺口，或是否清楚保留不可恢复限制。
参考文件：自己的短状态、原DIAGNOSIS_REVIEW、本卡及07 EVIDENCE_CLOSEOUT_READY绑定原件。
完成标准：只写S01/real_dual_ddp_evidence_closeout_r1_20261106/及自身状态；交EVIDENCE_CLOSEOUT_REVIEW.json，逐项核SHA与证据强度，区分“历史证据已补齐”和“缺口已如实定稿”。明确哪些结论仍未知，以及是否足以作为保留限制的诊断档案归档。档案可归档不等于原数值通过、清理实测通过或训练授权。不新跑模型/收缩/DDP/集群或重做大矩阵，不修改原FAIL。
07 READY未到仅准备审核要点、保存WAITING并结束；不后台监视或新增90分钟等待。07就绪后由用户在原会话续接。

## 其它窗口与协调接续

02当前无具体疑点，00/08/Git待命。两份READY/REVIEW齐后，协调判断55份旧诊断加本轮补充是否可按“有限诊断/缺口保留”冻结归档；再依据数值归因另定最小候选提案，不能把记录收尾当训练前置门槛通过。Git需新精确清单，不能追加已验收268份批次。
