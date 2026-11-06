"""Publish the exact failed run and NOT_RUN observations, without repairing input."""
from datetime import datetime,timezone
import json
from pathlib import Path
from prepare import sha,save
from review_gate import expected,RESOURCES,WORKLOAD
root=Path(__file__).resolve().parent;received=root/'evidence/received';audit=json.loads((root/'RUN_AUDIT.json').read_text(encoding='utf-8'));job=audit['job_id']
assert audit['status']=='FAILED_SUITE_RAW_EVIDENCE_VERIFIED_NO_RETRY'
def asset(path):
    p=Path(path)
    return dict(path=str(p),bytes=p.stat().st_size,sha256=sha(p))
directory=received/'payload/checks_current_job';cases={}
for case in ('normal','crash'):
    d=directory/case
    cases[case]=dict(accepted_by_original_suite=case=='normal',manifest=asset(d/'manifest.json'),summary=asset(d/'summary.json'),participants=asset(d/'participants.json'),
        rank_reports=[asset(d/f'rank{r}.json') for r in (0,1)],ready=[asset(d/f'ready_rank{r}.json') for r in (0,1)],
        events=[asset(d/name) for name in ('rank0.events.jsonl','rank1.events.jsonl','supervisor.events.jsonl')])
handoff=dict(status='RUN_TERMINAL_FAILED',protocol='S07_R6_ALIGNED_STACK_DIAGNOSTIC_V1',published_utc=datetime.now(timezone.utc).isoformat(),immutable_after_publish=True,
 job_id=job,host=audit['host'],scheduler_state='FAILED',job_exit_code=1,new_jobs=1,retries=0,active_s00_job=None,node_seconds=audit['node_seconds'],scheduler_usage_seconds=audit['scheduler_usage_seconds'],
 resources=RESOURCES,workload=WORKLOAD,source_bindings=expected(root),source_status='UNCHANGED',raw_existing_files_collected_and_verified=True,
 linux_checks_passed=71,linux_checks_skipped=0,communication_suite_passed=False,normal_fixed_tensor_passed=True,
 failed_case='crash',original_checks_error=audit['original_checks_error'],failure_evidence='crash/rank0.json is zero bytes; rank1 reached injected_crash/exit17; supervisor child_failed with [-15,17], both reaped; original reader stopped on JSON parse.',
 case_results=cases,not_run=['collective-timeout','watchdog'],watchdog_observation_status='NOT_RUN',diagnostic_task_complete=False,
 available_trace_inventory_status=audit['available_trace_inventory']['status'],available_readiness_inventory_status=audit['available_readiness_inventory']['status'],
 missing_serialized_cpu_reports=audit['missing_serialized_cpu_reports'],validated_serialized_cpu_snapshots=audit['validated_serialized_cpu_snapshots'],
 scheduler_pids_cleared=True,all_owned_processes_reaped=True,outer_cleanup_signal_actions=audit['outer_cleanup_signal_actions'],
 watchdog_required_files_not_generated=[f'watchdog/rank{r}.{suffix}' for r in (0,1) for suffix in ('python_stack.txt','stack_status.json','installed_python.json')]+['watchdog/'+name for name in ('proc_identity.json','proc_fields.jsonl','proc_summary.json','proc_helper.log')],
 evidence_directory=str(received),analysis_inputs=dict(evidence_dir=str(directory),available_cases=['normal','crash'],not_run_cases=['collective-timeout','watchdog']),
 next_action='S07/coordinator inspect exact crash JSON reader/write/TERM sequence. Preserve original criteria/package. No retry or watchdog-only run under this task card.',
 inference_boundary=audit['inference_boundary'],R12='CLOSED_NO_TRAINING_GAIN_KEEP_ORIGINAL_FP32_BASELINE',formal_training=False,performance_acceptance=False)
for key,path in [('evidence_index',received/'COLLECTION_S00.json'),('archive',root/('evidence/JOB_'+job+'_full_evidence.zip')),('audit',root/'RUN_AUDIT.json'),('review',root/'S01_REVIEW.json'),('deployment_ready',root/'S00_DEPLOYMENT_READY.json'),('original_checks',directory/'checks.json'),('stack_inventory',received/'STACK_INVENTORY.json'),('trace_inventory',received/'DIAGNOSTIC_INVENTORY.json'),('readiness_inventory',received/'READINESS_INVENTORY.json'),('cleanup',received/'job_evidence/cleanup.json')]:handoff[key]=asset(path)
save(root/'RUN_COMPLETE.json',handoff)
save(root/'RUN_PROGRESS.json',dict(job_id=job,state='FAILED_EVIDENCE_COLLECTED',active_s00_job=None,new_jobs=1,retries=0,not_run=['collective-timeout','watchdog'],next='S07/coordinator read frozen failure handoff; no automatic repair/retry'))
report='''# S00 S07 R6唯一执行：crash结果读取失败，watchdog未运行

2050433/cn21338，FAILED/exit1；2026-11-06T06:43:49Z—06:45:34Z，105节点秒，scheduler usage104秒分列。01八项SHA/资源/工作量及原判据明确PASS后，先去重再唯一提交；没有重试、补watchdog或热改冻结包。
新部署104603bytes，SHA82efe84bc36c34db71e107b64f9ff74641b44495d65452d3ec1a535ad5436dc1。R6内包43727bytes/16成员/15文件/14 delivery，SHA32740dcbbce682ee6b245dbb563e7d6ff7a22a11e78d4279db57c4c5b122e7a1；所有源码/实际case的comm_probe、cpu36和observer SHA不变。R6发布时历史未执行字段、旧2041919失败和R12原件保持。

| 层次/阶段 | 本轮实际结果 |
|---|---|
| 包装准备 | 11本地+11 Linux登录夹具、源SHA/LF/AST3.9/bash-n/ZIP CRC通过；不是Gloo验证 |
| 实际job标准库检查 | 27+16+6+6+16=71通过、零跳过，环境检查通过 |
| normal | 原check_case接受，双方exit0；固定fp32 shape4的broadcast/all-reduce等原张量判据通过 |
| crash | rank1到injected_crash/exit17；父记录child_failed、exit_codes[-15,17]、双方回收；原结果读取未完成接受 |
| 整组检查 | checks.status=FAIL，只有normal列入已接受cases；error=Expecting value: line 1 column 1 (char 0) |
| collective-timeout | NOT_RUN；失败后没有继续 |
| watchdog/新Python与proc取栈 | NOT_RUN，未启动observer/helper，不存在本轮栈/proc成果；不可拼旧结果或称观察完成 |

crash/rank0.json实际0bytes，SHA为e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855；rank1.json为10544bytes且stage=injected_crash。rank0原events末行worker_error(stage=broadcast)，父随后发送TERM并回收；空JSON与写入/TERM竞争一致，但这里只确认原件和读取停点，不把推断写成已证实根因。原write_json/监督顺序未修改，也未从events/临时文件重造rank0.json或放宽check_case。S07后续应先定向分析此停点，再由新任务安排取栈，不在本卡补跑。
通信结论与诊断分判：normal小张量通信PASS，原四case整组FAIL；仅已有normal/crash事件流与readiness清单一致，清单明确not_run后两项。STACK_INVENTORY.status=NOT_RUN、diagnostic_task_complete=false。ARMED/EXITED并无本轮watchdog记录，更不能称栈采集通过或多域训练已通。

原生CCS_JOB_ID/host/affinity、nonce/request/raw/ready SHA和30秒新鲜度一致。实际76分配、两完整38物理域，各selected36，共72实际/4预留；DDR总24576MB且同limit/exclusive/HBM0、job300/consumer270/清理15/收尾15，均未扩大或叠加新观察窗口。本次约103.51秒消费者后失败，未耗尽预算。两个域selected0—35与38—73，reserved36—37与74—75。
normal双方和crash rank1现存报告的Torch intra-op=36，原库路径/SHA与同job环境一致；现存23份完整CPU/TID快照核过。crash rank0空报告使其序列化快照缺失，不能把源代码内通过事件冒称完整原始快照。原四case判据未改，normal与crash的pg5/从spawn前起case30保持；后两项没有现场数据。
父/所属14个PID-start_ticks全部退出，global cleanup remaining_live/processes为空，调度PID清空；实际crash父TERM分支已发生，外层兜底没有追加信号动作，未运行watchdog/helper限时与清理分支。不能把本地mock当后者现场通过。

证据JOB_2050433_full_evidence.zip，321066bytes/125文件，SHA2b0dfd047aed0a17e745aefd79a0b150358e499eac1b51c52a7bdc1e6d306b7d。CRC、每文件bytes/SHA、原远端mtime和读取稳定性均核，空文件/所有事件/participants/ready/store/临时残件原样回传。源未漂移，旧受保护原件不变。RUN_COMPLETE.status=RUN_TERMINAL_FAILED绑定两个已到case全部关键原件、本地索引/原checks/审计；存在文件收齐不等于新诊断任务已完成。
本轮无活动S00 job，失败即停；未安装工具、改旧包/候选/阈值/正式门禁、操作其它任务或共享Git暂存/提交推送。R12按协调CLOSED_NO_TRAINING_GAIN结案并保持原fp32基线，没有训练、继续分块搜索或追加A/B。
'''
(root/'RUN_REPORT.md').write_text(report,encoding='utf-8',newline='\n')
print(json.dumps(dict(status='FAILED_TERMINAL_HANDOFF_PUBLISHED',job_id=job,path=str(root/'RUN_COMPLETE.json'),sha256=sha(root/'RUN_COMPLETE.json'),watchdog='NOT_RUN')))
