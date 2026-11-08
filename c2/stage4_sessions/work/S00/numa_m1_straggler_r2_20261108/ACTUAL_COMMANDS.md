# NUMA 慢域 R2 实际命令

既有 C2 登录端 `dengqingtian@10.44.9.4`，使用已核 SSH 主机密钥。先查 `djob -J` 和旧 2061246 的原生终态，查 M23 活动作业、当前优先节点和队列。各版本的原生 argv 以各自 `NUMA_RUN_BINDING.json` 及现场 `submission.command.json` 为准。

## PREF_A

```bash
source /etc/profile.d/donaukit_scheduler.sh
RUN=/home/share/dengqingtian/opt/stage4_sessions/S00/NUMA_M1_R2_PREF_A
PIN=e6089688f6d0f8448e639cf615862b1d27e61f2fc38c78b51013fdfd0dc919c2
PACKAGE_SHA=df8d3d291a78ae5f986d940cc00b42d36bbb11e4e94840da4a1d9e9cea3e0fed
cd "$RUN"
printf '%s  %s\n' "$PACKAGE_SHA" NUMA_M1.zip "$PIN" NUMA_RUN_BINDING.json | sha256sum --check --strict
unzip -n -q NUMA_M1.zip
/usr/bin/python3 -B prepare.py "$PIN"
timeout --signal=TERM --kill-after=5s 60s env -u LD_PRELOAD PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 /home/share/dengqingtian/opt/stage4_sessions/S00/ENV_20261104T130730Z_R4/venv/bin/python3 -B inspect_metadata.py --output LOGIN_METADATA_CHECK.json
timeout --signal=TERM --kill-after=5s 45s /usr/bin/python3 -B recheck_fixed_inputs.py > FIXED_INPUTS_BEFORE.json
nohup /usr/bin/python3 -B submit_once.py "$PIN" </dev/null >login_submit.log 2>&1 &
echo "$!" > login_submit_pid.txt
```

唯一提交入口生成 `dsub -J -q q_hpcai -x job -nl cn21341 -R 'cpu=152,mem=98304MB' -RL 'mem=98304MB' -a 'numa[count=4,distribution=pack]' -T 1800 --env none --cwd "$RUN" -oo "$RUN/job.log" bash "$RUN/run_job.sh" "$PIN"`。登录观察器对该优先节点只等 720 秒。到期仍 PENDING 时，仅对本作业 ID 使用 `dkill -y -s PENDING`。调度实际进入 RUNNING 后发布本作业分配回执，不取消有效计算。

查询 `djob -J -l 2063196`。若收到有效分配，执行原阈值严格五步，再执行两个新进程队列各 25 步。第二队列循环移动一个物理域，rank、启动顺序一同移动。微探针最多 90 秒执行加 30 秒清理，使用固定形状原生 KML dW 和 128 MiB 本地张量拷贝。

2063196 按上述排队条件终止。作业未获配，使用 `collect_unallocated.py "$PIN"` 只收集原生终态、取消及清理证据。传输包由 `tar -czf JOB_2063196_TRANSFER.tgz JOB_2063196_evidence.zip bundle_receipt.json` 生成，SHA256 为 `3542207f79090901a445ce9399e32b7ab2d5764331c7cab13f55d0909652e2e2`。

## ALT_A

重新用 `djob -J`、`djob -J -l 2063215`、`djob -J -l 2063247` 和 `dnode -J -l cn21385` 确认 2063196 终态、自身去重和节点隔离。cn21385 当时 OK、无调度作业、608 核空闲，aarch64、16 NUMA、每核 1 TID。M23/S09 在 cn21379，S10 在 cn21762，旧核验的两个健康参考节点当时均被占用。

```bash
RUN=/home/share/dengqingtian/opt/stage4_sessions/S00/NUMA_M1_R2_ALT_A
PIN=76aea26945c3c7dcfb63b8b9d2c8639e82e70e5f280cfe249fa759fd74f95a9a
PACKAGE_SHA=8d4c09f3e92a3f60477a385d7167165ee0761e9d58390f928ae83630308da051
```

其余上传、核包、数据门禁和提交调用与 `PREF_A` 相同，提交节点为 `cn21385`，PENDING 上限 900 秒。登录端在提交前另存 `dnode --frequency -J cn21385 > site_frequency_before.json`。本次唯一提交编号为 `2063260`，原生命令存 `submission.command.json`，运行参数与约束保留 152/144 核、DDR96GiB 同限额、HBM0、同 die 和原阈值。ALT_A 相对 PREF_A 只修订提交前的并发作业节点判定，按 RUNNING 实际节点、PENDING 明确正向节点判断冲突，并纳入 S10。模型和诊断入口保持字节相同。

终态后记录 `dnode --frequency -J cn21385`、`getconf CLK_TCK` 和原机状态，重核原输入。运行 `/usr/bin/python3 -B collect.py "$PIN"` 后用 `tar -czf JOB_2063260_TRANSFER.tgz JOB_2063260_evidence.zip bundle_receipt.json` 打包。回传 SHA256 为 `0c7294c3d096ab5787766c899f7d3983dce540b11bf29ed3b96ae76d8a26814c`。

## PREF_B

```bash
RUN=/home/share/dengqingtian/opt/stage4_sessions/S00/NUMA_M1_R2_PREF_B
PIN=a3dada7dae6cfb8ad7886fd75c3d9532121bb4a544a7d49da49eae3149d645a5
PACKAGE_SHA=171e6e98f7dde718b166017597dd6baea509bceeadf08fcda79c7820525ede54
```

重复已核的上传、哈希、解包、静态入口、固定数据及队列门禁。查询 `djob -J -l -u all 2063068` 得到 BATCH.1004，原机外部作业的预计结束时间不可见。只提交 2063321，限定 cn21341，PENDING 最多 2700 秒。资源、数据、模型、轮换、原门禁和两组 25 步一致。相对 ALT_A 新增固定 149 次 SGEMM 的逐形状 ctypes 调用用时，按各域总训练步时扣除 native 时间，比较慢域差异主要出现在哪里。微探针已用 18 秒，本作业最多执行 72 秒加最多 30 秒清理。

用户补充指令要求避免等待原计划节点。先以 `djob -J -l 2063321` 确认作业仍在 PENDING 且路径归属本次，再执行 `dkill -y -s PENDING 2063321`。确认 FAILED/10003、startTime=-、无分配节点，收集进程检查和原始证据后才进入下一次提交。传输 SHA256 `3dc1a0b60ffc44b67766a14130b11a04a153b23439abc19654241778b70478b2`。

## ALT_B

```bash
RUN=/home/share/dengqingtian/opt/stage4_sessions/S00/NUMA_M1_R2_ALT_B
PIN=75a5a7d6b3273b0f44b13f982e0b11cfa7bc43dcbbf4fb55a0cd113763b94a00
PACKAGE_SHA=171e6e98f7dde718b166017597dd6baea509bceeadf08fcda79c7820525ede54
```

原生节点快照显示 cn21386 OK、608 核空闲、无调度作业，先复核 2063321 终态及 M23/S09、S10 活动作业。以相同命令部署，站点独占节点约束改为 cn21386，PENDING 上限 120 秒。PREF_B 与 ALT_B 的负载包 SHA 相同，运行绑定随节点和预算独立冻结。唯一提交号为 2063333。

在终态后保存 `dnode --frequency -J cn21386`、`getconf CLK_TCK`、`djob -J` 和固定输入复核结果。运行 `/usr/bin/python3 -B collect.py "$PIN"` 后用 `tar -czf JOB_2063333_TRANSFER.tgz JOB_2063333_evidence.zip bundle_receipt.json` 打包。回传 SHA256 为 `8f033a40c2e57db2db2895dfe6fc2dd35047254ceaa5b46e48ee5ba43b04868a`。最后用 `djob -J -l` 逐一复核 2063196、2063260、2063321、2063333，均终态，两个已分配节点原生 PID 为 `-`，随后关闭登录连接。
