# M23 实际命令与证据口径

北京时间 2026-11-08。两个作业使用相同的 16 电极 Encoder/B64/fp32 训练、1600 帧与原比较器。CKPT6 仅包装前 6 个 Transformer 层，使用已有 non-reentrant checkpoint 实现。性能阶段为每侧独立进程、先 CKPT0 后 CKPT6、各 25 次更新，前 5 步预热。相同 job 内按相同帧、掩码、初态、优化器、CPU 绑定和 DDR 放置配对。

## 连接、冻结和提交

交互 SSH 连接 `dengqingtian@10.44.9.4:22`，实际登录落点为 `login03`，使用已确认 known_hosts 池并维持严格主机校验。用 SCP 上传各轮 `M23_PAYLOAD.zip` 和 `M23_RUN_BINDING.json`。登录端只在 M23 的相应目录写入，原 00 实时查询仅用 `djob -J -l 2060643`。两轮提交前均实时核验 `djob -J`、`dqueue -J -l q_hpcai`、`dnode -J -l cn21340` 和 `dsub --help`。

| 轮次 | 远端目录 | 绑定 SHA256 | 包 SHA256 |
|---|---|---|---|
| 单域 | `/home/share/dengqingtian/opt/stage4_sessions/M23_MEMORY_HBM/M23_R1_20261107T160435Z` | `29a57cf85ad6a903b75949e6904cfc7912d0fe77f3cdb8452817e0e7978a7a2a` | `3c5a6356d58ca79c303bc73d23ad58e0878d89725d4cf1a53b387d5cb8b16ac9` |
| 四域 | `/home/share/dengqingtian/opt/stage4_sessions/M23_MEMORY_HBM/M23_R2_20261107T161206Z` | `6992637f216cfe77f9da867093e80b255040142a905dca12bfeaf31a403ed448` | `171ff130143f306ccc120b314610bdfaf3de1f47bde050e5f309dc70b6755c2b` |

每轮在各自目录执行以下命令，`PIN` 与 `PACKAGE_SHA` 为上表值。

```bash
source /etc/profile.d/donaukit_scheduler.sh
printf '%s  %s\n' "$PACKAGE_SHA" M23_PAYLOAD.zip "$PIN" M23_RUN_BINDING.json | sha256sum --check --strict
unzip -n -q M23_PAYLOAD.zip
/usr/bin/python3 -B prepare.py "$PIN"
timeout --signal=TERM --kill-after=5s 60s env -u LD_PRELOAD PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 \
  /home/share/dengqingtian/opt/stage4_sessions/S00/ENV_20261104T130730Z_R4/venv/bin/python3 \
  -B inspect_metadata.py --output LOGIN_METADATA_CHECK.json
timeout --signal=TERM --kill-after=5s 45s /usr/bin/python3 -B recheck_fixed_inputs.py > FIXED_INPUTS_BEFORE.json
nohup /usr/bin/python3 -B submit_once.py "$PIN" </dev/null > login_submit.log 2>&1 &
echo $! > login_submit_pid.txt
```

原生提交命令从各轮 `received/submission.command.json` 取得。共同参数为 `dsub -J -q q_hpcai -x job -nl 'cn[21338-21504] !cn21340' --env none`。单域资源为 38 CPU、24576 MB DDR request=limit，`numa[count=1,distribution=pack]`，墙钟 1200 秒。四域资源为 152 CPU、98304 MB DDR request=limit，`numa[count=4,distribution=pack]`，墙钟 1800 秒。计算端每域选择 36 核并留 2 核。每阶段进入 `run_worker.sh` 前恢复完整分配集合，所有子进程启动后观察进程再收窄。

各阶段真实 argv 在 `received/job_evidence/{strict,perf_baseline,perf_candidate}/node*.command.json`。真实库映射和 SHA 在各 worker 的 `result.json`。复用 C2 已有 KML、OpenMP 和 SGEMM shim。四域在计算端只读查询 `/usr/bin/cc -print-file-name=libubsan.so` 和 `-print-file-name=libubsan.a`。这两项无可读路径，因此 M23 未执行分配器编译或预加载。

## 取回和校验

每轮终态后保存 `djob -J -l <job>` 原件，再运行原固定输入 SHA 核验并保存 `FIXED_INPUTS_AFTER.json`。使用本目录 `collect_evidence.py` 的相同源码作为标准输入，执行 `/usr/bin/python3 -B - <job>`，生成独立 ZIP 与回执。SCP 下载后使用 `python -B analyze_evidence.py <本轮目录>` 校验 ZIP CRC、整包 SHA、每个文件的 SHA 和大小，并从原始 worker 结果生成 `REVIEW.json`。远端 mtime 以索引原始元数据保存。

- 每步在计时前写 `/proc/self/clear_refs=5` 并验证 VmHWM 重置为当时 VmRSS。计时后、检查梯度和状态前立即读训练步 VmHWM。进程 RSS 包含共享库，不能从 RSS 分离 allocator 仍保留的 DDR 内存，也不等同于唯一物理工作集。
- `numa_maps` 是第 6 步前及第 25 步后分别取得的普通页和大页快照。四域各进程峰值来自各自步内，不求和当作同一时刻物理驻留。
- 仅严格首步以 autograd hook 去重统计前向保存的底层存储。按存储指针排除已识别权重和输入，同一存储多视图只计一次；形状是代表视图。临时分配及反向重算不属于这个口径。
