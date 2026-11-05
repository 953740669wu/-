# S06 R2：线程观测与父进程清理修订

2026-11-05；LOCAL_ONLY / CLUSTER_NOT_RUN。此包只替代R1的诊断入口；没有新Torch、模型、精度、数值容差或性能搜索。命令是准备交接，不授权提交集群作业。

## 与R1的差别

- Linux入口统一OMP36/MKL36/OpenBLAS1/cores/close。
- 不调用torch.set_num_threads。读取实际get_num_threads，非整数36即失败；保存interop和parallel_info。
- before_framework、after_framework和before_exit均保存全部当时可见TID掩码。复用未修改CPU36_MODEL_V1的snapshot_threads/validate_snapshot，要求完整快照且每个掩码均在S00选中的36核内；失败证据仍保留，退出前检查可将原PASS变为FAIL。
- 36是实际Torch intra-op配置和所选物理核边界，不要求瞬时可见TID数量恰好36；close绑定下单TID只有一个核也可通过。快照不是连续监测或每核活跃度证明。外部终止/超时可能没有子段退出快照，不能将缺失视为通过。
- 父进程在TERM、SIGINT/KeyboardInterrupt、wait异常、超时及正常返回后都进入finally清理。Linux只向本次Popen(start_new_session=True)建立的组发送TERM/KILL；每次回收等待分别至多0.5/1秒，没有无界wait。即使leader已退出，仍向其组发KILL，防止编译后代残留。创建句柄期间的中断延后处理，不改变子进程继承的OS信号掩码；清理期间忽略重复中断，完成后恢复原处理器。
- Windows仅清理直接子进程，不能证明Linux组清理；REAPED只表示直接子进程回收成功且清理调用未报错，不宣称所有后代均已被wait回收。SIGKILL父进程/主机失效无法由Python finally保证清理。
- 标准库测试可任意搬移，不再依赖ROOT.parents[3]；可选S06_PROJECT_ROOT仅用于显式复核原项目来源，默认只核包内冻结源。

## S00校验与针对性检查（尚未运行Linux）

将S06_R2_PAYLOAD.zip传入新的S06独立目录并解压，以下从包内payload目录执行；不要覆盖R1或其它任务路径。

```bash
cd /home/share/dengqingtian/opt/stage4_sessions/S06/<新R2目录>/payload
sha256sum -c ARTIFACT_SHA256.txt
bash -n candidate/run_linux.sh
# 仅在下一次明确安排的独立资源内检查，不因本文件存在自行提交新job。
env -i PATH=/usr/bin:/bin /usr/bin/python3 -I -S -B \
  -m unittest discover -s tests -v
```

26项共7项旧检查、19项针对性新检查。本地Windows为23通过/3跳过；3项Linux检查分别验证子进程信号掩码、TERM和SIGINT下清除忽略TERM的本任务后代且保留无关session。后代Z/X只视为无活进程，不当作全部后代已被本父进程回收。失败时测试finally仍限定在本测试创建的PID/组清理；不触及其它作业。

上面标准库检查不导入Torch，也不验证实际C2线程。实际probe仍需S00现场选择并核对授权核、DDR节点、当前作业和环境身份后另按下方入口执行。旧资源建议仍为38分配/36实际核、8192MB DDR、exclusive、660秒时限；本轮没有新增排期或作业授权。

## 修订后的实际probe命令（C2未运行）

```bash
: "${CCS_JOB_ID:?requires an allocated compute job}"
: "${S06_CPUSET:?S00 must select 36 allocated CPUs after checking topology}"
: "${S06_MEMNODE:?S00 must select the matching DDR NUMA node}"
export S06_CPUSET S06_MEMNODE
# 可选S06_CXX只允许已核实的现有C++编译器；不安装或更换工具链。
timeout --signal=TERM --kill-after=10s 640s bash candidate/run_linux.sh
```

入口沿用包内baseline/cluster_runtime_reference.env所列S00旧venv、现有torch_kml、shim/KML/OMP，不改环境文件。Python -I/-S与显式原包路径、独立缓存、fp32、MKLDNN及原数值容差保持；probe每段120秒、合计600秒，父进程清理最多另加1.5秒等待。实际路径/版本/库SHA漂移即停止，不安装补包、放宽线程门禁或调用setter“修好”观测。原KML/autograd/compile六段范围不扩。

回传evidence/c2_<job>_<UTC>/完整结果及S00调度/核/DDR来源原件。每段新增execution.json保存退出/中断原因和cleanup回执；result.json保存thread_checkpoints及thread_errors。清理失败为CLEANUP_FAILED且非零退出。被终止段没有result.json时保留stdout/stderr/execution.json及summary，不将未测线程检查报PASS。

当前实际Torch36、C2可见TID边界、Linux组清理、compile/卷积数值与性能均未运行。不要把模拟对象的36或Windows直接子进程回收当成C2实测。
