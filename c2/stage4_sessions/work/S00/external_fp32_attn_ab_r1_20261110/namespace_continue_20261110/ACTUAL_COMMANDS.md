# FP32 attention 命名空间接续实际入口

旧 V1/V2 和协调审核引用保持冻结。由 V2 派生 `M1_NS1_D1`，累计预算仍从 11 月 10 日 22:04:34 起算。启动前现场确认 `wujunyi`、`q_hpcai`、两个原生旧 job 已终态且 PID 空、活动作业为零，cn22036 空闲。此版本仍属数学候选 `M1_FP32_BQ64`，只修加载身份。

运行目录 `/home/share/wujunyi/opt/stage4_sessions/S00/ATTN_R1_M1_NS1_D1`，绑定 SHA `44be42846b7264bc5c32a2d9c5d04328ab336d84dcfef443e3b9c0b6201fe9c2`，包 SHA `eeef129d0ecd1884ca07f3e85fe25ae33a4ab87679b6275cd46a68ad21a15acf`。使用旧卡的 SHA、Linux 入口、元数据、固定输入及 `submit_once.py` 单提交命令。原生提交参数以本版 `RUN_BINDING.json` 和实际 `submission.command.json` 为准。

修复使用 `dlinfo` 从 `dlmopen` 返回的句柄查询 `LMID` 和 `link_map`，核 `cblas_sgemm` 归属相同映射。Python 将此实际句柄交给 CPU36 枚举，仍要求映射中的路径及 SHA 一致。其它映射库仍走原 `RTLD_NOLOAD` 路径，所有 TID、36 线程及原基础库验收继续。加载器接口依据 [Linux dlinfo 手册](https://man7.org/linux/man-pages/man3/dlinfo.3.html)。

终态使用 `djob -J`、`getconf CLK_TCK`、固定数据 SHA 复核、`/usr/bin/python3 -B collect.py "$PIN"`，然后 `tar -czf "JOB_${JJ}_TRANSFER.tgz" "JOB_${JJ}_evidence.zip" bundle_receipt.json`。本地核 SHA 后运行 `settle_ns.py`，保留原终态、数值和 A/B 核验，同时新增候选命名空间及各检查点亲和性复核。

实际 `2085664`，cn22036 物理域 0，UTC 15:27:33 创建、15:27:36 获配，原生 FAILED。候选实际执行第 1 个更新后原比较器拒绝，监督器停止所有后续阶段。独立命名空间实际为 `LMID=1`，36 个 TID 检查完整。传输包 SHA `fd65ef971ed186431d624ca61e108dbb8718fc3e5d05836d000ffdbb963373ec`。北京时间 23:31:54 复查 `2085024`、`2085051`、`2085664` 均终态、原生 PID 空，`wujunyi` 活动作业列表为空。
