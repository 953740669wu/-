# S00新S07 R6有限取栈部署

内包固定S07_ALIGNED_STACK_R6.zip，43727bytes，SHA32740dcbbce682ee6b245dbb563e7d6ff7a22a11e78d4279db57c4c5b122e7a1，16成员/15文件/14 delivery。observer SHA5b3ad54e675a293e3eb51d292b149c6939bbdc52b68322f340eb76be3b02b875。
原R5外包和2041919 FAIL、R12无收益原件不改。授权来自本轮TASK_CARD与用户，原R6发布时未提交/未授权字段保持。
仅一个job，76分配/两域各36实际共72/留4，DDR总24576MB同limit/exclusive/HBM0。job300秒，原生前置/71检查/环境/四case/观察共享从consumer导入前START起270秒绝对执行截止；所有逐步清理和最终清理共用最晚START+285的界，最多原15秒窗口（TERM2/KILL10），留15秒收尾，不按helper/阶段加窗。冻结worker自身TERM/helper停止顺序与2秒宽限不改。
CHECKS按27 observer+16 readiness+6 diagnostics+6 identity+16 probe，在本job71全通过零跳过后才环境与原run_checks一次。原normal→crash→collective-timeout→watchdog、pg5、spawn前起case30、deadline-5单次dump/repeat=False/exit=False、两rank共用2秒proc窗口全部保持。

## 先去重，再新建部署

```bash
source /etc/profile.d/donaukit_scheduler.sh
RUN=/home/share/dengqingtian/opt/stage4_sessions/S00/S07_STACK_R6_20261106T062352Z
djob -J
find /home/share/dengqingtian/opt/stage4_sessions/S00 -maxdepth 2 -type f -path '*/S07_STACK_R6_*/*' -name submit_once.marker -print
find /home/share/dengqingtian/opt/stage4_sessions/S00 -maxdepth 2 -type f -path '*/S07_STACK_R6_*/*' -name job_id.txt -print
djob -J -l 2041919
cat /home/share/dengqingtian/opt/stage4_sessions/S00/S07_READY_WRAP_R5_20261105T123530Z/job_id.txt
# 有本轮记录则只查原job，不创建新目录绕过；无记录才执行以下一次部署。
test ! -e "$RUN"
mkdir "$RUN"
# 上传新部署ZIP及.sha256后：
cd "$RUN"
sha256sum -c S00_S07_R6_DIAGNOSTIC_DEPLOYMENT.zip.sha256
unzip -q S00_S07_R6_DIAGNOSTIC_DEPLOYMENT.zip
sha256sum -c ARTIFACT_SHA256.txt
/usr/bin/python3 -B prepare.py
/usr/bin/python3 -B -m unittest discover -s tests -v
```

登录只核源码/ZIP/LF/AST3.9/Linux bash-n与11项包装层夹具，不导入真实Torch/Gloo。job中原生CCS_JOB_ID/host/affinity生成nonce/request，原login publisher实时djob生成raw/ready，原30秒新鲜度授权/逐CPU sysfs/每域36核不放宽。全局subreaper及PID/start_ticks跟踪覆盖所有后代/独立session/helper；只向身份复核后的所属PID发信号，不操作外部进程。

## 01同SHA放行后唯一提交

发布S00_DEPLOYMENT_READY后包/源冻结。固定等S01/s07_r6_resume_review_20261106/S01_REVIEW.json明确PASS_FOR_S07_R6_DIAGNOSTIC、review_complete=true，8项bindings和resources/workload逐项一致；旧R5/R12审核不接受。提交前再核原件SHA、队列及唯一marker，将新S01审核原字节上传RUN。

```bash
cd "$RUN"
/usr/bin/python3 -B submit_once.py "$RUN" > login_submit_publish.log 2>&1
```

submit_once独占x创建marker再单次调用（下行为展示，不再手动提交）：

```bash
dsub -J -q q_hpcai -x job -R 'cpu=76,mem=24576MB' -RL 'mem=24576MB' -a 'numa[count=2,distribution=pack]' -T 300 --env none --cwd "$RUN" -oo "$RUN/job.log" bash "$RUN/run_s07_diag_job.sh" '<本轮S01原件SHA>'
```

观察RUNNING后原producer只发布一次。不从JSON伪造job/PID/start_ticks，不设置候选内部S07_CASE_DEADLINE_NS或S07_PROC_TASK。断线或提交ID不明保留marker查同一job，不重提；排队60分钟仍未启动可核实后只取消此job，不重试。依赖每30—60秒固定文件查，最多90分钟，不占节点等待。

## 原件收集与分层结果

真实终态后一次：

```bash
/usr/bin/python3 -B collect_evidence.py "$RUN"
```

回传JOB_<job>_full_evidence.zip及原bundle_receipt.json；不要把收集日志写进正在索引的目录。完整保留两rank Python栈/stack_status/installed_python，proc identity/fields/summary/helper.log、父helper PID/kill/returncode/reaped，以及原events/summary/participants/ready/store/全部tmp残件/命令/资源/退出/逐步与全局清理。按实际读取bytes/SHA/远端mtime索引，若读取时变化也明示；缺、空、权限错误、截断不补造，调度PID未清空仍保存并标识。
DIAGNOSTIC_INVENTORY/READINESS_INVENTORY/STACK_INVENTORY各自独立；ARMED不证明有栈、EXITED不证明proc字段齐、未到injected_hang则原watchdog/整组仍FAIL。原run_checks判据不改，即使诊断可读也不提升通信结论。失败立即停止、不补项、不修payload后再提。全部通过仍只是小张量通信，非同步模型训练或多域性能接受。
