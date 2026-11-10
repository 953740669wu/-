# FP32 attention 实际入口

账号 `wujunyi`。使用任务私有目录、原 R4 Python、原 HBM 库和任务卡的独立预算。现场核 `djob -J -u wujunyi`、`dqueue -J -l q_hpcai` 和候选节点 `dnode -J -l`。每次原生实际参数与 SHA 绑定见各版 `RUN_BINDING.json` 及回传的 `submission.command.json`。

```bash
source /etc/profile.d/donaukit_scheduler.sh
cd "$RUN"
printf '%s  %s\n' "$PKG" FULL16_PAYLOAD.zip "$PIN" RUN_BINDING.json | sha256sum --check --strict
unzip -n -q FULL16_PAYLOAD.zip
/usr/bin/python3 -B prepare.py "$PIN"
timeout --signal=TERM --kill-after=5s 60s env -u LD_PRELOAD PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 /home/share/dengqingtian/opt/stage4_sessions/S00/ENV_20261104T130730Z_R4/venv/bin/python3 -B inspect_metadata.py --output LOGIN_METADATA_CHECK.json
timeout --signal=TERM --kill-after=5s 45s /usr/bin/python3 -B recheck_fixed_inputs.py > FIXED_INPUTS_BEFORE.json
nohup /usr/bin/python3 -B submit_once.py "$PIN" </dev/null >login_submit.log 2>&1 &
echo "$!" > login_submit_pid.txt
```

V1_D1 在 `ATTN_R1_V1_D1`，绑定 `a32c452c466a58252f7570a5fd69826cae2908c95738288bc22a27456ff7b4b9`，包 `4f168f4fa91513b540b87ba5dbc2a5758fefb7b751e48c4f0bd174e6f922dd7d`。`2085024` 现场获配 cn22036，实际 38 核集合，计算端拒绝 `stale/future scheduler handoff`，未编译 C、未启动 worker。终态 FAILED、PID 空、子进程清理完成。传输包 `66f4259bd4abf8d812774d80797d9bb79e001db0866fd47110e537a4bb43a033`。

V2_D1 在 `ATTN_R1_V2_D1`，绑定 `b24660823c4a04d134763616d2a291b9091cb4b4fb017ebadd11886f795f82d7`，包 `0cf199ed3c6f3e14ad3bdcfd21e7559dbb185bb421c91acf4e8d321e01da8d57`。仅在原交接期限内最多等 5 秒让本地时钟赶上 header，随后仍执行原时间排序、30 秒新鲜度、nonce、SHA、原生 job ID 与实际 CPU 检查。C 源和 Python 派发的 SHA 与 V1 完全相同。两版的 BQ 均为 64、BF16 为 0。

V2 原生 `2085051`，cn22036，实际 1 域、38 分配/36 实际。交接首读时 header 领先约 81 毫秒，实际等待约 100 毫秒后通过。计算端原命令见 `job_evidence/attn_compile.command.json`、`attn_link.command.json`。原版参考 5/5，候选因 CPU36 库枚举失败而未启动更新。终态 FAILED、PID 空、后代和页池均清理。传输包 SHA256 `8c8ff4bf2c0be97003bb418cd3bc27d5011aebc933d2742802ac7b6285e71f6d`。北京时间 22:17:37 现场复查两个原生 ID 均终态，`wujunyi` 活动列表为空。

终态收集顺序为 `djob -J > post_job_queue.json`、`getconf CLK_TCK > login_clock_ticks.txt`、原固定输入复核到 `FIXED_INPUTS_AFTER.json`、`/usr/bin/python3 -B collect.py "$PIN"` 和 `tar -czf "JOB_${JJ}_TRANSFER.tgz" "JOB_${JJ}_evidence.zip" bundle_receipt.json`。本地先核传输 SHA，再核归档清单和计算证据。
