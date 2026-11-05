# S07 R3：只修S00启动包装层，待协调核包

本轮不提交S07 job。不修改原R2 ZIP内34文件、候选、模板、22项原检查或四项小张量判据。旧2039114失败不覆盖。新层19项标准库检查仅为模拟交接正负控；不证明两域、Torch/Gloo或通信通过。

登录端读取当前job原始djob输出；计算端先原子写独有request，登录端写原始JSON/查询回执，最后原子写ready。每个文件先在同目录完整写临时文件、flush/fsync，再os.replace；ready之前不读raw。nonce、request SHA、raw SHA、30秒新鲜度及现场job/host/CPU/资源均核对，不能重用旧文件。每个输出必须不存在；源目录必须是独立新目录。

计算端CCS_JOB_ID仅从调度器原生环境继承，JSON不设置该变量。等待30秒、CLI单次查询5秒，无自动重试。错误在Torch/worker之前拒绝；成功后还须原冻结CPU36 sysfs拓扑检查与R2父/worker身份门槛。原22项全通过、environment exit0后才运行原normal/crash/collective-timeout/watchdog；未改后端/数值/故障判据。

## 外部前提

- 登录端：`/etc/profile.d/donaukit_scheduler.sh`实际存在；其CLI为`/opt/batch/cli/bin/dsub`、`/opt/batch/cli/bin/djob`。publisher通过已有PATH解析djob并记录实际绝对命令。登录端能读取当前job原件、写账号共享新目录。
- 计算端：不要求登录profile或djob。原生CCS_JOB_ID、Linux sysfs/affinity、`/usr/bin/python3`、`/usr/bin/bash`可用；38核NUMA合同来自冻结R2，不把主机可见CPU当授权。
- 共享新目录只能在`/home/share/dengqingtian/opt/stage4_sessions/S00/`下，basename以`S07_R2_TWODOMAIN_R3_`开头；两端是同一目录、文件锁定单producer，时钟同步到30秒门槛内。
- 沿用`/home/share/dengqingtian/opt/stage4_sessions/S00/ENV_20261104T130730Z_R4/venv/bin/python3`及其现有依赖；torch2.7.1+cpu来自`/home/share/songzhenlong/eitfm/sw/torch_kml`，Gloo必须可用，不安装或更换软件。
- 原LD_LIBRARY_PATH仍为`/opt/HPCKit/kml-lib/sme/kblas/multi:/opt/HPCKit/kml-lib:/opt/HPCKit/bisheng-lib`；不加载KML shim/模型/HBM。S07不依赖S06的C++编译器。
- 调度资源：单节点两个不同完整38物理核NUMA域，76分配/每域前36实际、每域末2留空；总24576MB且同值limit、exclusive、300秒、HBM0。没有合法授权即停止，不另试方案。

## 将来复核获准后的精确命令（本轮未执行）

先将已核ZIP解压至全新RUN，保持文件原字节。以下仅是未来入口，不授权执行：

```bash
set -euo pipefail
RUN=/home/share/dengqingtian/opt/stage4_sessions/S00/S07_R2_TWODOMAIN_R3_<新的UTC标识>
cd "$RUN"
sha256sum -c ARTIFACT_SHA256.txt
/usr/bin/python3 -B prepare.py
# 只做新交接层模拟检查，不运行Torch或worker。
/usr/bin/python3 -B tests/test_scheduler_handoff.py
# 以下source、dsub和publisher都只在登录节点执行。
test -f /etc/profile.d/donaukit_scheduler.sh
source /etc/profile.d/donaukit_scheduler.sh
(set -o noclobber; printf '%s\n' 'reviewed R3 once only' > submit_once.marker)
dsub -J -q q_hpcai -x job -R 'cpu=76,mem=24576MB' -RL 'mem=24576MB' \
  -a 'numa[count=2,distribution=pack]' -T 300 --env none --cwd "$RUN" \
  -oo "$RUN/job.log" bash "$RUN/run_s07_r2_job.sh" > submission.json 2> submission.stderr.txt
JOB=$(/usr/bin/python3 -B -c 'import json; print(json.load(open("submission.json"))["data"]["jobId"])')
djob -J -l "$JOB" > scheduler_observed.json
# 确认RUNNING后立即调用一次；若PENDING只观察，不提前触发30秒publisher窗口。
/usr/bin/python3 -B scheduler_handoff.py publish --root "$RUN" --job-id "$JOB" \
  > login_publish.log 2>&1
```

程序自行记录完整查询命令/退出、raw原文、request/ready、接收回执及逐rank allocation。publisher失败后不覆盖输出/重发：计算端有界拒绝，S00观察终态并回传全部失败原件。消费者270秒外层预算已包含30秒等待，清理仍沿用原S00监督层，job总300秒。原候选各case仍有原30秒监督截止，不能延长以掩盖失败。

回传pre-submit、全部交接原件/回执、调度终态、标准库22项、environment、四case的manifest/rank日志/summary/checks及bytes/SHA/原mtime_ns。S06同协议单域正路径若已实测也不代替S07两域验收。
