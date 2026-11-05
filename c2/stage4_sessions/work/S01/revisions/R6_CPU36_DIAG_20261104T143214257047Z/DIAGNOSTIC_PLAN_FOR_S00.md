# 给S00：只执行小型CPU36线程诊断，不重跑完整模型

版本：`S01_CPU36_THREAD_DIAG_V1`。状态：准备交接，**本地11项合同检查通过，Linux/C2诊断未运行**。依据CPU36_POLICY与AFFINITY_REVIEW；历史job2026450的38核失败证据保留不改。

## 固定范围、资源与停止条件

- 新的单计算节点作业，申请单NUMA域38CPU，继承原24576MB上限；诊断建议最长300秒（不超原900秒），不占用既有作业。它是待S00安排的诊断范围，本窗口没有提交。
- 在框架导入前取授权集合和现场拓扑，显式选择该38核域前36个物理核心，留末2核；如果只分到36，必须恰好为同域前36。授权不足、跨域、SMT重复或无法留出末2核就停止。
- 所有worker以numactl --physcpubind=<36核> --membind=<该域>执行。观察器也缩至该36核集合；不扩大任何CPU掩码。
- 没有EIT模型、NPZ、optimizer、HBM、attention大矩阵或性能搜索。仅小型torch逐元素、512² NumPy dot、1024²实际KML GEMM，每阶段重复约0.5秒用于可见采样，不计算吞吐。
- 五个worker串行，各45秒deadline。任一启动/库/算子失败或发现TID越界即停止后续case；TERM后1秒KILL仅作用于本次创建的session。不自动重试，不启动完整模型。

## 五个有限对照

所有case绑定同一选中36核，OMP_NUM_THREADS=36、OMP_PLACES=cores；不调用torch.set_num_threads，不改变已加载runtime设置。各case均是新进程，避免线程池缓存掩盖环境变化。

| case | MKL_NUM_THREADS | OPENBLAS_NUM_THREADS | OMP_PROC_BIND | 目的 |
|---|---|---|---|---|
| A_mkl1_negative | 1 | 1 | close | 明确单线程负控：历史变量组合移到36核集合；不是正式36线程配置，也不改写历史38核结果 |
| B_mkl_unset | unset | 1 | close | 相对A只移除MKL=1，观察Torch及KML实际线程 |
| C_mkl36 | 36 | 1 | close | 相对A只把MKL改36；与B比较显式设置/默认策略 |
| D_bind_false | 36 | 1 | false | 相对C只改绑定；隔离调用线程掩码与全部TID区别 |
| E_openblas36 | 36 | 36 | close | 相对C只改OpenBLAS，识别其独立线程池影响 |

A以及B/C/D中的串行NumPy阶段是显式诊断负控，不当作正式36线程算子配置。E仅是候选环境对照，不自动选为生产设置。S02原4核正式测试已经改36，但本次不运行S02检查。

## 采集内容及解释边界

每个worker在before_import、after_torch_import、Torch算子后、NumPy后、KML首次调用后与重复KML后保存全部TID的掩码/状态/start_ticks/CPU tick/last_cpu。父观察器每约20ms从/proc/<pid>/task读取全部TID并按phase累积CPU tick推进；所有样本原样保留于samples.jsonl。

保存真实torch intra/inter-op、parallel_info、完整相关OMP/MKL/OPENBLAS/KMP/GOMP变量，已加载OpenMP/BLAS/KML/shim路径和SHA，并只通过RTLD_NOLOAD查询已加载库API，不为探针引入第二套OpenMP运行时。记录omp_max、dynamic、proc_bind、places、OpenBLAS线程API；没有真实KML加载则失败，不用torch.mm替代。

不同TID可分别被绑单核，不能要求它们都等于整个36核集合。总TID数也不等于正在计算的线程数。CPU tick推进和omp_max只作观察，不能单独证明精确in-region team人数；采样不足必须如实记录，不可推断36线程已验收。DIAGNOSTIC_DATA_COMPLETE只表示5组数据收齐，不代表生产/模型/性能接受。

## 执行入口（交S00排期后运行）

完整原样解包本轮诊断ZIP到当前账号自有、全新且较短的目录。包内cluster_runtime.env为本次S00环境设置的冻结副本，仅作为基线；driver会在每个新worker覆盖本case的OMP/MKL/OPENBLAS配置。

```bash
# 必须在新的Donau计算job内；CCS_JOB_ID由调度器注入
bash /<S00自有全新诊断目录>/diagnostic/run_thread_diagnostics.sh
```

提交前检查解包后的每个文件SHA、全部.sh/.env无CR及真正Linux bash -n；再核对C2_PYTHON、torch/numpy/kml_ops来源。不可在login节点运行算子。建议用外层timeout --signal=TERM --kill-after=5s 270s包住上述命令，job时限300秒，仍按S00实际授权安排，不由本文件自动提交。

请回传job分配/终态、日志、完整results_<UTC>目录、cpu_receipt、五个command/worker/samples/assessment、SUMMARY与COLLECTION。COLLECTION有SHA/bytes/原始mtime_ns；不要重写mtime，不截掉失败case。原NPZ不需要也不应上传/下载。

S01收到后先判断A/B/C是否只因MKL变化改变真实intra-op/KML行为，再用D解释绑定，用E判定OpenBLAS是否需要单独修复。结合全部TID边界和runtime身份提出最小环境/合同修订，交总协调审核后再考虑模型恢复。当前旧模型包继续停止。
