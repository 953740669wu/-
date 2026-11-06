# S00 夜间工程部署/执行约定

仅 ENGINEERING_REAL_CORPUS_PILOT_V1；旧REALDATA_SOURCE_AUDIT.json仍DATA_NOT_READY。
固定16个单元/1600帧只用于工程训练，case不等于subject，不产生正式val/test或效果结论。
固定descriptor和初始暴露清单在DATA_READY.json中绑定；应用运行暴露清单独立写到payload/outputs。
源manifest必须为任务卡14300版SHA，不接受第三个版本。

## S01专项审核记录约定

执行器review_gate.py要求S01_REVIEW.json中：

- decision=PASS_FOR_ENGINEERING_PILOT、review_complete=true。
- bindings对象中的code_package_sha256、code_source_manifest_sha256、deployment_package_sha256、
  descriptor_sha256、interface_sha256与S00_DEPLOYMENT_READY.json的required_review_bindings逐项一致。
- resources对象至少包含S00_DEPLOYMENT_READY.json.resources所有键且值相同，
  即38/36/2核、24576MB同limit/exclusive、job900/whole_entry840/cleanup30。

FAIL/BLOCKED或未绑定实物的摘要都不能放行。S01可以另加现场待验项和不含科研/性能接受的说明。
该约定用于精确校验本任务卡要求的四类身份，不授权S00自行改变S01结论。

## 部署与必要登录检查（不启动模型）

固定远端目录为DATA_READY.json.remote_staging_root；不得新换目录隐藏已有提交。
先实际djob -J、核S00已有ENGINEERING/PILOT目录及marker/job_id，再核当前manifest SHA。
只有目录不存在且无本轮任务提交，才新建此S00目录；上传核准部署ZIP和同名.sha256。

```bash
set -euo pipefail
source /etc/profile.d/donaukit_scheduler.sh
RUN=/home/share/dengqingtian/opt/stage4_sessions/S00/ENGINEERING_PILOT_20261105T154333Z
djob -J
# 确认已有记录不含本轮提交后新建一次；目录存在时先检查，不覆盖。
test ! -e "$RUN"
mkdir "$RUN"
# 上传S00_OVERNIGHT_ENGINEERING_DEPLOYMENT.zip及.sha256到RUN后：
cd "$RUN"
sha256sum -c S00_OVERNIGHT_ENGINEERING_DEPLOYMENT.zip.sha256
unzip -q S00_OVERNIGHT_ENGINEERING_DEPLOYMENT.zip
sha256sum -c ARTIFACT_SHA256.txt
/usr/bin/python3 -B prepare.py
/usr/bin/python3 -B -m unittest discover -s tests -v > login_wrapper_tests.log 2>&1
# 用固定R4解释器只运行S02工程metadata入口；不运行模型或旧正式CLI，不安装依赖。
```

prepare核全部外层源及内包/源码清单SHA，拒绝已有payload/pre_submit_checks；LF、AST3.9、
Linux bash-n均检查。工程metadata检查命令随已发布的S02具体包路径在READY记录中给出。
计算端仍重新核包、原生job/nonce/raw/ready、主机、38实际物理核/NUMA/DDR、无重试。
计算端不source登录profile、不检查g++。保持38核入口授权，原S02守卫在同PID框架导入前绑前36，
观察实际Torch36/KML/全部TID，不添加线程setter冒充现场证据。

## 唯一提交（只在S01明确通过且全部身份一致后）

把S01确切审核原件复制到RUN/S01_REVIEW.json；复制不改字节。
本地和登录端均用review_gate核本条审核SHA及所有binding。

```bash
cd "$RUN"
/usr/bin/python3 -B submit_once.py "$RUN" > login_submit_publish.log 2>&1
```

submit_once先核SHA和S01专项审核，独占创建submit_once.marker，再只调用一次：

```bash
dsub -J -q q_hpcai -x job -R 'cpu=38,mem=24576MB' -RL 'mem=24576MB' \
 -a 'numa[count=1,distribution=pack]' -T 900 --env none --cwd "$RUN" \
 -oo "$RUN/job.log" bash "$RUN/run_job.sh" '<实际S01_REVIEW原件SHA256>'
```

不可在脚本提交后再手工执行同一dsub。提交超时/返回ID不明亦保留marker，不重提；
先查实际队列/原stdout。PENDING轮询不算新实验；RUNNING立即单次publisher。
只有自己本轮作业尚未运行且排队超过60分钟，复核当前状态后才可取消它，不能重提或取消其它任务。
网络中断先保存job ID与已观测状态；恢复只查原job。

外层从Python模块入口起全840秒，包括30秒以内的授权门禁、包检查及原工程入口所有步骤；
原S02内部840秒超时也消耗此共同截止，不能从启动训练时重新给外层840秒。
Linux child-subreaper记录并接管另起session的全部本任务后代；统一TERM15/KILL15总30秒，
最晚870秒结束清理，留30秒收尾，调度硬限900秒。共享盘/不可中断内核I/O的实际异常照实记录。
1epoch/200更新先到即停；多步loss波动不调参。任意来源/配对/资源/状态/数值/运行错误停止，不重试。

## 原始终态收集

```bash
cd "$RUN"
/usr/bin/python3 -B collect_evidence.py "$RUN"
```

回传JOB_<job>_evidence.zip和bundle_receipt.json；收集日志不要写入正在索引的RUN。
归档原调度/授权/命令/退出/清理、源内外包/接口/descriptor/暴露原件、steps/result/恢复记录及线程/库。
每个文件含远端path/bytes/SHA/mtime_ns。checkpoint留原远端路径，只回传完整大小/SHA和恢复结果；
不下载/加载权重做额外更新，不把数据/权重加入Git。失败/缺result/ledger也保留，不能当作PASS。
暴露不明时另写EXPOSURE_RECONCILIATION.json，保留原initial/runtime账本，不补造已消费帧。
RUN_COMPLETE.json在本地完整回传和核对后发布，供S08直接读取；失败终态也用同样入口明确标记。
