# CPU36线程问题：最小修复候选与保留的门槛

状态：**DRAFT_AFTER_SMALL_DIAGNOSTIC；不是模型恢复许可**。接受R2保持不变。本轮提供可测试的CPU合同原型，不替换现有runner。

## 已有证据与两个独立问题

job2026450的首轮子进程exit0，完整模型确已执行，但原汇总FAIL、job exit1且只完成1/3轮。原MKL_NUM_THREADS=1、worker OMP_NUM_THREADS=38、torch实际intra-op描述1；全线程掩码未采集，因此还没有唯一因果证据。

PyTorch v2.7.1的 `intraop_default_num_threads` 先读OMP，再以MKL覆盖该默认值；该读取不以实际链接Intel MKL为前提。它与本机aarch64上的症状一致，但实际二进制仍须用小算子A/B对照核实，不能只凭文档定案。[PyTorch v2.7.1源码](https://raw.githubusercontent.com/pytorch/pytorch/v2.7.1/aten/src/ATen/ParallelCommon.cpp)

Linux affinity是每线程属性；pid=0读调用线程。OpenMP启用绑定时可将初始线程绑定到第一个place。因此不能用主线程单核掩码等于完整核心集合作为所有线程的唯一判据，也不能由全TID掩码并集覆盖36核就断言计算使用36线程。[Linux手册](https://man7.org/linux/man-pages/man2/sched_setaffinity.2.html)、[OpenMP规范](https://www.openmp.org/spec-html/5.1/openmpse61.html)

## 最小环境修复候选

先由S00运行诊断中的B/C/E。若B或C解除intra-op=1且线程边界无越界，优先选择单一、可解释的环境改动：正式worker显式OMP_NUM_THREADS=36，并把MKL_NUM_THREADS从1改为36（或经B验证后选择unset，两者不得混作同一配置）。不能在torch导入之后才改环境，也不先用torch.set_num_threads掩盖本次优先级诊断。

OPENBLAS_NUM_THREADS独立处理：C固定为1、E改36，通过NumPy/Torch/KML阶段实际库API与线程采样决定。1可作为显式串行辅助负控，不能静默沿用并把所有实际后端都记为36；若正式算子走OpenBLAS且需要36线程，应选择经E验证的36设置。不要仅改日志、不核验实际API。

保留OMP_PLACES=cores、OMP_PROC_BIND=close。D的false只隔离绑定效应，不作为删检查的捷径。OMP_THREAD_LIMIT、KMP/GOMP等继承覆盖项一律记录；发现冲突就停止评审，不能静默清掉管理方约束。

## 36核选择与边界合同

1. 在框架导入前记录调度授权CPU集合、同域完整38核心拓扑及physical sibling映射。只接受完整38核或恰好该域前36核的授权；不足、跨域、SMT重复、误占末2核都拒绝。不调用任何扩大CPU权限的setaffinity。
2. 从现场域列表排除末2个物理核心，选中36核；allocated、selected、reserved三组分别记账。numactl使用明确的--physcpubind=<选中36核>，不能用整域--cpunodebind取代。
3. 模型/算子worker的OMP目标为36；正式候选需记录真实torch.get_num_threads()并要求36，interop值单独记录，不自动改成36。环境字符串不是实际线程数。
4. 将发布时的主线程affinity作为一个TID观察值保留；另记录全部TID掩码与完整性，每个非空掩码必须是selected36的子集。调用线程被绑到单核可通过边界检查，但任何TID越界、空/缺失采样或torch线程数错误仍拒绝。
5. 不要求进程总TID数恰好36，空闲BLAS池/辅助线程会增加总数；也不以掩码并集作为线程目标通过。保留分阶段CPU tick推进、runtime omp_max/BLAS API与采样覆盖。采样不足或无法确认计算team时标INCONCLUSIVE，不宣称模型36线程验收。

本轮 `diagnostic/cpu36_contract.py` 与11项正负检查证明上述“核心选择、所有TID边界、真实torch数”合同原型：单核TID可合法，越界/预留核/不足/跨域/SMT重复/缺证据/torch=1均拒绝；没有删除绑定检查。它尚未接入R2发布/汇总，也没有在C2运行。

## 接收与归档

S00此次完整19文件已逐字核对，原远端summary的实际失败仍为affinity mismatch。received文件mtime是本地解包时间，不能直接重跑R2汇总并把本地stale/future mtime错误当作远端根因。当前归档缺原始mtime_ns，不伪造恢复；新诊断COLLECTION记录稳定文件的SHA、bytes和原始mtime_ns，后续模型collector也应按此补齐。

诊断后若形成runner修订，只改核心选择、worker环境、线程元数据与验收合同，保持模型计算/损失/批量/精度/optimizer/数据不变，并新建版本/SHA。S00随后同步S01/S02包装器、同PID守卫、LF/提交门槛和新清单，再交总协调评审，不能直接重投旧38/4核包。
