# R2 现场入口与版本

首个冻结版本 `B32_C1_A`。绑定 SHA256 `fb2008a49ac2da518650be213ad45c9644a2db678e2b3fddc6dec1f4438ac58f`，包 SHA256 `b14c5a5a2ec65342b83bdf3bc5934f87e142a1840cd1dae0f4c68e7fb672539d`，worker SHA256 `4791a4cc6c187847a28d1c85a8c13b735a5cbd93f36f3561f4236a000bf4883a`，diff SHA256 `97605c3e76ff2ee2182811c8411eb0666f53d49821733f6c7830edcab460b6a4`。

```bash
source /etc/profile.d/donaukit_scheduler.sh
RUN=/home/share/dengqingtian/opt/stage4_sessions/S00/FULL16_R2_B32_C1_A
PIN=fb2008a49ac2da518650be213ad45c9644a2db678e2b3fddc6dec1f4438ac58f
PKG=b14c5a5a2ec65342b83bdf3bc5934f87e142a1840cd1dae0f4c68e7fb672539d
cd "$RUN"
printf '%s  %s\n' "$PKG" FULL16_PAYLOAD.zip "$PIN" RUN_BINDING.json | sha256sum --check --strict
unzip -n -q FULL16_PAYLOAD.zip
/usr/bin/python3 -B prepare.py "$PIN"
timeout --signal=TERM --kill-after=5s 60s env -u LD_PRELOAD PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 /home/share/dengqingtian/opt/stage4_sessions/S00/ENV_20261104T130730Z_R4/venv/bin/python3 -B inspect_metadata.py --output LOGIN_METADATA_CHECK.json
timeout --signal=TERM --kill-after=5s 45s /usr/bin/python3 -B recheck_fixed_inputs.py > FIXED_INPUTS_BEFORE.json
nohup /usr/bin/python3 -B submit_once.py "$PIN" </dev/null >login_submit.log 2>&1 &
echo "$!" >login_submit_pid.txt
```

提交入口内重查当前用户活动作业、各窗口归属及调度器资源。原生完整 argv 在各版 `RUN_BINDING.json`，实际参数由 `submission.command.json` 绑定。配对顺序 A/B、B/A、A/B。整体吞吐以三对等量观测窗的总工作量除以总耗时判定，另报告每对及每域值。若候选的三轮波动超过 5% 或整体吞吐下降，保持原版。

本次实到登录端提交前门禁。`dqueue -J -l q_hpcai` 返回 `BATCH.5001`，发生在 `submit_once.marker` 建立前。没有 `submission.command.json`、`job_id.txt` 或计算证据。`dqueue -J -l default`、`dnode -J -q default`、`dnode -J -q q_hpcai` 及账号实际活动队列的对照见 `preflight/QUEUE_ACCESS_EVIDENCE.json`。登录端已按原包 SHA 结束 helper。

账号换为 `wujunyi` 后，保留此前证据与原 R2 预算。新账号的 `q_hpcai` 队列门通过，私有目录 `/home/share/wujunyi/opt/stage4_sessions/S00/FULL16_R2_B32_C1_W1`。按上面命令，仅替换 `RUN`、`PIN`、`PKG`，并上传 `FROZEN_HBM_ALLOCATOR.so`。绑定 `648417a6a846246d426e972bc241a6455b6b86368ce14cd19c5ba3c2c1657072`，包 `9b44b57a6445091ca8a1c6206cdb0f7703bff1d56956cfc05edec77bb6896407`，候选 worker SHA 不变。原 HBM 库目录对该账号不可读，使用 R1 回传且与原 SHA `89f295754a199dcb6206f8e6217e6cf57651bceed2d364b1a6e4cc83eea6095d` 相同的库字节。恢复 `hbm_gate.py` 仍读取的历史证据字段，部署校验与实际原生 job 所有者同时绑定 `wujunyi`。原 R4 运行时和真实输入路径保持原身份。登录端已确认新账号无活动作业，旧账号跨用户实时查询返回 `BATCH.1004`。旧 R2 原件证明提交未调用 `dsub`，既有 09/10 短状态为终态，目标节点现场为零运行作业，原生仍独占。

唯一原生提交 `2081280`，用户 `wujunyi`，实际 cn22036。创建 UTC 08:20:37，开始 UTC 08:20:40，登录端同 ID 调度交接已发布，按计划进入安全与严格五步。

`2081280` 原版 HBM 严格步在域 4 连续记录 265.06、266.77、273.76 秒。先核当前 ID、所有者、独立路径与 RUNNING，再执行 `dkill -J -y -s RUNNING --comment 'R2: three original HBM updates on domain 4 took 265 to 274 seconds; complete matched rounds do not fit the allocation' 2081280`。监督器收到原生信号 2，有序回收，原生状态 `FAILED`、PID 空，页池已归还。分配 1278 秒，已记录更新 143，按已到达阶段记账 160。传输包 SHA256 `436b6d342f3954e1f2568377c58c8d12cd85098f3ca4f91eebdb606f73e5cd98`。

核前次终态后，私有新版本 `B32_C1_W2` 将同一候选部署到第二台合格候选 cn22044。`RUN=/home/share/wujunyi/opt/stage4_sessions/S00/FULL16_R2_B32_C1_W2`，`PIN=f8eee6715c4387144c77bd06377c3c8f1897c22ac436944ba725aec607c0a4bf`，`PKG=81553384c68b618e996903bd98e408026a2a26f97418e17b5a4a410a433e808c`。与 W1 的 worker SHA 及最小 diff 相同。登录端同链通过，唯一原生提交 `2081519`。创建 UTC 08:44:58，开始 UTC 08:45:02。实际 `hwThreads=0-569` 和继承集合一致，缺注册 NUMA 30 的 570–607，现场 CPU 门拒绝。未启动 worker，分配 5 秒，原生 `FAILED`、PID 空。传输包 SHA256 `7ce2a6c8bab74430b94188d25a6f57c943433284f063fd0b67fb8e4c7c8f57cc`。另取只读 `dnode -J -a cn22044` 的原件，SHA256 `0cd1e5d30ca928c7ec81d71d0fd2661164dfa628a54ab7935fcfac8d6c210508`。

两次终态均通过 `djob -J -l`、固定输入复核、`/usr/bin/python3 -B collect.py "$PIN"` 及 `tar -czf "JOB_${JJ}_TRANSFER.tgz" "JOB_${JJ}_evidence.zip" bundle_receipt.json` 取回。北京时间 16:48 复查两个 ID 均为 `FAILED`、调度 PID 为 `-`，`wujunyi` 活动列表为空。
