# LF 恢复小试复核：真实模型已运行，线程/绑定合同未通过

日期：2026-11-04。依据 S00/S01_LF_RESTART_REPORT.md 与 evidence/s01_lf_restart_2026450 的完整回传。本聊天未连接集群或提交作业。

## 决定

接受本轮运行与失败证据。**模型执行已到达，S01完整启动验收仍不通过；不推进S02，不在原配置下盲目重提。** 下一项归S01诊断线程配置与绑定合同，S00保留集群执行职责，等待明确诊断方案。

## 独立复核事实

- 完整证据包 SHA256 为 1403bb4c5ba5032eb16df5aab4b3acd7836b6edd692db4ccc2b5626df0cbe87d，与报告一致；包内19个文件与received副本逐字节相同。
- job2026450/cn21340，模型首轮子进程exit0、timed_out=false；16-pre/dec前后向及AdamW已执行，产生r1_d0.json。
- manifest的首轮预期CPU集合为0–37；模型结果run.affinity为[0]，run.omp_threads为38，gpu描述为`aarch64 cpu, 1 threads`。
- 保存的summary为FAIL，原错误为actual CPU affinity mismatch；job exit1。sync_r2不存在，没有第2/3轮、S02或内存测试。
- cluster_runtime.env明确设置MKL_NUM_THREADS=1、OPENBLAS_NUM_THREADS=1及初始OMP_NUM_THREADS=1；worker再将OMP_NUM_THREADS设置为38。这些实际配置值得优先隔离，但尚不能把MKL变量认定为唯一根因。

调用线程的[0]不能代表所有工作线程只用一个CPU。OpenMP绑定可能收窄单个线程掩码；另一方面torch.get_num_threads为1又是必须核实的独立信号。现有数据没有全部TID与真实算子阶段证据，既不能接受38核配置，也不能断言整个线程池只有1核工作。

## S01 下一项

1. 读取本次实际manifest、r1结果、状态、summary、commands、预检和rank日志，核对接受候选与本轮payload SHA。
2. 准备最小计算节点诊断：在框架初始化前、torch导入后、KML首次调用后采集调用线程及全部相关TID的允许CPU集合、实际intra/inter-op线程数、OMP/MKL/OPENBLAS设置、实际OpenMP/BLAS库路径和身份。小试只需受控小算子，不先重复完整模型。
3. 分开定义“调度授权的CPU集合”“每个线程的绑核集合”“实际算子使用的线程数”。每个线程都必须留在授权集合内，不能要求被绑定的每个TID都等于整个授权集合；仅看线程集合并集也不足以证明模型按目标线程数运行。
4. 对MKL_NUM_THREADS=1等可能覆盖项做有限单变量对照，给出证据再提出环境最小修复。若需修改runner/发布字段/验收逻辑，在S01新修订目录实现并补正负测试，保留R2，不删除绑定检查或扩大CPU权限求PASS。
5. 诊断结论与候选经复核后，再由S00按明确范围执行一次恢复小试。没有明确诊断前不继续同配置重投；S02仍等待。

## 回传与离线验收的附加问题

本地解包后的r1文件mtime已不在远程进程的时间窗内。直接在received目录调用原summarize(completed_rounds=1)返回stale/future result mtime，先于原远程affinity错误。该本地结果不能当作远程原失败原因，也不能据此推断原文件过期。

本次collection清单记录字节数和SHA，没有原始mtime_ns。后续回传应附带文件原始mtime_ns及其来源，并在独立临时复核目录恢复时间属性或使用明确的归档复核模式；源/结果身份与SHA仍必须检查。不要改写received原件，或凭进程结束时间伪造一个mtime来获得PASS。

## 给用户转发到 S01 的指令

```text
S00已返回job2026450完整结果，模型首轮已执行，但CPU affinity合同失败。
请读取 work/S00/S01_LF_RESTART_REPORT.md 和 work/COORDINATION/AFFINITY_REVIEW_20261104.md（work/相对c2/stage4_sessions）。
优先核对：期望CPU0–37、调用线程affinity=[0]、OMP_NUM_THREADS=38、torch.get_num_threads()=1，以及MKL_NUM_THREADS=1。
先准备小型线程/绑定诊断，区分调用线程与全部工作线程，核实环境变量及运行时的影响。
提出最小环境或验收合同修复，保留绑定检查及授权CPU边界，补正负测试；不要仅删除检查求PASS。
本轮先不重跑完整模型，诊断包交S00执行；提交补充报告后由总协调审核。
```
