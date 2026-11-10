# 16 域逐步屏障 A/B

本批独立记账。复用 job `2064138` 已归档的原 SDPA、FP32 KLinear、32 电极 B32、CKPT12 和 HBM。前五步的输入、掩码、损失和 KML 轨迹使用原归档 DDR 参考核对。A/B 同一个固定窗 worker 先 A 后 B，各自从冻结初态启动。预热仍用原逐步屏障，开窗按第六步统一放行的本机单调时钟。第七步开始，A 继续等全域，B 各域独立推进。

观测窗严格 600 秒，按 `open <= start < close` 且 `end <= close` 独立逐域计数。跨窗列原始开始/结束和窗外耗时。重复数据时每本域 25 步为一轮，精确循环冻结的 800 个样本索引与 25 份掩码，不重新抽样。每组 `/dev/shm` 共用 2000 次启动计数器含预热，合计最多 4000 次。计数器只作本机预算原子预留，B 无逐步等其它域的协议。

`wujunyi` 的 `q_hpcai` 现场开放、账号无活动作业。选历史物理域 12 慢域的 cn22035，原生提交前核空闲 608 核及 64640 页，获配后核实际域、CPU 集合、DDR 与逐域 HBM 页池。

```bash
source /etc/profile.d/donaukit_scheduler.sh
RUN=/home/share/wujunyi/opt/stage4_sessions/S00/STEP_AB_R1_20261111_D16
PIN=db43f6a1ef2b1a8b733bdab9682b2d19dcdc8844fe719759198532114273a92c
PKG=49ecd7255a91f9199e009d899ebe5c92049fcca981d800d29d60d7547f9dedf9
cd "$RUN"
printf '%s  %s\n' "$PKG" FULL16_PAYLOAD.zip "$PIN" RUN_BINDING.json | sha256sum --check --strict
unzip -n -q FULL16_PAYLOAD.zip
/usr/bin/python3 -B prepare.py "$PIN"
timeout --signal=TERM --kill-after=5s 60s env -u LD_PRELOAD PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 /home/share/dengqingtian/opt/stage4_sessions/S00/ENV_20261104T130730Z_R4/venv/bin/python3 -B inspect_metadata.py --output LOGIN_METADATA_CHECK.json
timeout --signal=TERM --kill-after=5s 45s /usr/bin/python3 -B recheck_fixed_inputs.py > FIXED_INPUTS_BEFORE.json
nohup /usr/bin/python3 -B submit_once.py "$PIN" </dev/null >login_submit.log 2>&1 &
echo "$!" > login_submit_pid.txt
```

唯一 job `2085843`，UTC 2026-11-10 16:08:21 创建、16:08:24 开始，cn22035。实际原生 argv 和运行身份见 `AB_D16/RUN_BINDING.json` 及回传的 `submission.command.json`。

原生成功终态。通过 `djob -J`、`getconf CLK_TCK`、固定输入复核、`/usr/bin/python3 -B collect.py "$PIN"` 及 `tar -czf JOB_2085843_TRANSFER.tgz JOB_2085843_evidence.zip bundle_receipt.json` 取回。传输 SHA `d730b18feadd0137b149602029a0683a4088224b4d7d1480f615e866859ea3bb`，内包 1082 成员。北京时间 01:19:48 核到 PID 空、`wujunyi` 活动列表 0。16 域 HBM 池、所有自有进程和 `/dev/shm` 预算文件均清理。A/B 各 128/946 个启动预留，合计 1074 次。
