# HBM_LIB 认证及 BF16/BQ16 条件续跑

登录为 `wujunyi`，队列 `q_hpcai`。新目录逐一创建。原生提交只有 `submit_once.py` 一处，依据独占队列、活跃作业、节点资源、固定输入、期限和一次标记执行。两次作业均使用 `cn22036` 的单域分配。

| 版本 | Job | 远端目录后缀 | RUN_BINDING SHA-256 | 部署包 SHA-256 |
| --- | --- | --- | --- | --- |
| C1 | 2086632 | `HBM_CERT_20261111_C1` | `8877b54b023c4600c616dc324bcdcc4afe360b6a1e915aef7973a135c7a0908d` | `b98f45c1cb392b79bba91fa64b92e66e7db4ae03ecc397a865381d67baa0bdf9` |
| B1 | 2086656 | `HBM_CERT_20261111_B1` | `d2b3a2bc7fca78456cd28343d0be919f47448b8c1cefe732df005b37e73f643f` | `5ca05a676ee14ff7ef3a49dda154a886563b1112769fe1ac501548dc5ede38ed` |

以下为已执行的命令链，`RUN` 取 `/home/share/wujunyi/opt/stage4_sessions/S00/` 拼接上表后缀。`PIN` 和 `PKG` 取对应行 SHA。上传独立目录的七份对象为 `FULL16_PAYLOAD.zip`、`RUN_BINDING.json`、`FROZEN_HBM_ALLOCATOR.so`、`DEPENDENCY_RECEIPT.json`、`ENGINEERING_DESCRIPTOR.json`、`PRIOR_PAIRING.json` 和 `MINIMAL.diff`。B1 冻结绑定另含 C1 通过结果 SHA `23cd31191d06b14742dd39b4bd83341b7d70141e9c7552fb0e8986fbda34b6f2`。

```bash
source /etc/profile.d/donaukit_scheduler.sh
cd "$RUN"
printf '%s  %s\n' "$PKG" FULL16_PAYLOAD.zip "$PIN" RUN_BINDING.json | sha256sum --check --strict
unzip -n -q FULL16_PAYLOAD.zip
/usr/bin/python3 -B prepare.py "$PIN"
timeout --signal=TERM --kill-after=5s 60s env -u LD_PRELOAD PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 /home/share/dengqingtian/opt/stage4_sessions/S00/ENV_20261104T130730Z_R4/venv/bin/python3 -B inspect_metadata.py --output LOGIN_METADATA_CHECK.json
timeout --signal=TERM --kill-after=5s 45s /usr/bin/python3 -B recheck_fixed_inputs.py > FIXED_INPUTS_BEFORE.json
nohup /usr/bin/python3 -B submit_once.py "$PIN" </dev/null > login_submit.log 2>&1 &
echo "$!" > login_submit_pid.txt
```

一次提交工具实际使用的原生参数如下。具体 `argv` 和响应在各自的 `received/submission.command.json` 及 `received/submission.stdout`。

```bash
dsub -J -q q_hpcai -x job -nl 'cn22036 !cn21341 !cn22044' -R cpu=38,mem=24576MB -RL mem=24576MB -a 'numa[count=1,distribution=pack]' -T 1800 --env none --cwd "$RUN" -oo "$RUN/job.log" bash "$RUN/run_job.sh" "$PIN"
```

仅在 `djob -J -l "$J"` 确认终态后收集。取回的 tar SHA 在逐作业分析与累计账本中。

```bash
J=$(cat job_id.txt)
getconf CLK_TCK > login_clock_ticks.txt
timeout --signal=TERM --kill-after=5s 45s /usr/bin/python3 -B recheck_fixed_inputs.py > FIXED_INPUTS_AFTER.json
djob -J -u wujunyi > post_job_queue.json
/usr/bin/python3 -B collect.py "$PIN"
tar -czf "JOB_${J}_TRANSFER.tgz" "JOB_${J}_evidence.zip" bundle_receipt.json
sha256sum "JOB_${J}_TRANSFER.tgz"
```
