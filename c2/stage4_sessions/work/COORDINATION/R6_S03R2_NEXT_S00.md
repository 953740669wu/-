# 给现有S00会话：本轮固定交接

日期：2026-11-05。本轮最多一项新数值job与一项新C测试job，分别落新目录/回传；不自动追加内存或HBM，不重跑旧R5/R7。

## 本轮目标

先执行S02 R6一组完整B64/CKPT0对CKPT1的C2/KML严格对照，原mean、固定case、fp32/fresh、16_adjacent/pre、HBM0。分配首选同域38核、实际计算36留2，24576MB且limit同值、最多900秒。原包SHA=`26e542430f024f60277bdbbbc699b41a203ee74270022806074040a531ac166f`；只调用run_s00_job.sh equivalence，不运行memory分支。

该项结束并正常清理后，独立干净环境执行S03第二轮新的50个C/UBSan场景及独立.so构建，同样限制在选中36核、24576MB及同值limit、最多300秒。协调包S03_ROUND2_C_VALIDATION.zip，SHA=`0fe3eeb3a7ad7fe2fb34eea220f3147edba5b72cdc44f5c7db4fd46d98ea872a`。无需作者重新打包。

## 参考文件

先读自己的SESSION_STATUS.md、ROUND_DELTA.md和总表，再读本轮R6_S03R2_LOCAL_REVIEW.md。实际操作只展开：

- `work/S02/round6_ckpt64_20261105T043038Z/C2_HANDOFF.md`的严格对照节及其package清单；case可只读复用该说明给出的旧S00远端文件，必须重新核实际大小/SHA，不重生成输入。
- `work/S03/round2_api_bounds_20261105/LINUX_COMMANDS.md`、tests/cases.py和tests/run_cases.py。本次frozen是上轮已接受候选，非最初生产源；previous的21个预期失败/29个控制必须逐项满足，其runner审查成功退出0；新候选50/50、无UBSan失败。别套用旧25-case/冻结runner退出1的包装判据。

work相对c2/stage4_sessions。提交前核真实远端ZIP/payload SHA、LF/Linux语法、来源与实际调度；source运行环境后恢复Donau PATH。新C任务清除KML/HBM/LD_PRELOAD等污染，按已有CPU36拓扑收窄所有子进程；UBSan不可用时记录阻断，不静默移除检查。

## 完成标准

两项分别观察到真实终态，回传job/资源/选核/内存/时限/实际命令、所有输出/退出/源码与原mtime_ns/bytes/SHA。S02必须有本R6完整1063项metrics、双方真实KML、完整同PID CPU36与checkpoint配置/模型隔离记录；PASS仅限该case，FAIL仍保持原阈值，不改检查或扩大矩阵。

S03回传previous和candidate的全部50场景、UBSan原始stdout/stderr与逐项期望审查、编译器/参数、独立库ELF/依赖/源码及二进制SHA。不跑真实HBM、policy_probe或模型preload，不把构建成功当50场景通过。

S02若只是数值FAIL且已终态/清理，仍可执行独立S03；若资源越界或无法清理，停止对应任务并报告。提交前的普通路径/包装问题可最小修复并留身份；已运行的模型不自动重提。

每轮结束更新S00自己的SESSION_STATUS.md、ROUND_DELTA.md，按六行格式只回报本轮变化。详细报告/证据保留链接，总协调按验收需要读取。
