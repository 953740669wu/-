# S01 R7：36核模型运行器候选复核

日期：2026-11-05。复核对象：`work/S01/revisions/R7_CPU36_RUNNER_20261104T151540967239Z`，work/相对c2/stage4_sessions。

## 决定

**ACCEPTED_LOCAL_CANDIDATE_FOR_BOUNDED_STARTUP / C2_MODEL_ACCEPTANCE_PENDING**。

接受 S01_CPU36_MODEL_R7_20261104 作为下一次单域36核完整启动小试的候选。不是生产部署、正式数值/性能接受，也不解锁S02或训练内存。

## 独立复核结果

- 复跑 `tests/test_cpu36_pipeline.py CPU36Pipeline`：48项中47通过、1项Linux进程组清理跳过。覆盖真实发布/汇总合同、单核TID合法、越界/缺证据/Torch1拒绝，以及原缺域/旧JSON/失败/超时等保护。
- 27项交付索引哈希匹配，ZIP内11文件与本地来源逐字节一致；shell/env原始字节无CR。
- 包 SHA256：`288a74181c36ec87b3953be5cde7e26575e45c219e9f446a21fca0683659119c`。
- 报告 SHA256：`5f974cce8e556e6b15bb58ab6e1ba60b2fc059f24759587663dea83d9165bf3c`。
- 审查了cpu36_contract、runner的新预检/线程采集/监督/汇总路径和两个接口脚本。固定C组OMP36/MKL36/OpenBLAS1/cores/close；选择同域前36物理核、预留末2；实际Torch36及全TID边界同时核查，保留调用线程真实掩码，不将其伪写为全集。
- 同job导入预检与实际模型证据分开；预检引用核对job/host/source/input/library/CPU/environment，模型仍需独立产生阶段与父监测证据。模型计算AST回归通过，未修改冻结数据或optimizer定义。

本聊天未SSH、提交作业或执行EIT模型。新版本的实际Linux线程采集、完整模型链和清理仍须本次新job验证；本地mock与静态检查不替代。

## 下一项交 S00

使用R7新包和 `INTERFACE_FOR_S00_S02.md`，在当前账号自己的全新目录落包。库与旧demo从已核实来源只读复制，保留LEGACY_TIMING_ONLY，不改变原输入/阈值。

仅安排一次完整启动小试：单38核域分配、实际选36核/预留末2核，24576MB及同值限制、最多900秒；HBM0/CKPT0、16_adjacent pre+dec、B32、fp32/KML、三轮REPS1。不得复用旧38/4核包、旧job或旧运行目录，不扩大配置。

远端实际包/9项payload/source清单、全部shell/env LF、真正Linux bash -n、Python语法及实际授权资源核对通过后才能提交。实际job内以 `interfaces/run_s01_startup36.sh` 执行同job新鲜预检和模型入口，不拿旧预检代替；该入口原样保留一次性marker与超时。

失败或UNSTABLE即停止、保留全部结果，不改检查或挑选轮次。R7的活TID采集采取保守拒绝；若出现自然线程退出等采集缺口，应交S01分析，不在现场删除检查求PASS。

回传完整job分配/终态、预检、manifest/summary、各轮模型结果与状态、所有thread checkpoint/monitor采样、命令/日志/ABORT、SOURCE身份及原始mtime_ns/bytes/SHA。离线汇总在独立副本按真实mtime元数据复核，不改received原件。

本次三轮REPS1仍只是完整启动/合同验收，不能单独作为正式速度、稳定性、数值等价或模型效果结论。通过后再审核S02的36核同PID包装接口与一组C2/KML等价小试；S02严格数值失败和训练内存NOT_READY状态保留。

## 可转发给 S00

```text
总协调已接受S01 R7本地候选，用于一次有限36核完整启动小试。
请读 work/COORDINATION/CPU36_RUNNER_R7_REVIEW.md
及 work/S01/revisions/R7_CPU36_RUNNER_20261104T151540967239Z/INTERFACE_FOR_S00_S02.md（work/相对c2/stage4_sessions）。
使用R7新包、新目录和新job，单域分配38核、实际36核留2核，24GiB、最多15分钟。
远端SHA/LF/Linux语法等门槛通过后，按接口执行同job新鲜预检和16电极pre/dec、B32、HBM0/CKPT0、三轮REPS1。
失败或UNSTABLE即停止，不扩大或现场弱化检查。
回传完整模型/线程/退出/库及原始mtime证据，交S01和总协调复核。
本轮不提交S02或训练内存测试。
```
