# S00：S02 R5 CPU36 C2/KML严格数值对照

日期：2026-11-05（Asia/Shanghai）。状态：**READY_FOR_REVIEW / EXECUTED / FAIL_ORIGINAL_CRITERIA / COMPLETE_EVIDENCE_RETURNED**。

## 1. 结论

按总协调S00_NEXT_S02_R5_S03_C_20261105.md及本轮用户授权，原样执行S02 R5的一组固定case严格对照。**job2034953 / cn21338 / 11:50:49–11:51:18 +08**，调度FAILED、job/checker均退出 **1**，result.status=**FAIL_ORIGINAL_CRITERIA**。

完整1063项原判据指标中 **95项失败：9个梯度、18个更新后参数、52个参数增量、16个AdamW状态指标**。loss、本轮输出及输入梯度组均通过，但不能覆盖参数/更新/状态失败。原阈值保持不变，没有重跑或扩大配置。

实际前提与数值失败分开：case/加载权重与张量身份通过，真实KML GEMM **447次/34种记录形状**，同PID 7个CPU checkpoint完整、实际Torch36、无CPU错误/越界，库身份结束重验通过。无identity/allocation运行错误或超时。本结果不能归类为“环境未运行”或“数值通过”。

S02数值门槛仍未过，不执行训练内存或真实HBM。历史Windows194项失败保留，本轮C2/KML环境及case身份单独记账，不把失败数量变化当作优化收益。

## 2. 前置依据、包/case身份与远端门槛

已完整读取集中执行说明、S02_CPU36_R5_REVIEW、R5 C2_HANDOFF、实际包装器与守卫；R7启动已被总协调及S01接受，不再运行R7或Windows完整实验。

- 原样代码包50873字节，SHA256：**64605deb9a08de087a42f9026272a18bfed1d1896acdd449852ed2837aa43003**。
- 固定case为R3原文件fixed_16_pre.pt，271979513字节，SHA256：**4de1fb40eb1c4b43a8747586399f336bf9e37184592d66fdbf711abad8469846**。
- 本机未复制/生成case，直接上传用户允许的同一原文件；运行后远端大小/SHA再次一致。完整证据包不包含或下载这个.pt。
- ZIP20成员、19项SOURCE_SHA256原样核对；远端20文件SHA、case SHA/大小、3个shell/env的字节LF与真正Linux bash -n、12个Python文件在系统Python3.9下编译检查通过。提交时再次核对实际文件及语法。

新远程目录：

```text
/home/share/dengqingtian/opt/stage4_sessions/S00/S02_CPU36_R5_20261105T034705Z/
```

先核当前账号队列，没有此组任务；使用新目录及submit_once.marker，仅提交一次。登录方式沿用用户已确认主机指纹的严格SSH校验，落点login02，密码未写入文件。

按审核说明修正的是**提交层**：source冻结runtime.env后重新source /etc/profile.d/donaukit_scheduler.sh，确认command -v dsub为/opt/batch/cli/bin/dsub后才提交。submission.json记录该事实和完整命令；原R5包未修改。

仅写S00；S02作者目录、原模型/loader/比较器/配对协议/阈值、固定case、共享库、生产数据和manifest均未改。R7/R6及2026356历史证据SHA核对不变。

## 3. 实际环境、配置、资源、命令与成本

账号dengqingtian，q_hpcai，cn21338，exclusive=true。新job分配38个同域物理核心0–37，模型计算前在checker**同一PID 2081719**收窄到0–35共36核，预留36/37；不是用整机608核冒充授权。NUMA域0，numactl先保留原授权集合以便同PID复核，框架导入前即收窄selected36。

解释器为已核实R4 venv：

```text
/home/share/dengqingtian/opt/stage4_sessions/S00/ENV_20261104T130730Z_R4/venv/bin/python3
```

实际Python3.9.9、torch2.7.1+cpu、numpy1.26.4、真实KML/shim/BiSheng OpenMP。C组环境OMP36/MKL36/OpenBLAS1/cores/close；实际Torch intra-op36，interop照实记录，不把它当实际创建的线程数。实际库路径、SHA、GEMM计数/形状及结束复核全保留在result.runtime。

唯一配置：16_adjacent/pre、backend=kml/mode=strict、有效B64对micro32×2、fp32/CKPT0/fresh/HBM0、原完整encoder/U-Net、原AdamW定义。输入S02_PAIRED_BELT_V1固定合成case及相同初权重/固定随机张量；不是legacy四帧计时或正式数据划分/效果测试。

调度resAlloc cpu=38,mem=24576；resLimit.mem=24576；wallClockLimit=900秒，内部780秒+15秒退出宽限。资源回执未被拿来伪称已独立读取不可见cgroup硬限。实际入口：

```bash
env S02_CASE_FILE="$RUN/fixed_16_pre.pt" bash "$RUN/payload/run_s00_job.sh"
```

完整dsub、起止/命令/日志见submission.json与djob_final.json。实际开始结束差 **29秒≈0.008056独占节点小时**，包括本次失败；该检查器保存参考/候选快照、包含比较开销，不将其墙钟换算训练吞吐或训练峰值。最终PID字段为“-”，确认正常结束/清理后才提交独立S03。

## 4. 严格数值与CPU/后端证据

原标准不改：逐张量max_abs与L2 relative；一般tensor绝对≤2e-5、相对≤2e-6；AdamW state绝对/相对≤2e-6；参考norm≤1e-8时仅判绝对。结构/finite/缺失梯度等继续用原比较器规则。

| 组 | 指标数 | 失败数 | 本组最大abs | 本组最大L2 relative |
|---|---:|---:|---:|---:|
| loss | 1 | 0 | 0 | 0 |
| input_v | 1 | 0 | 1.38243e-7 | 4.17910e-7 |
| input_y0 | 1 | 0 | 6.54836e-11 | 2.86099e-7 |
| output | 3 | 0 | 1.52588e-5 | 7.87515e-7 |
| grad | 153 | 9 | 1.02234e-2 | 1.18959e-5 |
| param | 299 | 18 | 1.95150e-4 | 7.19393e-1 |
| delta | 299 | 52 | 1.95150e-4 | 7.19393e-1 |
| state | 306 | 16 | 1.56250e-2 | 2.30338e-5 |

列中各组最大绝对与最大相对可能来自不同张量，不能拼成一个张量。完整逐项metrics/failures、optimizer_details、adjoint_differences及float64 detached score均原样回传。第一个失败grad.enc.mask_tok：max_abs=0.001953125、relative≈2.62608e-7，按原绝对阈值失败；没有因相对较小自动放宽标准。

7个有序同PID checkpoint为before_framework、after_framework、after_backend、before_reference、after_reference、after_candidate、publish。全部可见TID记录完整、mask非空且属于selected36；框架后实际Torch36；errors=[]。close下主线程可以是合法单核子集。本包无常驻采样，不冒称checkpoint之间每个瞬间已验证或复用R7的父采样。

## 5. 性能/内存及诊断边界

本轮仅为一次严格数值对照。没有速度/内存收益接受结果、训练内存测试、HBM、checkpoint矩阵、额外因果模式、四域/整节点或生产部署。保存对照快照的checker峰值不能作为训练峰值。

本结果保留95项原判据失败，下一步交S02分析。不能将loss通过当作一次AdamW更新等价，也不能以新阈值/eps/冻结参数、少算样本或更改case取得PASS。

## 6. 完整回传与停止状态

完整 **41文件**已回传，zip、逐文件SHA/bytes/原始mtime_ns核对通过；20项payload源文件与原包一致，case运行后SHA/大小一致。模型/阈值无变动，未做数值重试。数值FAIL且资源/进程边界正常，按集中说明继续了独立S03 C检查；不是自动放开训练内存/HBM。

本项结论为**FAIL_ORIGINAL_CRITERIA**，不是基础设施错误。待S02和总协调审核/原因分析；本轮范围已结束，不新增数值矩阵。

本地终检另观察到共享目录新建Git及5个快照/配置说明文件。108原始文件SHA未改；外部新增单独登记于evidence/workspace_git_additions_20261105.json，首次新增检测失败记录保留，S00未操作Git/暂存区。

## 7. 证据索引

绝对根：E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S00。

- evidence/s02_r5_s03_c_20261105/JOB_2034953_full_evidence.zip：完整41文件，SHA256 **dc36ad1896eb54484588a11992c6c42d3fc20167e52ac8a05abb6bf6c99bd636**。
- evidence/s02_r5_s03_c_20261105/S02/received/job.log、djob_final.json、submission.json、pre_submit_checks.json、COLLECTION_S00.json及case_identity_after.json：完整作业、资源/命令、提交门槛、源/时间及case核对。
- evidence/s02_r5_s03_c_20261105/S02/received/payload/evidence/c2_2034953_strict/：全部identity、allocation、placement、command、stdout_stderr、checker_exit_code及result.json。
- evidence/s02_r5_s03_c_20261105/S02/review.json：独立证据复核与计数。
- evidence/s02_r5_s03_c_request_20261105.json、execution_packages/S02_CPU36_R5_CODE.zip：授权/版本/case身份与实投包。
- candidate/audit_s02_r5_s03_c_delivery.py、collect_pair_evidence.py：只复核/收集数据，不重跑模型。
- ARTIFACT_SHA256.txt、evidence/source_integrity.json、delivery_validation.json：当前交付物及108原始项目文件不变终检。
