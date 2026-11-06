# R12唯一共享预算链

新ROOT=/home/share/dengqingtian/opt/stage4_sessions/S00/S02_DW_R12_20261106T053753Z；payload新解包，旧job/marker不可复用。
授权来自TASK_CARD.md和用户本轮任务，S02_R12_READY原历史execution_authorized=false不改。
仅target→strict5(两侧各5)→perf_baseline25→perf_candidate25，共最多60完整更新、一对A/B。
38分配/实际36留2，单NUMA，DDR24576MB同limit/exclusive/HBM0；总job900秒。
全入口含原生前置门禁共用绝对START+840截止，清理最多30秒、最晚START+870，留30秒收尾；不能各阶段重开840。
调用冻结run_ab_proposal.sh，不热改payload。非优化Python，run_job.sh env-i无PYTHONOPTIMIZE，应用-B，无-O/-OO，assert启用。

## 只读去重后部署，不在登录节点跑矩阵

```bash
source /etc/profile.d/donaukit_scheduler.sh
RUN=/home/share/dengqingtian/opt/stage4_sessions/S00/S02_DW_R12_20261106T053753Z
djob -J
find /home/share/dengqingtian/opt/stage4_sessions/S00 -maxdepth 2 -type f -path '*/S02_DW_R12_*/*' -name job_id.txt -print
find /home/share/dengqingtian/opt/stage4_sessions/S00 -maxdepth 2 -type f -path '*/S02_DW_R12_*/*' -name submit_once.marker -print
# 有本轮记录只查原job；无记录才新建并上传冻结包及.sha256。
test ! -e "$RUN"
mkdir "$RUN"
cd "$RUN"
sha256sum -c S00_R12_DW_AB_DEPLOYMENT.zip.sha256
unzip -q S00_R12_DW_AB_DEPLOYMENT.zip
sha256sum -c ARTIFACT_SHA256.txt
/usr/bin/python3 -B prepare.py
/usr/bin/python3 -B -m unittest discover -s tests -v
timeout --signal=TERM --kill-after=5s 60s env -u LD_PRELOAD PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 /home/share/dengqingtian/opt/stage4_sessions/S00/ENV_20261104T130730Z_R4/venv/bin/python3 -B inspect_metadata.py --output LOGIN_METADATA_CHECK.json
timeout --signal=TERM --kill-after=5s 55s /usr/bin/python3 -B check_old_inputs.py --phase BEFORE
timeout --signal=TERM --kill-after=5s 45s /usr/bin/python3 -B recheck_fixed_inputs.py > FIXED_INPUTS_BEFORE.json
```

发布S00_DEPLOYMENT_READY后源码/包冻结。等S01/round12_dw_ab_review_20261106/S01_REVIEW.json明确PASS_FOR_ENGINEERING_R12_AB、review_complete=true，bindings全部10项等于required_review_bindings，resources和workload逐项相同。无PASS/错SHA/旧审核不能提交。
提交前再次核实际队列/全部R12 marker、部署/代码/任务卡/原descriptor/元数据及审核原件SHA；将S01_REVIEW原字节上传新ROOT。

```bash
cd "$RUN"
/usr/bin/python3 -B submit_once.py "$RUN" > login_submit_publish.log 2>&1
```

submit_once独占x创建marker后只调用一次下列命令（展示，不可手动再提）：

```bash
dsub -J -q q_hpcai -x job -R 'cpu=38,mem=24576MB' -RL 'mem=24576MB' -a 'numa[count=1,distribution=pack]' -T 900 --env none --cwd "$RUN" -oo "$RUN/job.log" bash "$RUN/run_job.sh" '<本轮S01原件SHA>'
```

模糊提交/断线保留marker，查原job禁止重提；排队60分钟且未启动仅可复核取消自己的一个job。依赖按30—60秒固定文件轮询、90分钟上限，不占计算节点等待。

## 停止与完整收集

任何target数值/ABI失败关闭固定候选，不转strict/perf；strict未PASS不能转性能。单侧perf未25步/恢复未通过则无完整A/B；INCOMPLETE不能缩步补PASS。保留原错误和所有部分文件，不重试或换tile/精度。baseline逻辑149/native149/target_full12；candidate逻辑149/native161/tiles24/dispatch12，逐步核验。
Owned子reaper/PID-start_ticks覆盖全部所属后代，统一TERM15/KILL15窗口；自然退出与现场信号分支分别记录。

```bash
cd "$RUN"
timeout --signal=TERM --kill-after=5s 55s /usr/bin/python3 -B check_old_inputs.py --phase AFTER
timeout --signal=TERM --kill-after=5s 45s /usr/bin/python3 -B recheck_fixed_inputs.py > FIXED_INPUTS_AFTER.json
/usr/bin/python3 -B collect_evidence.py "$RUN"
```

所有target/strict/perf_baseline/perf_candidate/dw_ab原件、逐步/metrics/CPU/库/import/native计数、RSS/HWM/账本、runner退出/timeout/调度/清理完整归档。缺项/失败原样回传；checkpoint仅远端path/bytes/SHA/零额外更新恢复，不下载。收集日志不可写进正在索引的目录。
若完整A/B完成，只报本次后20步中位/范围及原25步、training/diagnostic/wall分项；RSS是性能进程scope的process-lifetime HWM，非逐步独占/全job峰值。无正式split/subject/val/test，不作生产/稳态加速接受。
