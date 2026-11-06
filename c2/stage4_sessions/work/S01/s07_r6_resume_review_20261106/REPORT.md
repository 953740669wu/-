# S01 S07 R6 恢复执行专项复核

结论：**PASS_FOR_S07_R6_DIAGNOSTIC，review_complete=true，无前置阻断项。** S00在提交前复核同SHA、实际队列及新独占marker后，可直接执行本卡唯一诊断，无需用户中转。仅审核R6新增观测与新包装边界；未代改作者源码、重复旧完整审核或提交作业。

R12按当前任务卡结论CLOSED_NO_TRAINING_GAIN，保持原fp32基线；保留旧通过/无收益原件，不集成分块候选，不换块宽或精度继续搜索，不追加A/B。本轮未重新审核R12数值或重训。

## R6时钟、文件与所属进程

R6内包43727bytes、16成员（15文件+evidence目录）、14 delivery均与SOURCE_MANIFEST一致，CRC/LF/Python3.9 AST通过。minimal.diff精确对应原R4 probe；原函数仅supervise/worker/run变化，原run_checks.py、CPU36合同、四组旧测试和allocation模板共7项逐字不变。旧2041919整组FAIL与原R6发布时未运行字段不改。

只有watchdog设置StackDump；原worker先验原生CCS_JOB_ID/CPU36/继承权限并绑本rank selected36，保留worker_ready后才arm。绝对目标来自原spawn前case时钟S07_CASE_DEADLINE_NS−5秒，只调用一次dump_traceback_later、repeat=False/exit=False；设置前后采全部可见TID边界。独占打开stack文件并保留FD，cancel先于close；取消错误保留文件引用和错误，异常仍进入原父清理。打开前/后错过目标都MISSED，不从ready/import重开计时。

父Popen的两worker PID进入本任务独立session helper；helper核原生job、实际父PID、worker PPID/session/start_ticks，并在采样前后复核身份和CPU。只在继承的selected集合内切换rank，不触预留核，不读其它PID。两个rank共用[目标,目标+2秒]，alarm及各段检查同一绝对截止；TimeoutError不吞为权限错误。每字段最多64KiB、最多16个FD线索；EMPTY/ERROR/TRUNCATED/MISSED/权限拒绝和部分文件原样记录，不安装、提权或扩大采样。

父只poll，到截止kill自己的helper，不helper wait/join；原worker TERM先发、再停helper，原2秒共享宽限不变。helper仍未退出记UNREAPED，交外层subreaper清理，无额外helper窗口。installed_python只读已加载distributed_c10d/rendezvous两个小Python文件，各<=1MiB，保存路径/bytes/mtime/SHA及静态调用位置；不是已执行分支或C++调用栈的证明。

## 原判据、资源与预算

原normal→crash→collective-timeout→watchdog同job各一次；pg timeout5秒，case从原spawn前起30秒，ready/注入点不改。normal要求固定小张量exact结果；crash要求rank1到injected_crash且exit17；collective-timeout要求真实Gloo broadcast超时且rank1 injected_hang；watchdog要求code124/deadline且两rank均到injected_hang。初始化阻塞未到注入不能由截止或清理成功补PASS。任何步骤失败停止后续，不单跑watchdog拼旧三项，不重试/热改后重提。

新CHECKS为27 observer+16 readiness+6 diagnostics+6 identity+16 probe，共71；本job必须全部通过且零跳过，之后才环境核验和原run_checks。作者Windows本地70过1 Linux跳过仅用于覆盖判断，登录包装fixture也不能替代计算job内71检查。

同节点两个完整NUMA域，每域38分配/36实际留2，总76分配、72实际、4预留；DDR请求/limit总24576MB（不是每rank各24GiB）、exclusive/HBM0。调度命令numa[count=2,distribution=pack]/300秒；原生CCS_JOB_ID/host/affinity→nonce/request→登录实时djob raw/ready与30秒新鲜度授权保持。load_allocation复核每CPU拓扑/38物理核，worker所有相关TID非空子集selected36且实际Torch intra-op=36。无KML/LD_PRELOAD，原CPU36环境不放宽。

START在consumer其它导入前取得，原生授权、71检查、环境、四case及观测共用START+270绝对执行截止；逐步run_step与最终cleanup都不晚于START+285，统一TERM2/KILL10在原<=15秒cap内，留15秒收尾到job300。单项limit只会收紧剩余预算；270秒到期打断后也不能为helper或阶段再加窗口。原worker内部清理时序不改。PR_SET_CHILD_SUBREAPER/跨session后代/PID-start_ticks复核覆盖全部所属helper，逐步及最终清理保存实际remaining/reaped；真实不可中断I/O等故障仍须如实留残留。

run_s07_diag_job.sh检查64位审核SHA参数，env-i显式转发S00_REVIEW_SHA与原生job、清除优化/注入环境；Python仅-B，外层拒绝-O/PYTHONOPTIMIZE。submit_once先核具体审核及部署字节，再独占x创建新marker、一次dsub；新S07_STACK_R6_20261106T062352Z根，不复用旧job/marker/审核。模糊提交只查原job，排队超60分钟仅可核实后取消自己的未启动job，不重提。

## 取证与分层结论

新stack_inventory独立核两rank非空Python traceback/目标时间/安装源码，父helper事件PID/退出回收、target PPID/session/start_ticks/CPU前后身份及helper全部TID、两rank同2秒窗口和8条原始proc字段。ARMED不代表栈已写，EXITED不代表字段齐；缺空/ERROR/EMPTY/TRUNCATED/超窗/身份不全均记观察不完整。trace inventory明确AVAILABLE_TRACES_ONLY并保留not_run；不能把部分case可读当完整suite。

通信结果仍来自冻结run_checks原判据；COLLECTION_S00分列original_communication_result/communication_passed、diagnostics/readiness/stack_observation、退出/资源和调度PID是否清空。诊断完整可能同时通信FAIL，通信通过也不能据此宣称完整取栈。全部通过仍仅固定小张量通信，不是多域同步模型训练或性能接受。

collect_evidence原样收两rank python_stack/stack_status/installed_python、proc identity/fields/summary/helper.log、父helper PID/kill/returncode/reaped，以及events/summary/participants/ready/store/tmp残件、命令/调度/逐步与全局清理。索引实际snapshot bytes/SHA/远端mtime/changed_during_read；终态PID未清空、空栈或部分tmp也保留并明确标识，不能补造/丢弃失败原件。收集器不重写候选结论。

## 验证证据、未运行与交接

S01核原作者71方法与70过1跳过原件及隔离包检查，覆盖一次真实本地faulthandler（CPU guard夹具）、所属标准库挂起helper回收、绝对时钟/MISSED/取消FD/权限和身份负例；未重跑该套件。S00新外包28成员（27文件+目录）/25源索引，核2项原封helper及唯一ownership时限diff。作者包装检查最终本地11/11、Linux登录11/11，包含晚步骤不得重置清理截止、原样收空/部分文件及未清空PID的负例；LF/bash-n/AST/SHA收据齐全。登录未导入真实Torch/Gloo。

S01独立重算全部内/外包字节与索引、检查唯一diff/AST/旧判据复用，并仅从自己冻结副本导入stdlib review_gate，验证拟发布原件与实际S00消费者兼容。76份冻结输入复核无漂移，没有重复模型/旧5315或作者整套检查。

本轮S01 0提交/0远端连接/0Torch-Gloo或模型运行。真实Linux71、实际CPU/TID继承、Gloo停点与栈/proc/现场信号清理仍待唯一job；本轮未触发真实故障清理分支。没有依据预先称通信通过、诊断完成、根因已修复或同步训练/吞吐接受。

| 执行绑定 | SHA256 |
|---|---|
| inner_package_sha256 | 32740dcbbce682ee6b245dbb563e7d6ff7a22a11e78d4279db57c4c5b122e7a1 |
| inner_manifest_sha256 | 1b2dec1148d74844ca826e21244069a54a009d8935242fd325fc0ad744083f46 |
| observer_sha256 | 5b3ad54e675a293e3eb51d292b149c6939bbdc52b68322f340eb76be3b02b875 |
| comm_probe_sha256 | c9efa0c9d4ba05c8fb4501ce75f2dd60e6268d732c707cc3beef133330a356dd |
| observation_contract_sha256 | 448cad1a857165c74d0cb241e32b18480d1495ec995704f9f6c5de2208712dde |
| deployment_package_sha256 | 82efe84bc36c34db71e107b64f9ff74641b44495d65452d3ec1a535ad5436dc1 |
| deployment_source_manifest_sha256 | b55408714ac60709467e1b94c67741d664341a720d678cf0e4c2d49e043fce75 |
| task_card_sha256 | 9a2c41f21f6f5be38ece42e082e3c221bb5593dbbbc84dbb302ce66ae33fff36 |

原判据run_checks SHA=7b7cc96edd9401981a61db5122bf785e3e2348a41cda5363ba5d2ea4b0217d07。完整输入路径/bytes/SHA见FROZEN_INPUTS.json；具体检查见code_review.json/deployment_review.json；固定S01_REVIEW.json发布后不热改。

只写S01本新目录及自身SESSION_STATUS.md/六行ROUND_DELTA.md。归档精确清单见ARCHIVE_FILES.json，排除ZIP、frozen重复副本、数据/权重/环境；未操作共享Git暂存/提交/推送。00直接读固定审核，在核同SHA/实时队列/新marker后唯一执行并跟踪终态；S01本轮复核完成，不后台监控。
