# S00 R9 PROFILE5独立部署

只接受ENGINEERING_REAL_CORPUS_PROFILE5_V1及新S02_PROFILE5_*/payload目录；
旧job2043445、旧marker、旧PILOT成功状态都不能复用。
原descriptor完整字节SHA必须为b88ea9745147acf7fa70d51dc27c727f22f14e98af5dff1b80a9047e95648cd6。
不改descriptor内的旧账本路径，它仅为来源元数据；R9只写新profile_JOB目录的EXPOSURE_LEDGER.json。

## 新部署和元数据检查

本轮固定RUN由WORK_STARTED.json/PINNED_INPUTS.json给出。
先查实际djob队列、所有S02_PROFILE5目录/marker/job_id，不因新目录推定未提交。
新根不存在且没有本轮已提交任务后，才创建一次、上传部署ZIP和同名.sha256：

```bash
set -euo pipefail
source /etc/profile.d/donaukit_scheduler.sh
RUN=/home/share/dengqingtian/opt/stage4_sessions/S00/S02_PROFILE5_20261106T030149Z
djob -J
test ! -e "$RUN"
mkdir "$RUN"
# 上传S00_R9_PROFILE5_DEPLOYMENT.zip及.sha256，先核准其旁DEPLOYMENT_RECEIPT.json的bytes/SHA。
cd "$RUN"
sha256sum -c S00_R9_PROFILE5_DEPLOYMENT.zip.sha256
unzip -q S00_R9_PROFILE5_DEPLOYMENT.zip
sha256sum -c ARTIFACT_SHA256.txt
/usr/bin/python3 -B prepare.py
/usr/bin/python3 -B -m unittest discover -s tests -v > login_wrapper_tests.log 2>&1
env -u LD_PRELOAD PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 \
 PYTHONPATH=/home/share/songzhenlong/eitfm/sw/torch_kml \
 /home/share/dengqingtian/opt/stage4_sessions/S00/ENV_20261104T130730Z_R4/venv/bin/python3 -B \
 payload/inspect_engineering.py --descriptor "$RUN/ENGINEERING_DESCRIPTOR.json" \
 --descriptor-sha256 b88ea9745147acf7fa70d51dc27c727f22f14e98af5dff1b80a9047e95648cd6 \
 --output LOGIN_METADATA_CHECK.json
```

登录端只核源码/LF/AST3.9/bash-n/SHA及真实选样元数据，不跑模型、profiler、数组运算或编译。
保留原R4环境；计算端无登录profile依赖、不要求g++、不加线程setter。
数据16单元/1600帧全部用于原工程scale，只有原seed0前320帧接受5次更新；
不新选数据、不读旧checkpoint、不扩为完整epoch。

## S01审核及唯一提交

发布S00_DEPLOYMENT_READY.json后包/源码冻结。S01_REVIEW.json必须满足：

- decision=PASS_FOR_ENGINEERING_PROFILE5且review_complete=true。
- bindings逐项匹配required_review_bindings中的代码包、源码清单、部署包、部署索引、
  profile_contract、reference_first5、descriptor、原interface八份SHA。
- resources匹配38授权/实际36留2、24576MB同limit/exclusive、job900/whole840/cleanup30/closing30/stop_new720。

旧PASS_FOR_ENGINEERING_PILOT或FAIL/BLOCKED不能放行。
将01审核原件原字节上传RUN/S01_REVIEW.json，提交前再次核审核SHA、全部实物、实际队列及唯一标记。

```bash
cd "$RUN"
/usr/bin/python3 -B submit_once.py "$RUN" > login_submit_publish.log 2>&1
```

程序独占写新submit_once.marker，仅调用一次：

```bash
dsub -J -q q_hpcai -x job -R 'cpu=38,mem=24576MB' -RL 'mem=24576MB' \
 -a 'numa[count=1,distribution=pack]' -T 900 --env none --cwd "$RUN" \
 -oo "$RUN/job.log" bash "$RUN/run_job.sh" '<实际新S01_REVIEW原件SHA>'
```

该行供核命令，不能在submit_once后手工再执行。
超时/返回ID不明同样不重提，保存原stdout/stderr并核原目录/队列；RUNNING后单次publisher。
只有自己本轮尚未启动且排队超60分钟，复核未RUNNING后可取消它，不重提、不动其它任务。
整个门禁和应用共享入口840秒；child-subreaper/PID-start_ticks追踪全部所属后代，
统一TERM15/KILL15合计最多30秒、最晚870秒清理，留30秒收尾，调度硬限900秒。
本地mock不等于Linux信号故障清理已验；现场自然退出与实际信号路径分别记录。

## 五步判据、停止和完整收集

仅1—2预热无采样，3—5各一次CPU capture，连续AdamW1..5、B64/320帧。
成功只接受PROFILE5_COMPLETE_NOT_PERFORMANCE_ACCEPTANCE且全部原loss比较、来源、CPU/KML、恢复证据齐全。
profile_outcome.py核5条记录/原3分量比较、2+3时序、3trace/3events的bytes/SHA/事件阶段/KML标记与上限；
旧PILOT成功或缺文件不能PASS。UNSUPPORTED_PROFILER、PROFILE_LIMIT_EXCEEDED、SOURCE_CHANGED、
DATA_NOT_READY、ERROR_RUNTIME_OR_STATE和INCOMPLETE保留原状态与非零退出，不转backend、不截断、不补跑。
任何数值/身份/资源/预算异常即停，checkpoint只留远端、只收路径/bytes/SHA/零更新恢复。

每采样结束后核<=50000事件、<=256 KML包裹标记；每trace<=8MiB、每events<=1MiB，3+3合计<=27MiB。
不是实时逐事件截断。KML包裹含Python/分配/ctypes/native，不能当精确原生内核时间；
不叠加嵌套inclusive，不以跨线程CPU和除wall作占比，不把三步当稳态吞吐或收益。

```bash
cd "$RUN"
/usr/bin/python3 -B collect_evidence.py "$RUN"
```

回传JOB_<job>_evidence.zip/bundle_receipt.json，收集输出不要重定向到正被索引目录。
保留新profile_JOB全目录，包括失败/缺失/超限原件及所有trace/events、steps/result/新ledger/CPU/库/退出，
原始调度、授权、命令、后代清理和完整源包；逐项远端path/bytes/SHA/mtime_ns索引。
旧descriptor指向的运行账本及checkpoint只读，运行后再核其SHA不变。
RUN_COMPLETE.json在本地回传核验后发布，明确完整/unsupported/limit/失败/未完成状态，不缺失即PASS。
