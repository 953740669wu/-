# S02夜间工程入口（本地已准备）

依据OVERNIGHT_ENGINEERING_20261105，仅完成S02节。接口先于代码发布；代码/包就绪后冻结，不热改。S00_DATA_READY已收到且完成元数据兼容核验，无须等待正式split推进本次工程入口。原R8正式门禁和历史数值/内存证据不变，checkpoint优化任务保持结案。

## 交付与范围

完整Encoder37995777参数、fp32/CKPT0、原native SDPA/KML linear、原mean voltage/coarse双loss与AdamW。13个关键R8文件逐字节不变；engineering_training.py仅把checkpoint协议标签两处改为独立工程协议，模型/训练/恢复算法完全不变。新engineering_data.py明确隔离正式模式；train_engineering.py复用R8训练流程，移除正式val调用、加入暴露和计时。限时包装仅替换入口与工程环境变量。最小差异见diff/R8_TO_ENGINEERING.patch。

接口SHA：8b1b540b8adeb4f4e49233c262b113c7c437f7a6e30b9f6d13113a96891dc669。
源码清单SHA：e4acbbcb604dc3afd22b462bbfc2c3e348108c32e004557b891de7e14978b7d2。
代码包：E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S02\overnight_engineering_20261105\package\S02_OVERNIGHT_ENGINEERING_CODE.zip，71182bytes/29文件，SHA256=add690cf983d5902c78586101ee6250358380786a8c13aa209b0a024735835a7。
精确文件及解包SHA见package/PACKAGE_MANIFEST.json；命令和资源边界见C2_HANDOFF.md。

## 数据与暴露

固定源为任务卡14300单元/1430000对/143case/3399057bytes manifest SHA=bdd146040bddf2ddd47fb9d571d5d2f40e5fa20fbd30d0c0d11239893e647032，工程源锚并非正式冻结。固定S00描述SHA=b88ea9745147acf7fa70d51dc27c727f22f14e98af5dff1b80a9047e95648cd6：s0285/s0593、16单元、1600帧。仅元数据和S00交接SHA已在S02本地核验；真实NPZ/manifest Linux路径没有在S02读取，实际来源/选样重算/文件SHA门禁必须由S00登录侧检查并由唯一作业再次执行。S00选样检查是119候选均具备至少8个合规单元的记录，入口按已发布接口重算选择，若不一致停止、不换样。

同unit/belt/pair配对、base_of_pair与states/电极顺序核验、原参考均值*100，工程train absmax只拟合一次，无val/test。所有工程标记显式UNKNOWN/NOT_RUN_NO_FORMAL_SPLIT；case不当subject。运行暴露清单先于模型工作创建，每次读取/更新前后原子持久化，区分selected、loaded、possibly-used interrupted update及confirmed frames，恢复探针另记0额外更新。失败/timeout保留清单；未来按真实subject映射排除工程暴露对象的最终测试，当前无无泄漏保证。

## 本地检查（非真实训练）

14项夹具/小型native Torch36检查通过：工程数据/隔离/来源锚/范围/顺序/暴露8项，小型连续多batch、原mean/AdamW表达式、独立工程checkpoint零更新恢复3项，复用配对/状态顺序/电极顺序、零参考与cross-belt/SHA异常3项。实际2种CLI在框架前拒绝缺失描述或工程输入送正式入口；全部Python3.9 AST、LF、Git Bash -n、R8关键文件SHA、源码清单与ZIP逐项SHA核验通过。证据evidence/local_validation.json和各日志。

计时拆分Python入口内读取、batch物化、训练、诊断、checkpoint/恢复、未归属开销；诊断计时范围显式记录，外层部署/调度壁钟由S00收集。RSS/HWM为process_lifetime，不作逐步独占峰值或稳态性能结论。

## 未运行与停点

S02本轮真实NPZ读取0、完整模型训练0、C2/KML验证0、集群提交0；正式val/test不运行。Linux实际Torch36/全部TID/KML映射/GEMM、真实数值有限训练、checkpoint和恢复仍须唯一工程作业验证。当前无已知S02代码阻塞；S00部署及S01绑定精确SHA的专项审核是后续执行前提。S02不代交任务、不声明其它窗口活动job终态。失败/资源超限/SOURCE_CHANGED保留证据停止，无自动重试。

## 精确待归档范围

本目录INTERFACE.json、INTERFACE_READY.json、CODE_READY.json、SOURCE_SHA256.json、C2_HANDOFF.md、REPORT.md、diff/R8_TO_ENGINEERING.patch、package/PACKAGE_MANIFEST.json、package/S02_OVERNIGHT_ENGINEERING_CODE.zip、源码清单所列28文件，以及evidence/R8_INPUT_SHA256.json、S00_COMPATIBILITY.json、local_validation.json、验证日志和准备/发布脚本；另自身SESSION_STATUS.md与ROUND_DELTA.md。最终精确路径/SHA由ARCHIVE_FILES.json列举。仅元数据/代码/证据，无真实数据、权重或环境。没有暂存/提交/推送。
