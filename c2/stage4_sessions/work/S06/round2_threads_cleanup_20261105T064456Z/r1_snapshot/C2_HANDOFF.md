# S06 PREP_R1：交S00的Linux探针

日期：2026-11-05；LOCAL_ONLY / CLUSTER_NOT_RUN。此文件是准备命令，不是已获批的新作业。S06本轮没有连接集群、创建远程目录或提交job。先由总协调/S00安排独立有界资源，不能借用其它任务正在运行的allocation。

## 范围与停止条件

仅现有Torch/Python/NumPy/KML/OpenMP；不安装包、重编框架、修改权限、读取syssentry受限内容或启动完整模型。独立S06目录保存缓存与结果；原模型/kml_ops逐字节副本保留。

建议单节点单域：分配38核、实际36核、DDR 8192MB、exclusive、调度时限660秒；进程内总预算600秒，每阶段最多120秒，编译并发1。最大申请约0.1833节点小时，实际成本待S00调度证据，不按36/608折算。若资源、路径、权限、导入、数值或编译失败，当轮停止；不自动加内存、换编译器、放宽阈值或重试。显式NUMA绑定仅为有界探针，不是训练性能基线。

## 准备与身份核验（无计算）

将整个S06目录原样传到当前账号独立路径，例如`/home/share/dengqingtian/opt/stage4_sessions/S06/PREP_R1_<唯一时间>/S06`。下面在该目录执行；文件中的历史账号/路径必须由S00重新核实，不把2026-11-04记录当实时状态。

```bash
cd /home/share/dengqingtian/opt/stage4_sessions/S06/PREP_R1_<唯一时间>/S06
sha256sum -c ARTIFACT_SHA256.txt
bash -n candidate/run_linux.sh
test -r baseline/cluster_runtime_reference.env
```

运行环境参考源为S00已实测venv，不创建新venv。`-I -S`不处理site/.pth；启动器用参数显式注入共享torch根和原venv的两个site-packages目录，保留同一解释器和依赖。不能只用`-I`然后期待PYTHONPATH仍有效，也不能把`-s`当成移除系统site-packages。

若包校验失败或依赖路径缺失先停。缺少sympy/typing_extensions等编译依赖时，保留精确ModuleNotFoundError和sys.path；不要添加整个系统site-packages绕过隔离，不安装依赖，不修改site或importlib.metadata。探针按`baseline/environment_expected.json`核对S00历史模块版本/路径及torch_cpu、shim、KML、OMP四库SHA；漂移即停，交总协调决定，不能继续声称旧环境。

## 已分配计算节点内的执行命令

S00先取得djob原始资源记录、CPU/DDR NUMA拓扑，在分配核集合中选择一个域的36核。`S06_CPUSET`、`S06_MEMNODE`必须填写现场值，下面`${变量:?}`在未填写时直接失败，避免静默使用整机资源。

```bash
# S00在当前shell设置S06_CPUSET、S06_MEMNODE；CCS_JOB_ID由作业环境提供。
: "${CCS_JOB_ID:?not an allocated job}"
: "${S06_CPUSET:?set 36 allocated CPUs after checking topology}"
: "${S06_MEMNODE:?set the matching DDR NUMA node}"
export S06_CPUSET S06_MEMNODE
# 默认只读/usr/bin/g++；若已核实历史sw/gxx路径，可显式export S06_CXX=/已核实路径/g++。
timeout --signal=TERM --kill-after=10s 640s bash candidate/run_linux.sh
```

入口复用S00历史路径：`/home/share/dengqingtian/opt/stage4_sessions/S00/ENV_20261104T130730Z_R4/venv/bin/python3`；Torch=`/home/share/songzhenlong/eitfm/sw/torch_kml`，shim为同一S00环境内`S01_payload/lib/libkml_sgemm_shim.so`，KML=`/opt/HPCKit/kml-lib/sme/kblas/multi/libkblas.so`。共享树只读；不预加载整个kblas（历史曾在import torch时挂起）。脚本不传HBM预加载。

顺序为imports → pointwise → conv → block → kml-explain → kml。每段新进程，共用本轮专用编译缓存；首次/后两次时间分别保留，均为微型诊断，不算编译摊销或训练收益。block只实例化原始`Block(128,128,512)`，空间8×8/B1，不实例化UNet/Encoder、不读demo。kml使用128×512输入，避开`numel < 2**16`的原始fallback；没有KML库即失败。

`kml-explain`记录Dynamo forward graph数量、break数量/原因，不证明反向可编译；随后`kml`用Inductor/fullgraph=True检查真实执行限制。失败不设置suppress_errors、不自动fullgraph=False、不注册新custom op；保留data_ptr/ctypes/autograd原始错误。graph break条数为0也不保证KML完整被捕获。

数值预设：CPU fp32，rtol=atol=1e-6逐元素assert_close；额外记录max_abs和relative_l2（分母max(||ref||2,1e-12)），检查输出及所有应有输入/参数梯度、shape/dtype/finite。Block未使用的h不求梯度并明确标记。未做optimizer、完整模型loss/更新、四域/整节点或科学训练验证；S02等原阈值不变。

## 回传与解释

回传新`evidence/c2_<job>_<UTC>/`完整目录，连同作业stdout/stderr、djob/节点/资源/开始结束/退出记录、NUMA选择依据和包SHA。需保留所有失败、TIMEOUT及未运行段，不能只回PASS段。

- `summary.json`：逐段退出/命令/耗时、总状态和not_run；TIMEOUT时可能没有该段result.json，但stdout/stderr仍在。
- 每段`result.json`：Python/flags/sys.path、源码SHA、Torch/NumPy/Inductor/Dynamo文件与版本、torch构建配置、CXX路径/版本/SHA、OMP/KML/shim实际映射SHA、异常阶段和traceback。
- `.cache`内容实际为新结果目录下`cache/`；进程级临时目录、Inductor/Triton/XDG缓存也都指向这里。无需回传缓存体积很大的部分即可审核原始日志；不要把缓存计时当成冷启动新轮。

imports通过仅说明隔离导入可用；pointwise通过才补到现有工具链实际代码生成；conv/block通过仍不是完整解码器通过。若出现新权限错误，只保存异常及所属显式路径，不读取拒绝访问的包内容、不申请系统权限变更。本轮没有S00执行结果，当前不存在C2 PASS、graph break实测数或速度结论。
