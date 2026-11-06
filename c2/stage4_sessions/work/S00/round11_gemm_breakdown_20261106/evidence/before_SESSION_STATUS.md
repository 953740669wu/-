# S00简短状态

- 更新/轮次：2026-11-06；R9_PROFILE5执行与完整取证完成；目录round9_profile5_20261106。
- 终态：唯一2048959/cn21338 SUCCEEDED/jobExitCode0，PROFILE5_COMPLETE_NOT_PERFORMANCE_ACCEPTANCE；仅5连续更新/320帧，1—2预热、3—5采样，无重试、无活动S00 job。
- 放行/身份：S01完整PASS_FOR_ENGINEERING_PROFILE5、八份SHA/资源一致；审核SHA=596b45e77308f5aca05799a5a613d43048e294f9db70411069ca3e2135a6a5da。提交前实际队列/新marker/原包/数据再核，一次dsub/原生job交接完成，未操作其它任务。
- 数据/模型：原descriptor SHA=b88ea9745147acf7fa70d51dc27c727f22f14e98af5dff1b80a9047e95648cd6；固定16单元/1600工程帧和原scale不变，仅原seed0前320帧训练。初始化、frame顺序/ID SHA、mask SHA、KML计数与2043445 first5参照一致；15/15 loss原门槛通过，max_abs/relativeL2均0。没有重跑旧5315或扩大数值结论。
- 采样：3trace+3events齐全，单次10845事件/149 KML包裹，trace1533488/1556905/1555946bytes，events9122/9119/9120bytes，合计4673700bytes，所有原SHA及50000事件/256标记/8MiB+1MiB上限通过，无截断/回退/补跑。
- CPU/资源：38物理核授权/实际selected36留2、DDR24576MB同limit/exclusive/HBM0；job900/全入口840/清理30/留30/内部720不变。19次完整TID快照全在36核内，最多37 TID（非37核），实际Torch intra36/interop608未加setter；训练KML745/进程843调用，库身份原件齐。
- 时间/边界：应用wall82.124880秒；带标记训练内25.088423，独立profiler外层16.014551，诊断2.180670，保存恢复7.453861，其余分项见RUN_AUDIT。原阶段wall/CPU self与嵌套total分别保留；KML包裹非精确内核时间，内部扰动UNKNOWN，不称稳态吞吐/加速或跨节点性能对比。
- checkpoint/暴露：新profile_2048959/checkpoints/final.pt留远端，456134879bytes，SHA=2d7dfb1ac8846f4101107924d7f4810b142285dd831b55628d55d686b6e6e64a；模型/AdamW/RNG/cursor/身份精确恢复、前向差0、额外更新0。新ledger在profile_JOB目录，5 confirmed_updates与steps帧一致，in_flight=null；旧ledger/旧checkpoint/source前后SHA不变。
- 清理/成本：所属进程自然退出，all_reaped=true、remaining_live/processes空、调度PID清空；未现场触发TERM/KILL故障分支。UTC03:21:22—03:22:56，新增94节点秒/usage93分列；已知累计24job/1386节点秒。
- 完整证据：evidence/JOB_2048959_evidence.zip，1066705bytes/105文件，SHA=bb17a1ff559ffe328ae95f23db9f3126158a771052e3350ef435166755a88f5c；归档bytes/SHA/原mtime索引全过，missing=[]/source_status=UNCHANGED。RUN_COMPLETE.json锚定received目录、索引及6采样SHA；RUN_AUDIT.json/RUN_REPORT.md为只读原件核查，不重跑模型。
- 保留/下一步：原PROFILE_READY历史授权字段未改；旧正式DATA_NOT_READY/无正式split/subject/val/test边界保留，未来追溯排除工程暴露subject进入最终test。交01/02/协调按新证据定向分析，不自动再提job/改候选或阈值。精确待归档清单ARCHIVE_FILES.txt，未操作共享Git暂存/提交推送。
- 连接续接：入口恢复后使用新指纹uz4s0MHoKxwByo7kK+KaY6VXwIG7WqYEphR7AgqiG7I；沿用用户对该入口所有指纹的明确持续信任，独立新pool在本轮evidence/known_hosts_r9_confirmed_pool，旧记录保留，严格校验启用。
