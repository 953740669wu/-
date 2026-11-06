# 总协调简短状态

- 更新/轮次：2026-11-05；OVERNIGHT_ENGINEERING_PLAN，待用户转发，非已启动。
- 用户新授权：暂时没有正式划分也推进固定真实样本工程小试；安排可独立的夜间工作，不为耗时凑任务。覆盖旧卡“全部训练必须先正式split”的限制；不建立正式划分、不接受正式效果。
- 已知数据：00核当前14300单元/143万对，manifest SHA=bdd146040bddf2ddd47fb9d571d5d2f40e5fa20fbd30d0c0d11239893e647032；工程卡锚该版，不冒充原11900冻结版恢复。正式split/subject映射仍缺。
- 任务分配：02独立工程入口先接口后代码；00固定样本/部署；01专项核具体代码/数据/部署；00条件满足直接唯一job；08可选只读结果整理。只维护各自目录，固定就绪文件免用户中转。
- 数据范围：ENGINEERING_REAL_CORPUS_PILOT_V1，固定<=2case各<=8个16电极单元；无正式val/test，case不等同subject，固定训练统计。EXPOSURE_LEDGER记录已选/实际使用，今后必须映射subject后排除最终测试。
- 执行边界：完整Encoder fp32/CKPT0/现有KML，原mean/AdamW；38分配36实际、24GiB同limit/exclusive、唯一job900秒（840+30+30），1epoch/200更新先到。失败停止不重试，不在运行中热改；等待前置最多90分钟、30—60秒只读轮询；排队超60分钟未运行可取消自己本轮排队job。
- 审核授权：01写绑定代码/部署/接口/descriptor SHA、review_complete=true及PASS_FOR_ENGINEERING_PILOT；00重核一致与去重才执行。科学/生产接受仍未完成，修订超范围停下，不请求睡眠中的用户中转。
- 代码现状：R8包23文件/54204bytes元数据/CRC/AST已核，19本地检查按作者记录；R8正式门禁和旧DATA_NOT_READY原件保持，不静默skip_split。新工程代码/descriptor尚未实现或核验，root无SSH/job。
- 本轮改动/检查：仅OVERNIGHT_ENGINEERING_20261105.md、总表/状态/摘要；旧三文件存history/PRE_OVERNIGHT_ENGINEERING_20261105/；查短状态/必要接口确定可独立任务，不改作者源码/数据/共享环境。
- 其余/Git：03/04/05/06/07待命，不重跑工具链阻断/否决项；历史716文件GitHub归档不变，今晚新交付核验后提醒唯一Git窗口精确归档，数据/权重不进Git。
- 下一步：用户分别转发给02、00、01及可选08；当前只是交接计划，明早按各短状态/六行摘要复核实际执行和停止点。
