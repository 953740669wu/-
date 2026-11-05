# 给S00：S01候选确认与首次小试结论

状态：**R2候选身份确认；首次小试在包装器失败；LF修正版身份确认、未重跑**。

- 候选：`S01_LOCAL_RUNNER_R2_20261104`；5个候选文件与总协调接受清单逐字节相同，未改模型/运行器/输入/分配器。
- 目前确认的LF修正包SHA256：`747f9c36354136afa3383a3d836c7e3db7568a043d1712fb2f03765068b4ec5e`。
- 目前确认的包装器SHA256：`72ba04253bc4b68446d642a70bcc0571ee926b71bc81e553c1a385d91dc1709f`。
- 第一次实际执行的包是 `5bb0a6718ec8ae3eb794e7f05f0faae9addd22342df0253833234320427a7616`，不是当前LF包；两者不能混记。
- 最新LF包15条目/14项嵌入清单全部验证；相对失败包，仅包装器CRLF→LF及其嵌入清单哈希变化。没有候选代码改动。

已复核 **job2026356 / cn21338 / FAILED / jobExitCode=2**。真实日志是包装器第3行 `set: pipefail`、`invalid option name`；该包31处CRLF与错误一致。发生在runtime_preflight与runner启动前，模型未到达。`djob_exit=0`只是查询命令成功，不能当作作业成功。S02未提交；已按失败停止，没有自动重试。

资源/配置仍以总协调PILOT_REVIEW为准：新job、38CPU同域、24576MB、900秒；16_adjacent pre+dec、B32、fp32/KML、CKPT0/HBM0、3轮REPS1；包装器780+15秒、每轮180秒、barrier120秒。当前包装器路径约束是账号自有 `S00/PILOT_S01_*/payload`，须与真实S01_RUN和执行记录保持一致，不能套用旧文档的S01/PILOT路径。

当前没有完整模型启动通过或性能/科学数值通过。修正包身份确认不等于允许忽略“失败后停止”安排；由S00/总协调决定是否在原有限范围重新排期，S01不提交或扩大作业。

后续结果请保留：新job终态/资源与包装器退出；本次预检RESULT及依赖/输入SHA；完整run目录的manifest、summary、sync日志/commands/ABORT、逐PID状态、各轮结果/状态。单域三轮正常完成须恰好3个结果JSON+3个状态JSON，rank按实际NUMA ID，不预设d0；失败时原样回传已有文件及缺失清单，不补造输出。

S01将用接受runner.summarize独立重算并对照保存summary；缺域、坏/旧JSON、非零退出、超时或配置/身份不一致一律不能PASS，UNSTABLE原样保留，NODE16_DONE不能单独作为接受依据。

完整复核：[RUN_REVIEW.md](RUN_REVIEW.md)；机器清单：[CANDIDATE_CONFIRMATION.json](CANDIDATE_CONFIRMATION.json)。本窗口未改S00文件、未重新SSH、未提交作业。
