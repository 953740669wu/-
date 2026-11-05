# S02 第三轮：严格数值失败原因隔离与 C2/KML 入口

日期：2026-11-04（Asia/Shanghai）。

状态：**READY_FOR_REVIEW — WINDOWS_CAUSE_ISOLATED / ORIGINAL_STRICT_FAIL / C2_KML_NOT_RUN / MEMORY_NOT_RUN**。

## 1. 结论

保持原阈值、模型、样本、有效B64、loss分母、eps和LR，完成同一16-pre配置的9项受控诊断。第二轮194项失败逐项、逐值复现，未改成PASS。主要近因已有直接证据：

1. **loss标量差是分块求和的fp32舍入。** 只拆loss、仍做整批前反向时，仅loss相差1个fp32 ULP=3.0517578125e-5，梯度/更新/state逐位一致；同输出的公共float64分数完全一致。该差仍超过原2e-5，不能忽略或放宽。
2. **参数梯度差来自改变batch后局部参数归约的fp32结果。** 固定参考loss上游梯度后，微批仍复现全部194项失败。两处代表投影的逐元素输入与上游梯度完全一致，但相同局部点积/和的fp32参数梯度不同；相同元素用float64归约则给出一致结果。不是本次forward值或loss上游梯度差异导致。
3. **fresh AdamW放大近零残差。** 最坏权重坐标g_ref=1.05228537e-9、g_candidate=-3.72529030e-9，分别产生约-9.54047e-6与+2.71238e-5的更新，差3.66643e-5。固定相同参数梯度重放AdamW时逐位一致，因此没有证据指向optimizer状态错位/多step；近零梯度相对eps=1e-8不可忽略。

12个失败的packed attention bias更新均集中在K段，Q/V段更新差上界仅2.1827873e-11；公共key bias的softmax平移不变性解释了其理论冗余和近零梯度。本轮没有删参数/归零梯度或修改optimizer来获得PASS。

已提供显式native/kml后端、固定跨平台case、原严格判据和四核/库身份验证的诊断入口。实际C2/KML由S00按限定排期运行，不能把Windows结论直接升级为C2结论。**未执行内存测试，M2严格门槛仍未通过。**

## 2. 前置条件与范围

先读最新STATUS和PILOT_REVIEW_20261104，原任务卡/容差沿首轮接受版本，读取S00的COMPUTE_ENVIRONMENT_REPORT、cluster_runtime.env及现有S02包装器。注意S01启动交接、4CPU/24GiB/900秒与显式原CPU绑定前提；本窗口不使用已结束job2026223、不接管SSH/排期。

开始核对S02首轮60项、第二轮69项索引；原始与复制计算源SHA见evidence/start.json。只写本轮独立目录：`E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S02\round3_20261104T134939Z`。首轮根报告、round2报告/证据、共享模型、阶段二/三、冻结corpus、旧demo、manifest及其它任务未改。

baseline/s4_models.py、baseline/kml_ops.py、candidate/training_step.py、candidate/paired_inputs.py、tests/check_equivalence.py、paired_fixture.py及VALIDATION_PLAN仍逐字节复制。新增diagnose_update.py调用原model_definitions/compare/expected_gradient，不重写模型或阈值。projection_trace只观察两个原F.linear；KML模式观察函数继续调用原KML函数。

已完成8项控制的入口版本、补记录NumPy元数据前的辅助代码分别保存在history/before_projection_trace和history/before_runtime_metadata，并记录哈希；每个结果自身记录实际源SHA。后续变化仅新增可选投影trace和后端身份检查，不改原计算源/门槛。所有新增代码diff见candidate目录，全产物SHA见ARTIFACT_SHA256。

无生产部署、上传、SSH、集群作业或Git提交。没有修改S00既有包/清单，新代码ZIP与独立固定文件供S00审查，不沿用旧包哈希或传输授权。

## 3. 环境、输入、复现与成本

本地DESKTOP-54BJCD6，Windows AMD64；沿用round2隔离Python3.11.9、torch2.7.1+cpu/NumPy2.2.6、MKL/oneDNN，torch线程4，interop8，无KML/HBM/NUMA绑定。实际版本/来源/构建信息按每个result.runtime记录。元数据补充和身份断言不代表C2已验证。

固定16_adjacent/pre、M208，完整12×512/8编码器及原U-Net、64×64，fp32、seed0、有效batch64、候选micro32×2、CKPT0、fresh。AdamW lr1e-4、betas0.9/0.999、eps1e-8、weight_decay0.01。配对合成协议S02_PAIRED_BELT_V1，不是真实NPZ，不决定正式训练scale/split。无DDP或有效全局batch。

导出的case/fixed_16_pre.pt包含完整初始模型state和全部固定张量，271,979,513字节，SHA256=`4de1fb40eb1c4b43a8747586399f336bf9e37184592d66fdbf711abad8469846`。初始权重和v/y0/idx/mask/t/noise SHA与round2完全一致。CASE_MANIFEST留存身份；C2读取同一文件，不因NumPy1.26.4/2.2.6或跨平台初始化重新生成输入。

本地受保护运行命令示例（已运行；strict预期退出1）：

```powershell
Set-Location 'E:\eitfm_c2_stages2-4_2026-11-03'
& 'c2\stage4_sessions\work\S02\round2_20261104T114949Z\.venv\Scripts\python.exe' -B 'c2\stage4_sessions\work\S02\round3_20261104T134939Z\run_local.py' --mode strict
```

各项run.json/stdout记录命令、起止与退出；9项本地完整模型控制在约21:55–22:04完成。外层elapsed包括对照快照/比较，仅用于成本与时限，不是训练耗时/吞吐。新增集群节点小时0、GPU小时0、作业0，本轮未再安装依赖。C2资源保护和停止条件见C2_HANDOFF，未获运行结果。

## 4. 正确性与因果证据

原门槛不变：输出/loss/输入及参数梯度/更新参数与增量max_abs≤2e-5且L2 relative≤2e-6；AdamW moments绝对/相对≤2e-6。norm<=1e-8只判绝对差，分母下限1e-12。step/keys/shape/dtype/梯度集合精确检查。控制模式通过不替代原微批strict通过。

| 受控模式 | 唯一主要变化 | 原判据失败数 | 结论 |
|---|---|---:|---|
| reference_repeat | 原mean整批对自身重复 | 0 | 所有快照逐位一致 |
| candidate_repeat | 原B32累积候选对自身重复 | 0 | 所有快照逐位一致 |
| strict | 原B64 mean对B32×2 | 194 | 逐项metric与round2完全相同 |
| full_sum | 仍B64×1，仅mean改sum/整批分母 | 0 | 所有数值差0，不是单独sum公式错误 |
| split_full | 一次B64前向，loss分两块，反向一次 | 1 | 只有loss失败，参数梯度/更新/state差0 |
| pinned_full | B64，固定参考预测/目标上游梯度重放 | 0 | 所有数值差0，VJP重放控制有效 |
| pinned_micro | B32×2，但上游梯度固定为参考值 | 194 | 逐项metric与strict完全相同，排除loss上游差异 |
| optimizer_same_gradient | 同初值，同参考参数梯度，仅重放AdamW | 0 | 梯度/更新/state差0 |
| reduction_trace | 原strict加两处无修改观察 | 194 | 原metric不变，局部归约证据如下 |

strict与pinned_micro的h/voltage/coarse输出及其上游梯度都逐位一致，v/y0输入梯度逐位一致；这不能覆盖参数梯度49项、更新参数13项、增量33项、moments98项及loss1项失败。

两处代表投影的输入和dL/dprojection均逐位相同：

| 参数/坐标 | 相同元素float64归约值（两路相同） | 实际参考fp32梯度 | 实际候选fp32梯度 |
|---|---:|---:|---:|
| layer1 in_proj_bias[576]（K段） | 4.65532129e-9 | 2.79396772e-9 | 5.82076609e-10 |
| layer10 in_proj_weight[1379,79] | 1.27444795e-9 | 1.05228537e-9 | -3.72529030e-9 |

这里float64只是对**同一fp32局部输入/上游梯度**的脱图点积/求和，并非全模型float64真值，也没有替换训练梯度。它将两个代表失败坐标的差异定位到参数归约；未逐算子证明所有49个梯度失败的完整误差传播。

fresh AdamW首步实数公式为`Δp=-lr*wd*p-lr*g/(abs(g)+eps)`。最坏权重位置参考实测Δ=-9.54046845e-6、候选Δ=2.71238387e-5；按相同g与p的float64标量公式分别约-9.53998179e-6/+2.71227896e-5，余差为参数存储/算子舍入量级。与同梯度重放完全一致的控制结合，支持“归约残差被AdamW放大”的近因，不支持optimizer次数/状态协议错误。

K bias公共平移不变性：`Q(K+b)^T=QK^T+(Qb)1^T`，每个query行增加相同常数，softmax不变；理论K-bias梯度为零。fp32反向与归约会残留微小值，fresh AdamW对其敏感。12层实际K段更新差最大约1.63e-5，而Q/V更新差≤2.18e-11。本轮不据理论不变性删掉K bias、归零其梯度、改变eps或放宽阈值。

9项单元检查通过：4项真实torch数学/负控、5项CPU额度/库身份逻辑；后者的系统接口替身不是实际Linux验证。Windows下显式请求kml退出2，不产生native回退PASS。Git Bash bash-n通过，Python按3.9语法检查；实际C2路径/ABI/绑核/调用仍待S00。

## 5. 性能与内存

**内存测试未运行。** 未建性能接受结论、未测训练峰值/DDR-HBM驻留、未扩大16-dec/32/CKPT/seeded或48矩阵。run_local的整机剩余资源门禁仅保护本机，不属于内存优化实验；trace与快照程序额外驻留不能用作训练峰值。

没有吞吐/整步加速、三有效轮、第二主机、四域/整节点或DDP结果；局部float64和控制模式不作为性能候选。M2数值门槛仍FAIL，因此S03实际工作集/热度仍未解锁。

## 6. C2交接、接受范围与下一步

诊断入口为diagnose_update.py，显式`--backend native|kml`。实际KML模式要求Linux、明确4个获分配CPU、fp32、真正的KML/OMP/shim映射及SHA、观测到direct KML GEMM，运行后核对CPU与库身份。使用原baseline/kml_ops，不固定kml=False，不静默fallback。

run_c2_diagnostic.sh在S00实际job/env下保存继承4CPU集合，使用exact --physcpubind加单域membind；Python再验主线程集合相等、工作线程不越界、torch线程4。源码/case校验、唯一输出、780秒timeout/15秒kill-after均明确。Linux真实执行仍待S00，不能把逻辑单测叫作4核实际验收。

已提供待审查的代码ZIP和独立约259MiB固定case，详见C2_HANDOFF及package/PACKAGE_MANIFEST。S00在限定一组排期中可选择strict或带相同严格比较的reduction_trace，不自动追加其它控制。旧S00包/哈希/上传范围不自动涵盖新载荷；本窗口未上传或修改其文件。

本轮完成失败原因隔离与可实际选KML的入口，**没有修复或接受原微批数值**。Windows失败保留，C2结果独立记账；待S00实际对照后判断是否同一归约敏感性。若后续需要计算修复，须保持当前门槛和训练定义另立候选；不得用控制通过冒充微批通过。内存阶段继续NOT_READY。

## 7. 证据索引

绝对根：`E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S02\round3_20261104T134939Z`。

| 产物 | 绝对路径 |
|---|---|
| 报告 | `E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S02\round3_20261104T134939Z\REPORT.md` |
| 交S00的具体说明 | 同根C2_HANDOFF.md |
| 实际后端诊断入口 | 同根diagnose_update.py、diagnostic_common.py、projection_trace.py、run_c2_diagnostic.sh |
| 九项完整模型因果结果 | 同根evidence/native_<mode>_<UTC>/result.json、run.json、stdout_stderr.txt |
| 已核验因果汇总 | 同根evidence/causal_summary.json |
| 小检查/CPU库检查 | 同根evidence/all_unit_tests.txt、controls_before.txt、controls_after.txt、affinity_tests.txt |
| 错后端拒绝与包校验 | 同根evidence/kml_wrong_platform_rejected.json、package_validation.json |
| 固定权重/输入 | 同根case/fixed_16_pre.pt、CASE_MANIFEST.json、evidence/case_export.json |
| S00新代码载荷 | 同根package/S02_DIAGNOSTIC_R3_CODE.zip、PACKAGE_MANIFEST.json |
| 源与交付物SHA | 同根SOURCE_SHA256.json、ARTIFACT_SHA256.txt |
| 不变与语法终检 | 同根evidence/delivery_validation.json |

所有初值/输入/源身份随结果记录；未向外部聊天发消息，未更改协调状态。报告与载荷交用户/总协调/S00复核。
