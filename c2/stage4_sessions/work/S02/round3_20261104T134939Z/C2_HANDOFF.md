# S02 R3：交给 S00 的限定 C2/KML 诊断入口

日期：2026-11-04。**仅本地准备，S02没有上传、连接集群、修改S00包或提交作业。** 仍按PILOT_REVIEW：S01启动交接通过、S00落实新作业的4CPU/24GiB/最多900秒及同域分配后，才执行原定的一组16-pre数值对照；HBM0，CKPT0、fresh、有效B64、microbatch32、fp32。没有内存测试或自动扩展矩阵。

## 新载荷

本轮文件位于`E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S02\round3_20261104T134939Z`：

- `package/S02_DIAGNOSTIC_R3_CODE.zip`：代码/协议/源哈希，包含可移植入口diagnose_update.py和run_c2_diagnostic.sh；不含venv或Windows专用run_local.py。
- `case/fixed_16_pre.pt`：271,979,513字节（约259.38MiB），SHA256=`4de1fb40eb1c4b43a8747586399f336bf9e37184592d66fdbf711abad8469846`。**独立文件，不在代码ZIP内。** 初始enc+dec权重及v/y0/idx/mask/t/noise等固定张量与第二轮Windows记录SHA完全一致。没有真实病例/冻结corpus数据。
- `CASE_MANIFEST.json`：固定文件SHA/大小和逐张量/初值身份；`SOURCE_SHA256.json`：执行源码和协议的逐文件SHA；`package/PACKAGE_MANIFEST.json`：ZIP本身和条目哈希。

这是新的可审查载荷，不能沿用S00旧14条目包的SHA/清单，也不能默认为旧包上传授权已经覆盖这个约259MiB文件。由S00核对本轮载荷和自己的授权/传输安排；本窗口不代上传。

冻结张量是为避免Windows NumPy2.2.6与C2 NumPy1.26.4、跨架构初始化差异混入后端对照。C2用`torch.load(...,weights_only=True,map_location='cpu')`读取，不重新生成输入或权重；原始dtype/shape保持，所有比较仍用原容差。case内含两个模型的完整state，不缩小模型或有效批量。该case只支持本轮16_adjacent/pre诊断，不是正式训练集/归一化/split决定。

## S00落盘布局与入口

在当前账号自有新目录解压代码；将独立固定文件放为`<payload>/case/fixed_16_pre.pt`。先核对PACKAGE_MANIFEST/CASE_MANIFEST及实际作业分配，保存自己的调度与库预检证据。不得覆盖共享源码、旧demo、S00旧包或已运行脚本。

在S00已核实的实际计算节点job内，先source其`cluster_runtime.env`，保留原KML/shim/OMP路径。再调用：

```bash
# C2_PYTHON、KML_BLAS_LIB、LD_PRELOAD、LD_LIBRARY_PATH由S00已核实环境提供。
# CCS_JOB_ID必须来自这一次真实Donau分配，不复用已结束的job2026223。
bash <owned_payload>/run_c2_diagnostic.sh strict
```

若本次限定对照需要同时保留两处代表投影的局部归约证据，可在同一明确排期中**选择**以下入口替代上条，不自动追加第二个完整配置：

```bash
bash <owned_payload>/run_c2_diagnostic.sh reduction_trace
```

`reduction_trace`和`strict`执行同一B64参考与B32×2候选；trace仅观察第1/10层投影的输入和上游梯度，并按固定坐标计算脱离训练图的float64点积/和。它不替换训练梯度、不改变optimizer或阈值。所有原严格比较完整输出；控制模式即使通过，也不替代正式接受。

不要调用旧`diagnose_same_config.py`：它固定kml=False。本入口`--backend kml`必须实际载入baseline/kml_ops及KML，观察到direct GEMM调用，并验证实际libkblas、BiSheng libomp、shim映射及SHA；不具备条件即退出2，不能回退native后打印actual_KML。

## 四核/后端约束

包装器在进入模型前读取继承affinity，要求恰好4个获分配CPU并属于同一NUMA域，保存其确切集合；仅用`numactl --physcpubind=<原集合> --membind=<该域>`，没有`--cpunodebind`。已有外层S02_CPUSET时还需完全一致。

Python进程内再次验证主线程affinity与原集合相等、所有可见线程affinity不超出该集合；torch线程固定4，记录interop、Torch/NumPy实际来源/版本、torch构建信息、选定环境变量、KML/OMP/shim映射与SHA及direct GEMM调用数/形状。结束时重验affinity及已见运行库身份。不能用608个host CPU或38个域CPU当作4核额度。

启动前核对源码和固定case SHA，拒绝现有结果目录/文件。输出为`<payload>/evidence/c2_<CCS_JOB_ID>_<mode>/`；内部780秒timeout，15秒kill-after，在900秒job限额内保留收尾空间。S00仍须验证Donau实际24GiB和无干扰等前提，本入口不凭节点总内存推断作业额度。

## 结果判读与回传

- 退出0：指定模式原比较均通过；strict标PASS_STRICT_SYNTHETIC_ONLY，其它标PASS_CONTROL_ONLY。范围仍是此合成case，不是全矩阵/真实数据/内存接受。
- 退出1：FAIL_ORIGINAL_CRITERIA，原阈值失败；保留所有metrics/failures，停止扩大。不能据Windows FAIL预设C2也FAIL，也不能抹去Windows证据。
- 退出2：后端/输入/身份/affinity等运行前提错误，不属于数值结论。
- 退出124/137等：timeout/终止，保留实际退出状态；不能标PASS。

回传result.json、stdout_stderr.txt、checker_exit_code.txt，以及S00保存的actual allocation/环境/源码/库/case清单。result包含初值及固定张量SHA、源哈希、后端及CPU身份、完整原判据metrics、投影block/最坏更新坐标和可选局部归约trace。

其它诊断模式仅供本地因果隔离/后续另行限定的同配置检查：reference_repeat、candidate_repeat、full_sum、split_full、pinned_full、pinned_micro、optimizer_same_gradient。不要在C2自动循环这些模式，当前用户/S00准备的是限定对照。

## 本地已验证及限制

Windows完整模型9项因果控制完成；当前严格194项失败重现。9项单元检查通过（4项真实torch诊断数学/负控、5项CPU/库身份逻辑），KML在Windows被明确拒绝；shell经Git Bash `bash -n`通过、可移植Python语法按3.9检查。CPU逻辑单测中的系统接口替身不是实际Linux绑核证据；实际C2/KML加载、调用、调度、库ABI与结果均等待S00，不在本报告冒充已运行。

没有性能/内存测量入口，没有用保留快照脚本的RSS推断工作集。本轮不改变eps/LR/参数/样本/阈值，也不应用float64训练或去掉key bias。M2严格门槛仍未通过。
