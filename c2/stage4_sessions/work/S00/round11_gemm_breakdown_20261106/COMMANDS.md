# S00 R11：未改原基线GEMM五步调用分解

仅ENGINEERING_REAL_CORPUS_GEMM5_V1，新S02_GEMM5_*/payload、新marker、新job。
不执行/打包R10 candidate或20更新A/B，不改原descriptor/数据/模型/阈值，不复用旧2043445/2048959。
原descriptor字节SHA仍b88ea9745147acf7fa70d51dc27c727f22f14e98af5dff1b80a9047e95648cd6；
实际baseline/kml_ops.py必须e6c5c4411c453c8168939cd51d737a7e9d8232bdfff05da3967805a5e917ff26。
顶层INTERFACE是R11新观测接口，payload/data_gate保留原工程数据接口，不能覆盖或混称。

## 先去重、核源、部署（登录侧不跑模型）

```bash
set -euo pipefail
source /etc/profile.d/donaukit_scheduler.sh
RUN=/home/share/dengqingtian/opt/stage4_sessions/S00/S02_GEMM5_20261106T041202Z
djob -J
find /home/share/dengqingtian/opt/stage4_sessions/S00 -maxdepth 2 -type f \
 -path '*/S02_GEMM5_*/*' -name job_id.txt -print
# 已有本轮marker/提交则只监测/收集，不新建目录重提。
test ! -e "$RUN"
mkdir "$RUN"
# 上传已核S00_R11_GEMM5_DEPLOYMENT.zip及.sha256；核旁DEPLOYMENT_RECEIPT.json的bytes/SHA。
cd "$RUN"
sha256sum -c S00_R11_GEMM5_DEPLOYMENT.zip.sha256
unzip -q S00_R11_GEMM5_DEPLOYMENT.zip
sha256sum -c ARTIFACT_SHA256.txt
/usr/bin/python3 -B prepare.py
/usr/bin/python3 -B -m unittest discover -s tests -v > login_wrapper_tests.log 2>&1
timeout --signal=TERM --kill-after=5s 60s env -u LD_PRELOAD \
 PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 \
 /home/share/dengqingtian/opt/stage4_sessions/S00/ENV_20261104T130730Z_R4/venv/bin/python3 -B \
 payload/inspect_engineering.py --descriptor "$RUN/ENGINEERING_DESCRIPTOR.json" \
 --descriptor-sha256 b88ea9745147acf7fa70d51dc27c727f22f14e98af5dff1b80a9047e95648cd6 \
 --output LOGIN_METADATA_CHECK.json
```

只核LF/AST3.9/Linux bash-n/源码及ZIP SHA、固定16NPZ/sidecar字节身份和元数据；
不读数组跑算子、不启用完整profiler、不安装依赖。计算节点同样先核原生job/主机/nonce/raw/ready、
实际单NUMA38物理核/DDR同limit及selected36；无计算端登录profile、无线程setter。
旧账本/checkpoint只读，新账本与3份记录只写outputs/gemm_JOB。

## 新专项审核与唯一提交

S00_DEPLOYMENT_READY发布后包/源冻结。S01_REVIEW必须decision=PASS_FOR_ENGINEERING_GEMM5、
review_complete=true，bindings逐项等于required_review_bindings的代码/源清单/新接口/契约/参照/
descriptor/部署包和部署索引SHA；resources逐项匹配38/36留2、24576MB同limit/exclusive/HBM0、
job900/全入口840/清理30/收尾30/720秒停新步。
旧PILOT或PROFILE5 PASS、FAIL/BLOCKED、缺项/错SHA都不能放行。

将新S01原件原字节上传RUN/S01_REVIEW.json；提交前再次只读核所有SHA、源、实际队列和唯一marker：

```bash
cd "$RUN"
/usr/bin/python3 -B submit_once.py "$RUN" > login_submit_publish.log 2>&1
```

脚本独占创建新submit_once.marker，再唯一调用（下行为审核展示，不得再手工重复）：

```bash
dsub -J -q q_hpcai -x job -R 'cpu=38,mem=24576MB' -RL 'mem=24576MB' \
 -a 'numa[count=1,distribution=pack]' -T 900 --env none --cwd "$RUN" \
 -oo "$RUN/job.log" bash "$RUN/run_job.sh" '<新S01_REVIEW实际原件SHA>'
```

提交超时/ID不明保留marker和stdout/stderr，查同一目录/队列，不重提。
RUNNING单次发布原生授权；未启动排队超60分钟，仅复核当前状态后可取消自己这一个排队job，不重提、不动外部任务。
新门禁/数据/完整应用共享840秒，child-subreaper/PID-start_ticks覆盖全部所属后代，
统一TERM15/KILL15最多30秒，最晚870秒清理，留30秒收尾，硬限900秒。
本地mock不等于现场信号故障清理通过；自然退出与信号路径分别记录。

## 调用分解、停止与原始收集

仅5次连续AdamW更新，1—2不挂详细hook、3—5各一份gemm_step_N.json。
原1600帧只用于同一工程scale，训练前320帧；原init/frame/mask/15项loss/KML149次每步不变。
观测原counted GEMM和同次真实_sgemm，按线程/序号记录m/n/k、shape/stride/dtype/连续性、
ta/tb/beta、实际sgemm布局/转置/leading dimensions及输出alias布尔、嵌套单调ns边界。
只记录标量元数据，不复制/打印tensor值；一次原函数调用、同参数/输出/顺序，异常时恢复临时hook。

gemm_outcome只接受GEMM5_COMPLETE_NOT_PERFORMANCE_ACCEPTANCE，须5步/320帧/3份149条完整一一对应、
全部原门槛/CPU/KML/恢复证据齐；不拿R9 trace当成功证据。
GEMM_OBSERVATION_ERROR、GEMM_LIMIT_EXCEEDED、UNSUPPORTED_GEMM_OBSERVATION、SOURCE_CHANGED、
DATA_NOT_READY、ERROR_RUNTIME_OR_STATE和INCOMPLETE均保留原状态，停止、不回退/截断/重试。
每采样最多256条、文件<=1MiB、最多3份；缺记录或多配/漏配即停。

ctypes wall包含Python参数转换、原生打包/调度/计算；外层差值还含准备/分配/计数及观测bookkeeping，
均非纯微内核时间。role只按已核Linear上下文及flags判forward/dX/dW，其它UNKNOWN。
同线程/嵌套区间和跨线程重叠要单独处理，不能把简单求和当程序wall或据此称加速。

```bash
cd "$RUN"
/usr/bin/python3 -B collect_evidence.py "$RUN"
```

回传JOB_<job>_evidence.zip及原bundle_receipt.json；收集日志不要写入正被索引目录。
包含全部新gemm_JOB目录、steps/result/3调用文件/CPU/库/命令/退出/超时/新ledger、源码包、原始调度/资源和后代清理。
逐文件远端path/bytes/SHA/mtime_ns索引；失败/半文件/缺项原样保存，不缺失即PASS。
checkpoint只留远端，收路径/bytes/SHA和零额外更新恢复；不下载权重、无续训。
运行后再核原输入/旧账本/checkpoint SHA不变，发布RUN_COMPLETE绑定本地索引及3份记录供08直接读取。
