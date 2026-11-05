# S00 wrapper R5：S07双方就绪R4内包，待协调核具体包

本轮只准备，未SSH、未调用调度CLI、未提交job或模型/通信。S07内包为R4，S00部署包装层为R5；旧wrapper R4及2040233/2041165失败保留。诊断根因未定，不称已修复。

## 固定身份与预算

- 内包必须叫S07_READY_SYNC_R4.zip，34295bytes，SHA256=d39ae26f2b29d53f733bdef937832edeeec4bf4a468adf2d0eff0dbe5fb39c45；13文件+evidence/空目录，SOURCE_MANIFEST含12项delivery。旧R2包/旧SHA不可替代。
- prepare在解压前核精确成员及12项bytes/SHA，拒绝已有payload；计算端再次核内包SHA及13项源文件，不改候选。
- 原scheduler_handoff.py与bounded_round_step.py字节不变。原生CCS_JOB_ID只继承，原nonce/request/raw/ready/30秒交接、76核授权/主机/资源/逐核sysfs及每域36核检查保持。
- 单节点两完整38物理核域，76分配，每域36实际留2；DDR24576MB且同limit，exclusive，HBM0，job300秒。消费者只建立一次270秒deadline；新增16项readiness检查上限30秒，6项诊断检查仍上限30秒，原6/16项各45秒上限及环境60秒都消耗同一剩余预算，未叠加新窗口。
- 一个原run_checks入口，normal→crash→collective-timeout→watchdog，normal失败立即停止；原pg_timeout=5、每case deadline=30、原有界清理不变。不临时重跑normal、不调参/安装/换环境。

## 外部前提

登录节点实际存在/etc/profile.d/donaukit_scheduler.sh，可用CLI为/opt/batch/cli/bin/dsub及djob。仅登录端source该profile；登录/计算端共享同一全新目录，单producer，时钟满足原30秒新鲜度。计算端有原生作业身份、Linux sysfs/affinity、/usr/bin/python3、/usr/bin/bash，不要求登录profile或C++编译器。

沿用R4解释器/home/share/dengqingtian/opt/stage4_sessions/S00/ENV_20261104T130730Z_R4/venv/bin/python3、Torch2.7.1+cpu路径/home/share/songzhenlong/eitfm/sw/torch_kml及既有Gloo。LD_LIBRARY_PATH仍为/opt/HPCKit/kml-lib/sme/kblas/multi:/opt/HPCKit/kml-lib:/opt/HPCKit/bisheng-lib；无LD_PRELOAD/KML shim或模型/HBM。依赖/身份不符即停，不自动修复。

## 将来明确安排一个新job后的命令

以下是待审核部署入口，本轮没有执行。先核本轮DEPLOYMENT_RECEIPT.json所列外包SHA，确认远端队列及S00既有提交记录，避免新建目录掩盖已提交任务。

```bash
set -euo pipefail
RUN=/home/share/dengqingtian/opt/stage4_sessions/S00/S07_READY_WRAP_R5_<新的UTC标识>
test ! -e "$RUN"
mkdir "$RUN"
# 将核准外包上传为$RUN/S07_S00_READY_WRAPPER_R5.zip，先与DEPLOYMENT_RECEIPT.json核SHA。
unzip -q "$RUN/S07_S00_READY_WRAPPER_R5.zip" -d "$RUN"
cd "$RUN"
sha256sum -c ARTIFACT_SHA256.txt
/usr/bin/python3 -B prepare.py
# 本地/登录侧仅部署与交接模拟；44项候选检查须在同一实际job内全部通过且无Linux跳过。
/usr/bin/python3 -B tests/test_deployment.py
/usr/bin/python3 -B tests/test_readiness_collection.py
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

publisher仅一次；PENDING观察不是实验重试，不提前启动30秒发布等待。CLI/发布失败后不重发或重提，消费者原窗口内拒绝并停止，观察终态后收集。消费日志包含44项逐命令开始/结束/退出/清理回执，失败步仍保留独立receipt。

在同一登录环境确认实际终态且调度PID字段清空后，执行一次终态收集：

```bash
/usr/bin/python3 -B collect_evidence.py "$RUN"
```

回传JOB_<job>_full_evidence.zip和bundle_receipt.json，标准输出回执保留在会话传输记录。不要把仍在写入的收集日志重定向进待索引目录。收集器在登录端、job终态后执行，不占消费者270秒或追加计算资源。

## 事件原件及接受边界

每个已到达case回传rank0.events.jsonl、rank1.events.jsonl、supervisor.events.jsonl全文件，以及原rank JSON/log、commands、manifest、summary/checks、S00逐step时间/清理、原授权及终态。所有原文件以bytes/SHA/远端mtime_ns索引，包含截断、错误及原内包；不只摘录最后事件。尚未到达case另列NOT_RUN。

DIAGNOSTIC_INVENTORY.json独立于原通信结论。TRACE_WRITE_ERROR、缺流/身份/父spawn或reap行、无法解析/截断行、已观测begin未闭合等均标为不完整；仍把全部原字节写入ZIP，不以证据错误跳过收集。缺end不等于永久卡住；日志无全局序号，检查只能验证可观察格式/边界/配对，不能排除整对事件同时遗漏。待原事件和监督信号一起分析，不由清单自动定位根因。

事件间隔包括flush/fsync及共享盘I/O，不作为纯导入/通信性能。共享盘刷盘成本未现场测量，不许诺Python层硬实时保证；调度300秒总限保持。Windows本地候选44项为43通过/1 Linux跳过，不能替代新job的44全通过；旧2041165的Linux28项属于历史，不挪作本轮通过。

## 新就绪证据的终态核验

S00执行层不写participants.json或ready_rank*.json，不设置S07_CASE_DEADLINE_NS；它们只能由冻结候选的父监督/真实worker产生。本轮只做本地准备，未来也必须先核实际队列和已有提交，不能以新建目录绕过去重。

READINESS_INVENTORY.json与DIAGNOSTIC_INVENTORY.json分别保存，不替代原checks/summary判据。终态收集器读取participants.json、ready_rank0.json、ready_rank1.json和全部*.tmp*残件，记录原bytes/SHA/mtime；即使缺失、半JSON、类型错误、旧token或未完成发布仍完整打包，不删除、不覆盖、不从残件补造ready。

只读核对manifest的run/job/ready_token、当前收集job、父summary真实PID及spawn事件、participants精确字段和绝对deadline，再检查每rank自己的after_framework→preparation_complete→ready_published→both_ready→init尝试顺序。both_ready/init记录必须早于原绝对deadline；deadline相对supervisor_begin事件不超过30秒，不能改成就绪后重新计时。日志不能独立恢复进程私有环境；来源仍由冻结代码/现场授权共同约束。

跨rank不比较ready_published事件先后，不用文件mtime冒充精确发布时间。原子os.replace发生在同rank该日志之前，对方可在日志落盘前读到合法ready；这种合法交错有专门本地正例。不完整清单只表示证据尚不足，不能据缺行认定永久卡住或将就绪失败当故障注入成功。

未来同一job内检查顺序为16 readiness + 6 diagnostics + 6 identity + 16 probe=44，无Linux跳过；然后原environment和一次原四case入口。新增检查不增加270秒消费者预算，不延长300秒job、5秒通信或原spawn前起算30秒监督/清理。本地43过1跳过及模拟就绪不能称真实Gloo通过。
