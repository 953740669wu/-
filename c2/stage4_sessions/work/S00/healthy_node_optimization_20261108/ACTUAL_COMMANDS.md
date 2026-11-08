# S00 FFN 缓冲复用同机 A/B

取消 2063398 和进程清理已在 R3 的原生证据中核实。取消产生的 1169 秒排队和 1 次提交计入继承预算。

本地 `python -I -S -B freeze_optimization.py RELU_A cn21385 cn21762 cn21387` 冻结候选。现场查 `djob -J`、`djob -J -l 2063431` 和各目标 `dnode -J -l`。09 实际在 cn21379，目标列表三台均符合资源检查，节点由调度器选择，cn21341 排除。运行目录中留存提交前队列和实际占用证据。

```bash
source /etc/profile.d/donaukit_scheduler.sh
RUN=/home/share/dengqingtian/opt/stage4_sessions/S00/NUMA_M1_R3_OPT_RELU_A
PIN=ebbaee78bc31913d32f0ba99b4db84231b71e48fc9a7edc25951efe635918dc3
PKG=0af2d230f41b99fa31f0d562b55c0c68245ed0c4d4022a29b0caef110156a161
cd "$RUN"
printf '%s  %s\n' "$PKG" NUMA_M1.zip "$PIN" NUMA_RUN_BINDING.json | sha256sum --check --strict
unzip -n -q NUMA_M1.zip
/usr/bin/python3 -B prepare.py "$PIN"
timeout --signal=TERM --kill-after=5s 60s env -u LD_PRELOAD PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 /home/share/dengqingtian/opt/stage4_sessions/S00/ENV_20261104T130730Z_R4/venv/bin/python3 -B inspect_metadata.py --output LOGIN_METADATA_CHECK.json
timeout --signal=TERM --kill-after=5s 45s /usr/bin/python3 -B recheck_fixed_inputs.py > FIXED_INPUTS_BEFORE.json
nohup /usr/bin/python3 -B submit_once.py "$PIN" </dev/null >login_submit.log 2>&1 &
echo "$!" > login_submit_pid.txt
```

实际提交入口发出 `dsub -J -q q_hpcai -x job -nl 'cn21385 cn21762 cn21387 !cn21341' -R 'cpu=152,mem=98304MB' -RL 'mem=98304MB' -a 'numa[count=4,distribution=pack]' -T 1800 --env none --cwd "$RUN" -oo "$RUN/job.log" bash "$RUN/run_job.sh" "$PIN"`。作业 2063448，实际 cn21385。

四域独立模型。严格阶段每域原版和候选五步，原 tensor/state/relL2/near-zero/exact 比较；四域全部通过后，原版和候选分批以独立进程各执行 25 步，统计第 6–25 步。候选每步应有 12 次 FFN 缓冲复用，原版应为 0。两侧实际 native SGEMM shape/flags 和 149 次计数必须一致。两侧归档实际 rank/物理域/线程、固定输入、运行库及恢复身份。同步观测窗口用时下降 10% 是首对继续条件，三个独立同机对照的波动须不超过 5% 才可采用。

候选源 SHA256 `c1502a0afd31916fcac38139a17a35d346649b8aff7261e73b945fdcd7a0954e`。单项候选 diff 在 `RELU_A/CANDIDATE.diff`，部署与采集改动另存 `RELU_A/DEPLOYMENT.diff`。

终态后执行 `djob -J > post_job_queue.json`、`getconf CLK_TCK > login_clock_ticks.txt`，再复核固定输入并运行 `/usr/bin/python3 -B collect.py "$PIN"`。`tar -czf JOB_2063448_TRANSFER.tgz JOB_2063448_evidence.zip bundle_receipt.json` 生成的传输 SHA256 为 `92f01a81a96a22d9240bfbb75a414ab191fa0343cef95760e2d7b7de79daf63d`。逐一现场复核 2063398 和 2063448 原生终态及 PID 后关闭连接。
