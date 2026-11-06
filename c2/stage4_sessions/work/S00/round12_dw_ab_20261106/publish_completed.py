"""Publish audited terminal R12 evidence; no further cluster actions."""
from datetime import datetime,timezone
import json
from pathlib import Path
from prepare import sha,save
from review_gate import expected,RESOURCES,WORKLOAD
root=Path(__file__).resolve().parent;received=root/'evidence/received';audit=json.loads((root/'RUN_AUDIT.json').read_text(encoding='utf-8'))
assert audit['status']=='R12_FULL_CHAIN_COMPLETE_EXPLORATORY_ONLY' and audit['outcome']['complete']
job=audit['job_id'];performance=audit['performance'];baseline=performance['baseline'];candidate=performance['candidate']
change=(candidate['observed20_median_seconds']/baseline['observed20_median_seconds']-1)*100
def asset(path):
    p=Path(path)
    return dict(path=str(p),bytes=p.stat().st_size,sha256=sha(p))
phases={}
for phase,info in audit['phases'].items():
    directory=received/'payload/outputs'/(phase+'_'+job)
    record=dict(status=info['status'],result=asset(directory/('screen_result.json' if phase=='target' else 'result.json')),metric_count=info['metric_count'],max_abs=info['max_abs'],cpu_snapshots=info['cpu_snapshots'])
    if phase!='target':record.update(steps=asset(directory/'steps.jsonl'),ledger=asset(directory/'EXPOSURE_LEDGER.json'),completed_update_cycles=info['completed_updates'],optimizer_updates_total=info['optimizer_updates_total'])
    phases[phase]=record
complete=dict(status='RUN_COMPLETE',protocol='ENGINEERING_DW_TILES_R12_AB_V1',published_utc=datetime.now(timezone.utc).isoformat(),immutable_after_publish=True,
 job_id=job,host=audit['host'],scheduler_state=audit['scheduler_state'],job_exit_code=audit['job_exit_code'],new_jobs=1,retries=0,active_s00_job=None,
 outcome='R12_COMPLETE_EXPLORATORY_NOT_SPEEDUP_ACCEPTANCE',full_model_updates=60,resources=RESOURCES,workload=WORKLOAD,source_bindings=expected(root),
 phase_order=['target','strict','perf_baseline','perf_candidate'],phases=phases,node_seconds=audit['node_seconds'],scheduler_usage_seconds=audit['scheduler_usage_seconds'],
 performance={role:{k:value[k] for k in ('observed20_median_seconds','observed20_range_seconds','all25_training_seconds','timing','process_lifetime_HWM_MiB','rss_scope')} for role,value in performance.items()},
 candidate_observed20_median_change_percent=change,performance_conclusion='NO_TRAINING_GAIN_IN_THIS_SINGLE_PAIR; candidate slower median; coordinator disposition pending, no integration or new search',
 checkpoints={role:value['checkpoint'] for role,value in performance.items()},checkpoint_transfer='REMOTE_ONLY_NOT_DOWNLOADED',extra_optimizer_updates_in_restore=0,
 source_status='UNCHANGED',old9_and_fixed36_unchanged=True,all_owned_processes_reaped=True,scheduler_pids_cleared=True,signal_fault_cleanup_triggered=False,missing_evidence=[],
 evidence_directory=str(received),analysis_inputs=dict(evidence_dir=str(received/'payload/outputs'),phase_subdirs={phase:phase+'_'+job for phase in phases},ledger_relative_path='EXPOSURE_LEDGER.json'),
 engineering_only=True,formal_split_status='UNKNOWN',subject_mapping_status='UNKNOWN',validation_status='NOT_RUN_NO_FORMAL_SPLIT',scientific_acceptance=False,steady_state_speedup_acceptance=False)
for key,path in [('evidence_index',received/'COLLECTION_S00.json'),('archive',root/('evidence/JOB_'+job+'_evidence.zip')),('audit',root/'RUN_AUDIT.json'),('review',root/'S01_REVIEW.json'),('deployment_ready',root/'S00_DEPLOYMENT_READY.json')]:complete[key]=asset(path)
save(root/'RUN_COMPLETE.json',complete)
save(root/'RUN_PROGRESS.json',dict(job_id=job,state='SUCCEEDED_EVIDENCE_COMPLETE',active_s00_job=None,new_jobs=1,retries=0,next='coordinator reads RUN_COMPLETE; this round has no remaining run or retry'))
report=f'''# S00 R12实际门槛与单对同节点A/B

唯一2049894/cn21338 SUCCEEDED、exit0，2026-11-06T05:50:02Z—05:57:53Z，新增471节点秒；scheduler usage470秒分列。01 PASS_FOR_ENGINEERING_R12_AB精确绑定10项SHA、资源与工作量后才提交；没有重试/缩步/复用旧job或追加A/B。
新部署SHA=a3f81b40e58e63bde612c95cd04fcb7a2d054746f5977371bc58310ca8beccc8，原02 ZIP SHA=44232f7627cfbcf59fb721acd23af46aed8fa790b20fe743a3c9886717ec4de4。原candidate/baseline、数据/模型/阈值和历史execution_authorized字段保持，授权来自本轮TASK_CARD及用户；非优化Python原assert保持启用。

严格顺序target→strict5→baseline25→candidate25，4个不同PID、结果原远端mtime顺序相符，总60完整更新。单节点38分配/实际36留2，DDR24576MB同limit/exclusive/HBM0，总900秒；原生前置及整链共用START+840、统一清理30/收尾30，无阶段重置。
实际KML target输出比较1项差0；原生1个full和候选2个N1024块、完整K13312/偏移0与4096/lda512-ldb2048-ldc2048实际指针及canary/输入不变原门禁通过。完整strict两侧各5更新：3895项记录比较差0，每步153个参数的grad/param/delta/exp_avg/exp_avg_sq覆盖一致，h/voltage/coarse、loss和两个输入梯度、原AdamW step精确检查均保留；不是loss-only门槛。两侧perf首次5步各15项原loss比较差0，后20步有限性/状态门禁通过。
全部60更新逻辑GEMM149/步；baseline native149/full12、candidate native161/tiles24/dispatch12逐步核验。4阶段共139个完整CPU快照，全TID在selected0—35，reserved36—37；实际Torch intra36、interop608仅观察原默认。原R4 KML/shim/OpenMP等全部库path/SHA与前次已核原件及各阶段前后相同；实际baseline/candidate导入SHA正确，无R10和profiler。

| 同范围指标 | baseline | candidate |
|---|---:|---:|
| 后20步训练调用中位秒 | {baseline['observed20_median_seconds']:.6f} | {candidate['observed20_median_seconds']:.6f} |
| 后20步最小—最大秒 | {baseline['observed20_range_seconds'][0]:.6f}—{baseline['observed20_range_seconds'][1]:.6f} | {candidate['observed20_range_seconds'][0]:.6f}—{candidate['observed20_range_seconds'][1]:.6f} |
| 原25步训练调用总秒 | {baseline['all25_training_seconds']:.6f} | {candidate['all25_training_seconds']:.6f} |
| 独立进程应用wall秒 | {baseline['timing']['wall_seconds']:.6f} | {candidate['timing']['wall_seconds']:.6f} |
| 同范围逐步诊断秒 | {baseline['timing']['diagnostic_seconds']:.6f} | {candidate['timing']['diagnostic_seconds']:.6f} |
| 输入加载秒 | {baseline['timing']['data_loading_seconds']:.6f} | {candidate['timing']['data_loading_seconds']:.6f} |
| mask/attempt账本秒 | {baseline['timing']['mask_and_attempt_ledger_seconds']:.6f} | {candidate['timing']['mask_and_attempt_ledger_seconds']:.6f} |
| 保存/零更新恢复秒 | {baseline['timing']['checkpoint_recovery_seconds']:.6f} | {candidate['timing']['checkpoint_recovery_seconds']:.6f} |
| 逐步采样process-lifetime HWM MiB | {baseline['process_lifetime_HWM_MiB']:.3f} | {candidate['process_lifetime_HWM_MiB']:.3f} |

此次candidate后20步中位比baseline慢{change:.4f}%，未显示训练收益；不默认集成，交协调处置这个固定候选，不换块宽/精度继续搜索。仅固定顺序的一对探索，不是ABBA/多seed稳态或生产加速接受；不能把strict双模型/hook时间作性能对照，不能与旧跨job诊断比速。完整两侧原25步/后20步数组、RSS-before/after和所有计时分项在RUN_AUDIT，raw steps保持。HWM是独立性能进程在各训练步前后采样所见的进程生命周期高水位，非每步独占峰值、非恢复后最终或全job峰值。

原16unit/1600统计帧，strict共享前320帧各跑两侧；perf两侧各完整1600帧/25步。原init/scale/order/mask一致，无重复填充或扩样。strict账本5个共享批次确认，对应10模型更新；perf各25确认，全部in_flight=null。保存恢复两侧参数/optimizer/RNG/cursor/identity精确、forward门槛过，额外更新0；checkpoint各456122783bytes仅远端，路径/SHA见RUN_COMPLETE，不下载权重或续训。
旧9项原件以及固定36份输入path/bytes/SHA/mtime前后不变，本地7份受保护原件不变。所属8个PID/start-ticks全部回收，remaining_live/processes空、调度PID清空；自然退出未触发信号故障清理，因此该分支本轮未实测。
证据ZIP865426bytes/116文件，SHA=a078da8c80b776f88859f4cd824207b1fc8d98dad15d1a0d2421841f8037ecd7，CRC和每文件bytes/SHA均核，远端mtime原样索引；两checkpoint不入ZIP。初始化审计首版误把不同摘要schema整字典比较，已保留原审计与说明，改按原权重SHA/参数数目/seed0/模型源SHA逐字段核验，冻结执行包、原结果和数值阈值未改，没有重新执行。
RUN_COMPLETE绑定各阶段result/steps/ledger、本地索引/审计和性能摘要，供协调直接读。无正式subject/split/val/test、无科学/泛化/正式效果结论。只写S00本目录及短状态，旧失败/原包保持，未操作共享Git暂存/提交推送。
'''
(root/'RUN_REPORT.md').write_text(report,encoding='utf-8',newline='\n')
print(json.dumps(dict(status='RUN_COMPLETE_PUBLISHED',job_id=job,path=str(root/'RUN_COMPLETE.json'),sha256=sha(root/'RUN_COMPLETE.json'),median_change_percent=change)))
