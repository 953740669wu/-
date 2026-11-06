"""Publish the audited terminal evidence for direct downstream handoff."""
from datetime import datetime,timezone
import json
from pathlib import Path
import shutil
from prepare import sha,save
from review_gate import expected
root=Path(__file__).resolve().parent
audit=json.loads((root/'RUN_AUDIT.json').read_text())
assert audit['status']=='PASS_GEMM5_ENGINEERING_EVIDENCE_ONLY'
job=audit['job_id'];received=root/'evidence/received';run=received/'payload/outputs'/('gemm_'+job)
def asset(path):
    p=Path(path)
    return dict(path=str(p),bytes=p.stat().st_size,sha256=sha(p))
shutil.copyfile(run/'EXPOSURE_LEDGER.json',root/'EXPOSURE_LEDGER.json')
complete=dict(status='RUN_COMPLETE',protocol='ENGINEERING_REAL_CORPUS_GEMM5_V1',data_protocol='ENGINEERING_REAL_CORPUS_PILOT_V1',
 published_utc=datetime.now(timezone.utc).isoformat(),immutable_after_publish=True,job_id=job,host=audit['host'],scheduler_state='SUCCEEDED',job_exit_code=0,
 new_jobs=1,retries=0,active_s00_job=None,outcome='GEMM5_COMPLETE_NOT_PERFORMANCE_ACCEPTANCE',completed_updates=5,actual_train_frames=320,
 normalization_frames=1600,warmup_steps=[1,2],sampled_steps=[3,4,5],original_loss_metrics_passed=15,original_loss_max_abs=audit['original_loss_max_abs'],
 node_seconds=audit['node_seconds'],scheduler_usage_seconds=audit['scheduler_usage_seconds'],source_bindings=expected(root),source_status='UNCHANGED',
 old_inputs_ledger_checkpoint_unchanged=True,original_fixed36_path_bytes_sha_mtime_unchanged=True,scheduler_pids_cleared=True,all_owned_processes_reaped=True,
 recovery_status='PASS_NO_EXTRA_UPDATE',extra_optimizer_updates=0,checkpoint=audit['checkpoint'],checkpoint_transfer='REMOTE_ONLY_NOT_DOWNLOADED',
 evidence_directory=str(received),analysis_inputs=dict(evidence_dir=str(run),run_subdir='.',ledger_relative_path='EXPOSURE_LEDGER.json'),
 gemm_samples=[dict(step=i,records=149,native_calls=149,**asset(run/('gemm_step_'+str(i)+'.json'))) for i in (3,4,5)],
 sample_total_bytes=audit['capture_bytes'],missing_evidence=[],engineering_only=True,formal_split_status='UNKNOWN',subject_mapping_status='UNKNOWN',
 validation_status='NOT_RUN_NO_FORMAL_SPLIT',scientific_acceptance=False,steady_state_performance_acceptance=False,
 native_kml_kernel_time='UNKNOWN_CTYPES_NOT_PURE_KERNEL',in_step_observer_overhead='UNKNOWN_WITHOUT_MATCHED_CONTROL',
 timing_scope='same-call same-thread monotonic GEMM and ctypes boundaries; ctypes includes conversion and native packing/scheduling/compute; outer difference includes preparation/counters/alloc/observer; never sum overlap as program wall',
 R10_disposition='CLOSED_NOT_SELECTED_LOW_BENEFIT_NO_AB')
for key,path in [('application_result',run/'result.json'),('steps',run/'steps.jsonl'),('exposure_ledger',run/'EXPOSURE_LEDGER.json'),
 ('evidence_index',received/'COLLECTION_S00.json'),('archive',root/('evidence/JOB_'+job+'_evidence.zip')),('audit',root/'RUN_AUDIT.json'),
 ('review',root/'S01_REVIEW.json'),('gemm_contract',root/'GEMM_CONTRACT.json'),('reference_first5',root/'REFERENCE_FIRST5.json')]:complete[key]=asset(path)
save(root/'RUN_COMPLETE.json',complete)
save(root/'RUN_PROGRESS.json',dict(job_id=job,state='SUCCEEDED_EVIDENCE_COMPLETE',exit_code=0,active_s00_job=None,new_jobs=1,retries=0,next='coordinator/S08 read RUN_COMPLETE; no further job authorized in this round'))
save(root/'PROGRESS.json',dict(status='COMPLETE',job_id=job,new_jobs=1,retries=0,active_s00_job=None))
report=f'''# S00 R11 GEMM5唯一工程采集

2049454 / cn21338：SUCCEEDED、exit0，2026-11-06T04:43:39Z至04:44:55Z，76节点秒，scheduler usage76秒。本轮仅一次提交，无重试、无活动S00 job。
S01 PASS_FOR_ENGINEERING_GEMM5绑定8项具体SHA及38分配/实际36留2、24576MB同limit/exclusive/HBM0、job900/全入口840/清理30/收尾30/720秒停新步；原冻结部署、原基线和原descriptor不变。

仅5次连续AdamW/B64，1—2无详细hook，3—5各149条外层GEMM/实际ctypes _sgemm同线程一一对应，共447条，3文件共450119bytes（每份约150KB，均小于1MiB和256条）。实际矩阵shape/stride/dtype/连续性、ta/tb/beta、m/n/k、原生sgemm布局/leading dimensions、输出alias及嵌套单调ns边界逐条核通过。没有R9完整profiler文件或R10候选。
原16单元/1600统计帧、前320训练帧/seed0、初始化/scale/frame/mask均一致；15项原loss比较max_abs和relative均0，未修改2e-5/2e-6阈值。训练KML745次、全进程843次分列，恢复额外98次不混作训练观测。
19个CPU完整快照全部TID在selected0—35，reserved36—37，实际Torch intra-op36，interop608仅观察原默认；最大观测TID数36。原shim/KML/OpenMP及运行前后加载库SHA一致，实际原_sgemm类型_FuncPtr、baseline与observer实际导入SHA与冻结包一致。

程序wall {audit['timing']['wall_seconds']:.6f}s；五步training范围{audit['timing']['training_step_seconds']:.6f}s；详细观测导出/挂钩外层差{audit['timing']['observation_export_and_hook_seconds']:.6f}s，这个差不包含所有步内观测成本。逐调用ctypes wall含Python转换和原生打包/调度/计算，外层差含准备/分配/计数/observer；均不是纯微内核时间，不作同机A/B、稳态加速或性能接受。并发/嵌套区间不直接求和当程序wall。细分归因供08按原件继续。

新暴露账本5次confirmed、in_flight=null，无重复/补齐帧。保存恢复参数/optimizer/RNG/cursor/identity exact，3项恢复forward差0、额外更新0。新checkpoint仅留远端：456135071bytes，SHA={audit['checkpoint']['sha256']}，路径见RUN_COMPLETE；未下载权重/续训。
所属5个PID/start-ticks受subreaper监督，终态全部回收、remaining_live/processes为空，调度PID清空。自然结束未触发TERM/KILL，因此本轮不声称信号故障注入清理实测通过。
原36份固定源path/bytes/SHA/mtime前后相同；旧manifest/descriptor、2043445与2048959账本/checkpoint和原baseline7项SHA不变，本地7个受保护原件不变。保留早期无结果元数据检查和提交前引号失败；两者均未调用dsub，后续有界检查通过后才唯一提交。所有失败原件保留。

证据ZIP：471647bytes/106文件，SHA=671305ef5915870820d0a8890bdf9050d5eff61f4f5e2f5fdd9e68b497220513；归档CRC、逐文件bytes/SHA和远端mtime索引已核。RUN_COMPLETE锚定本地索引/三份记录/steps/result/ledger/audit供08直接读。9本地+9 Linux登录夹具为准备检查；现场结果与之分别记录。
无正式split/subject/val/test，仅工程证据，不作科学/泛化/正式效果结论。R10保留且低收益不选用，不执行20更新A/B、不默认集成。未改其它任务、正式门禁、旧结果、共享Git暂存或提交推送。
'''
(root/'RUN_REPORT.md').write_text(report,encoding='utf-8',newline='\n')
print(json.dumps(dict(status='RUN_COMPLETE_PUBLISHED',job_id=job,path=str(root/'RUN_COMPLETE.json'),sha256=sha(root/'RUN_COMPLETE.json'))))
