# S04 R2：R1 的28项数值失败归因

2026-11-05（Asia/Shanghai）。状态：LOCAL_ATTRIBUTION_COMPLETE / NUMERICAL_FAIL / NOT_ACCEPTED。

本轮新增了候选重写路径关闭量化的真实 fp32 对照和局部因果检查。**fp32 对照83项76 PASS/7 FAIL；原bf16路径逐项复现R1的55 PASS/28 FAIL。** 原夹具/权重/门槛没有改变，不将R1原模块与deepcopy的自我比较当作本轮对照。

已证实两处量化敏感边界：FFN1/ReLU的63个开关变化足以产生linear1/norm2的四项大范数梯度失败；QKV梯度转bf16破坏key-bias归约的精细抵消，导致最大的packed bias更新差。剩余更新差可由记录的梯度和原AdamW逐位重放，没有发现optimizer语义改变。**严格fp32整步对照仍有7项失败，不能宣称候选数值等价，也没有把诊断反事实提交为修复。**

## 范围与身份

- 仅新建本R2目录；根SESSION_STATUS.md/ROUND_DELTA.md按请求更新，R1原件另存在evidence/R1_*.md。R1源、数值协议、失败JSON、报告、旧ZIP及清单等30文件保持原SHA；旧包SHA仍为323fecc6f477465ab6f418e4ee4cb6eade91e4c852b2d3f27d1dd0f03fbeab84。
- 开始前逐项核R1包28成员及包原件；R2 baseline与tests/common.py为原字节副本。R2运行时再次逐项核输入和全部16个初始参数payload SHA，与R1 block_numeric.json完全一致。
- B2/M17/D512/8头/2048 FFN、原heads和pre mean loss、fresh AdamW lr1e-4/betas(0.9,0.999)/eps1e-8/decay0.01、每侧一次backward/step、Torch2线程不变。
- Windows已有Python3.11.9/Torch2.7.1+cpu独立环境只读使用；无安装、集群连接/job、KML实测、性能/峰值、完整模型、200步或S05启动。
- 候选最小改动仅增加显式torch_fp32_control诊断后端：同一BF16EncoderBlock.forward、自定义linear forward/backward、SDPA/QKV/残差/FFN结构，以fp32替换各bf16 cast。原torch_reference与kml模式仍用原bf16 dtype。
- R1_TO_R2_DIAGNOSTIC_MODE.patch共84行；不是优化修复。运行中局部hooks/linear与attention观察包装在finally恢复，不写生产或R1代码，不patch全局F.linear/SDPA。
- DIAGNOSTIC_PLAN.md和新模式检查先冻结SHA并保留“尚不支持诊断后端”的红灯；实现后10项合同/attention/诊断模式检查通过，数值检查另报，不以这10项代替83项控制。

## 1. 新增的候选fp32整步对照

用原fp32控制协议逐tensor检查：max_abs<=2e-5（moments<=2e-6），ref_norm>1e-8时还须rel<=2e-6；小范数只用max_abs。keys/shape/dtype/梯度/finite/step严格检查。门槛来源为S02 R7 VALIDATION_PLAN，未调整R1任何bf16门槛。

结果：输出、loss、输入梯度、16个参数梯度和全部moments均PASS；更新后参数15/16 PASS、增量10/16 PASS，合计76/83 PASS。
输出rel=4.6457e-8、max_abs=2.3842e-7；输入梯度rel=1.2091e-7，参数梯度最差rel=2.6011e-7。7个FAIL完整保存在evidence/fp32_control.json：

- in_proj_bias 的更新后参数及增量两项：rel=1.51275%，max_abs=8.83237e-6。
- in_proj_weight、out_proj.weight、linear1.weight、linear2.weight、head_coarse.weight五个增量：rel约6.69e-6至4.99e-5，超原2e-6；不是把绝对误差条件当唯一门槛。

**已记录的fp32前向边界中，首处分歧在linear1偏置epilogue。** 从block输入到norm2输出的观测值逐位一致；原F.linear的结果逐位等于torch.addmm，而候选的mm后add偏置相对误差5.4006e-8、最大绝对差2.3842e-7，ReLU开关变化0。这一固定输入对照见linear1_fp32_epilogue.json。不是漏掉norm/ReLU/残差，也不是改变损失；它是两个数学等价fp32求值次序的舍入差。
反向各梯度虽满足原门槛，fresh AdamW仍把很小的差异放大到严格更新门槛之外。256项参数/增量/moments逐位重放证明更新差来自实录梯度，而非不同optimizer或状态承接。不能据此把fp32整步标PASS，亦未证明所有7项都只由linear1 epilogue单独造成；完整反向浮点归约路径也不同。

## 2. bf16首处分歧与FFN/ReLU局部归因

evidence/intermediate_metrics.json记录每个边界激活/梯度的ref_norm、绝对/相对误差、RMS、零值及符号统计；evidence/intermediates.pt保留必要原张量/梯度。前向第一处差异是预定的入口bf16量化（rel=0.16516%），不是发现新的结构改写错误。

| 边界 | 前向rel | 反向rel |
|---|---:|---:|
| norm2 fp32输出 | 0.17201% | 4.8064% |
| linear1实际输入（候选bf16） | 0.23966% | 4.8064% |
| linear1输出 / ReLU输入 | 0.33949% | 4.6980% |
| ReLU输出 / linear2输入 | 0.33959% | 0.32573% |

按反向顺序，梯度误差从ReLU输出的0.32573%跳到其输入的4.6980%，再传播到norm2；这是首次明确的FFN反传放大边界。
69632个ReLU位置中63个开关变化（约0.0905%），27个正→非正、36个非正→正；跨越位置原preactivation绝对值最大0.00274217。每个位置的值和上游梯度见relu_gate_changes.json。

局部VJP固定参考的norm2输入/输出、W1、norm2权重和ReLU上游梯度，只把ReLU gate换成bf16路径的gate；参考和完整bf16局部反传均与实际四项梯度逐位一致（不是近似重构）。结果见local_vjp.json：

| 失败梯度 | 参考norm | 原bf16 rel | 只换gate的rel | 反传恢复参考gate后的rel |
|---|---:|---:|---:|---:|
| linear1.weight | 2.766409 | 4.68222% | 4.66280% | 0.41233% |
| linear1.bias | 0.127267 | 4.48891% | 4.47935% | 0.30106% |
| norm2.weight | 0.071512 | 4.63292% | 4.62719% | 0.46340% |
| norm2.bias | 0.071936 | 4.81494% | 4.76480% | 0.39686% |

这四个参考norm均明显高于1e-8，**不是小分母造成的相对误差假象**。固定上游梯度的实验直接证明仅gate变化就足以造成全部四个2%梯度FAIL；没有通过更换输入或降低阈值获得该结论。
另一次诊断反事实只在backward恢复参考gate，forward输出/loss与原bf16逐位不变，四项梯度和8项moments全部转PASS；28项FAIL降到14项，无新增失败。它不是量化ReLU的真实导数、不是候选修复，也不能称门槛通过。

## 3. 参数更新失败与QKV梯度归约

R1的28项分为4梯度、4 exp_avg、4 exp_avg_sq、4更新后参数、12更新增量。
恢复gate后剩14项全部是3更新后参数+11增量；这证明不能把全部28项都归为ReLU。每个参数的实际梯度符号变化、eps附近数量及增量误差在adamw_replay.json。

保留原初值并向原AdamW注入实录梯度，在reference/fp32_control/bf16/restored_gate四种诊断输入中，参数/增量/moments共256个张量全部逐位复现原结果，每个独立optimizer仍只step一次。由此证实本夹具上的更新差来自梯度扰动与fresh AdamW敏感性；不是optimizer超参/步数改变。

最大的70.084% packed in_proj_bias相对更新误差有独立定位：

- 原参考key-bias梯度范数5.89977e-9，bf16路径变为3.71472e-5。
- 在**同一次bf16执行**中，SDPA反传到fp32 QKV的key-bias归约范数为5.69341e-9；只转bf16再恢复float求和后为3.71472e-5。
- 该cast逐位复现存下的bf16 QKV梯度，求和逐位复现实际in_proj_bias.grad；最大分量从约1.00044e-9变为7.74860e-6，见key_bias_rounding.json。
- 对应key-bias更新范数：参考5.64938e-5、bf16 0.00221426。key方向的精细抵消在梯度量化前后发生变化，再经eps=1e-8的fresh AdamW放大。这与上述四个大范数FFN梯度的gate机制不同。

其他增量也对元素级符号变化敏感。例如bf16 head_coarse.weight整体梯度rel仅0.29707%，但有111/131072个梯度符号变化，增量rel为5.57782%；linear2.weight为0.40554%梯度差/1241个符号变化/6.82135%增量差。恢复ReLU gate不改变这两项，不能将它们归因于该gate反事实。
未逐一拆分每个剩余cast对14项更新失败的独立贡献，也未声称整个数学/科学等价性已经证明。

## 4. 结论与后续边界

已证实：原R1失败能原样复现；候选fp32重写的输出/梯度在原容差内，但严格整步更新不全过；FFN/ReLU gate变化主导四项大范数梯度超阈；QKV梯度量化造成key-bias抵消丢失；更新/状态差可由原AdamW加实录梯度完整复现。
没有发现漏算、错误loss/批量、缺失梯度或错误AdamW语义的证据。当前没有足够依据把合法舍入差异当作编码缺陷修掉；本轮只增加诊断开关，bf16路径未修、未集成。
敏感精度边界已交清：FFN1输入/权重/pre-ReLU及其反传gate，QKV梯度转bf16与bias归约。若下一轮评估新的fp32稳定岛，须另立最小候选并按原83项全测；入口量化仍可能改变gate，单独把ReLU计算转float不保证解决。不能直接交付“恢复参考mask”的诊断反事实。
本地严格fp32更新仍失败，bf16仍28FAIL；先由协调评审此归因与下一步有限候选范围，不自行扩大精度搜索、修改门槛、上C2、测性能或开S05。

## 复现和交付

在项目根目录运行现有Python（不安装环境）：

```powershell
& './c2/stage4_sessions/work/S02/round2_20261104T114949Z/.venv/Scripts/python.exe' -B -m unittest discover -s ./c2/stage4_sessions/work/S04/round2_local_attribution_20261105/tests -p 'test_*.py' -v
& './c2/stage4_sessions/work/S02/round2_20261104T114949Z/.venv/Scripts/python.exe' -B ./c2/stage4_sessions/work/S04/round2_local_attribution_20261105/tests/diagnose.py
python -B ./c2/stage4_sessions/work/S04/round2_local_attribution_20261105/verify_delivery.py
```

诊断脚本exit0仅代表夹具核对、对照/局部实验和记录成功完成；summary.json明确fp32 7FAIL、bf16 28FAIL，不是数值PASS。
SOURCE_MANIFEST.json、diff/R1_TO_R2_DIAGNOSTIC_MODE.patch、ARTIFACT_SHA256.txt与package/PACKAGE_MANIFEST.json提供来源/新包SHA；evidence/delivery_verification.json只核身份/保存证据关系，不替代模型验收。
R1旧ZIP及原根状态在旧包中保留；根短状态按本轮要求更新，因此不要用R1旧清单要求当前根短状态继续等于R1文本。
