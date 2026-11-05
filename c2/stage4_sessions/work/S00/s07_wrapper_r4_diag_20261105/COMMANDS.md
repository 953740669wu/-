# S00 wrapper R4：新S07诊断内包，待协调核具体包

本轮只准备，未SSH、未调用调度CLI、未提交job或模型/通信。S07内包为R3，S00部署包装层为R4；旧wrapper R3、2040233失败及2040363结果保留。诊断根因未定，不称已修复。

## 固定身份与预算

- 内包必须叫S07_INIT_DIAGNOSTIC_R3.zip，31262bytes，SHA256=af2725e24d0bd8b2183f1d7bc8b6aae79f801b7b83b640b41645e822e0c23f45；12文件+evidence/空目录，SOURCE_MANIFEST含11项delivery。旧R2包/旧SHA不可替代。
- prepare在解压前核精确成员及11项bytes/SHA，拒绝已有payload；计算端再次核内包SHA及12项源文件，不改候选。
- 原scheduler_handoff.py与bounded_round_step.py字节不变。原生CCS_JOB_ID只继承，原nonce/request/raw/ready/30秒交接、76核授权/主机/资源/逐核sysfs及每域36核检查保持。
- 单节点两完整38物理核域，76分配，每域36实际留2；DDR24576MB且同limit，exclusive，HBM0，job300秒。消费者只建立一次270秒deadline；新增6项诊断检查上限30秒，原6/16项各45秒上限及环境60秒都消耗同一剩余预算，未叠加新窗口。
- 一个原run_checks入口，normal→crash→collective-timeout→watchdog，normal失败立即停止；原pg_timeout=5、每case deadline=30、原有界清理不变。不临时重跑normal、不调参/安装/换环境。

## 外部前提

登录节点实际存在/etc/profile.d/donaukit_scheduler.sh，可用CLI为/opt/batch/cli/bin/dsub及djob。仅登录端source该profile；登录/计算端共享同一全新目录，单producer，时钟满足原30秒新鲜度。计算端有原生作业身份、Linux sysfs/affinity、/usr/bin/python3、/usr/bin/bash，不要求登录profile或C++编译器。

沿用R4解释器/home/share/dengqingtian/opt/stage4_sessions/S00/ENV_20261104T130730Z_R4/venv/bin/python3、Torch2.7.1+cpu路径/home/share/songzhenlong/eitfm/sw/torch_kml及既有Gloo。LD_LIBRARY_PATH仍为/opt/HPCKit/kml-lib/sme/kblas/multi:/opt/HPCKit/kml-lib:/opt/HPCKit/bisheng-lib；无LD_PRELOAD/KML shim或模型/HBM。依赖/身份不符即停，不自动修复。

## 将来明确安排一个新job后的命令

以下是待审核部署入口，本轮没有执行。先核本轮DEPLOYMENT_RECEIPT.json所列外包SHA，确认远端队列及S00既有提交记录，避免新建目录掩盖已提交任务。

```bash
set -euo pipefail
RUN=/home/share/dengqingtian/opt/stage4_sessions/S00/S07_INIT_DIAG_R4_<新的UTC标识>
test ! -e "$RUN"
mkdir "$RUN"
# 将核准外包上传为$RUN/S07_S00_DIAGNOSTIC_WRAPPER_R4.zip，先与DEPLOYMENT_RECEIPT.json核SHA。
unzip -q "$RUN/S07_S00_DIAGNOSTIC_WRAPPER_R4.zip" -d "$RUN"
cd "$RUN"
sha256sum -c ARTIFACT_SHA256.txt
/usr/bin/python3 -B prepare.py
# 本地/登录侧仅部署与交接模拟；28项候选检查须在同一实际job内全部通过且无Linux跳过。
/usr/bin/python3 -B tests/test_deployment.py
/usr/bin/python3 -B tests/test_scheduler_handoff.py
test -f /etc/profile.d/donaukit_scheduler.sh
source /etc/profile.d/donaukit_scheduler.sh
djob -J > queue_review_before_submit.raw
# 提交程序先独占写marker，单次dsub；观察RUNNING后立即原publisher，不等人工回复。
/usr/bin/python3 -B submit_once.py "$RUN" > login_submit_publish.log 2>&1
JOB=$(cat job_id.txt)
djob -J -l "$JOB" > scheduler_observed_after_publish.json
```

submit_once.py内精确dsub参数为：

```bash
dsub -J -q q_hpcai -x job -R 'cpu=76,mem=24576MB' -RL 'mem=24576MB' \
  -a 'numa[count=2,distribution=pack]' -T 300 --env none --cwd "$RUN" \
  -oo "$RUN/job.log" bash "$RUN/run_s07_diag_job.sh"
```

publisher仅一次；PENDING观察不是实验重试，不提前启动30秒发布等待。CLI/发布失败后不重发或重提，消费者原窗口内拒绝并停止，观察终态后收集。消费日志包含28项逐命令开始/结束/退出/清理回执，失败步仍保留独立receipt。

在同一登录环境确认实际终态且调度PID字段清空后，执行一次终态收集：

```bash
/usr/bin/python3 -B collect_evidence.py "$RUN"
```

回传JOB_<job>_full_evidence.zip和bundle_receipt.json，标准输出回执保留在会话传输记录。不要把仍在写入的收集日志重定向进待索引目录。收集器在登录端、job终态后执行，不占消费者270秒或追加计算资源。

## 事件原件及接受边界

每个已到达case回传rank0.events.jsonl、rank1.events.jsonl、supervisor.events.jsonl全文件，以及原rank JSON/log、commands、manifest、summary/checks、S00逐step时间/清理、原授权及终态。所有原文件以bytes/SHA/远端mtime_ns索引，包含截断、错误及原内包；不只摘录最后事件。尚未到达case另列NOT_RUN。

DIAGNOSTIC_INVENTORY.json独立于原通信结论。TRACE_WRITE_ERROR、缺流/身份/父spawn或reap行、无法解析/截断行、已观测begin未闭合等均标为不完整；仍把全部原字节写入ZIP，不以证据错误跳过收集。缺end不等于永久卡住；日志无全局序号，检查只能验证可观察格式/边界/配对，不能排除整对事件同时遗漏。待原事件和监督信号一起分析，不由清单自动定位根因。

事件间隔包括flush/fsync及共享盘I/O，不作为纯导入/通信性能。共享盘刷盘成本未现场测量，不许诺Python层硬实时保证；调度300秒总限保持。Windows本地候选28项为27通过/1 Linux跳过，不能替代新job的28全通过；旧2040233的Linux22项属于历史，不挪作本轮通过。
