# S02：电极目标配对、更新等价性与内存优化准备

日期：2026-11-04（Asia/Shanghai）。

状态：**READY_FOR_REVIEW — LOCAL_ONLY / PAIRED_INPUT_PREPARATION / MODEL_NUMERICAL_NOT_RUN / CLUSTER_NOT_RUN**。

## 1. 结论

已按最新开场说明补齐电压、目标和帧身份协议`S02_PAIRED_BELT_V1`，实现独立只读配对loader，将完整模型等价检查接到同一套配对合成输入。**10项真实NumPy配对检查+4项既有代数/源码检查通过**；本机四个已知解释器均无torch，完整模型输出/梯度/AdamW/CKPT比较仍未运行。没有新内存峰值、耗时或加速结果，未证明工作集进入4GB。

建议接受本地准备供总协调评审，暂不集成到正式入口。真实NPZ尚未适配/验收；合成数组通过不能替代真实输入、训练步数值、C2性能或训练效果验收。

核心语义保持：pre的masked项以整批mask总数为分母、coarse项以B×256为分母，dec以B×4096为分母；固定整批mask/t/noise/idx，一次清梯度、逐微批backward、最后一次AdamW.step。B64×1/B32×2/B16×4仅为比较配置，未决定正式batch/LR/schedule。

## 2. 前置条件与执行范围

- 先读COORDINATION/STATUS最新S02说明，再读sessions README、S02_WORKING_SET、REPORT_TEMPLATE、S00_REMOTE_REVIEW、S00/REPORT和INPUT_CONTRACT，复核remote_context的图像payload及s6原始配对顺序。另读执行期间新增的S00/PENDING_ITEMS与closeout_status。
- 接受依据：`ACCEPTED_EVIDENCE_HANDOVER / NEW_NUMERICAL_AND_PERFORMANCE_ACCEPTANCE_PENDING`。协调复核的S00报告SHA256=`8c10b0b2182608eba42eeaa14285d6ee05c9d9f088e9b1bd51fc44ccd3deec08`，与S00保存的REPORT_ACCEPTED_HANDOVER_20261104.md重算一致。并发收尾后的当前报告SHA=`b67004b15bdca8e998be3dc8d9e10fa12eedc2b89a1949af7727f1fbb94cfa23`，两版分开记账。
- 校验上一轮S02的23项索引后，将全部24个文件原样归档到`history/before_pairing_20261104T092345Z`；旧报告SHA=`17760409ab3df2c41147ebfa88383dc5eb725ee549c9bd348b0dbaa16804b29f`。未覆盖未知产物。
- 模型原件/S00/S02副本保持一致：s4_models SHA=`9ff6417b80c42cee0df02fc52e1892b20cd7cd0abda36c7272bb8957a42fc2c2`，kml_ops SHA=`e6c5c4411c453c8168939cd51d737a7e9d8232bdfff05da3967805a5e917ff26`。独立training_step本轮不变，SHA=`524e35817080a3f28a0bc0cda8ecce9c8264b15d73edebe05c5d9d8b9632a0aa`。
- 新candidate/paired_inputs.py SHA=`51d44bd85cdd9e730c9bc455dc796e9c7d6849f33326df7372c95227f24087b1`；更新的tests/check_equivalence.py SHA=`e9b53136146c062b0817fd0bf63632ad6c8cde6daa8d862cf78ba10431024a3e`。最小diff：training_step.diff、paired_inputs.diff、equivalence_pairing.diff。其余改动为测试/文档/审计；没有共享核心修改。
- 开始108个原文件与当时87项S00索引核对通过；结束108个原文件与当前91项S00索引核对通过。S00作者并发更新报告/RUNBOOK/两份审计JSON并新增4个收尾文件，详见s00_owner_changes及dependency_changes；原模型、输入证据、已接受报告快照不变。没有把作者收尾误称为S02修改或新的性能接受。
- 本任务只写`E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S02`。阶段二/三、冻结corpus、原demo、正式manifest/配置、HBM/KML和其它任务目录未修改。没有Git提交、远程路径创建、上传、部署、SSH或作业。

## 3. 环境、复现方式与成本

| 项目 | 本轮证据 |
|---|---|
| 主机/系统 | DESKTOP-54BJCD6，Windows AMD64，build26200 |
| 默认Python | `C:\Users\A\AppData\Local\Programs\Python\Python311\python.exe`，3.11.9，无torch/numpy |
| 既有隔离环境 | `E:\Codex\home\cache\phase2-speed-venv`、phase3-speed-venv、phase4-speed-venv均有numpy、无torch；未改环境或安装依赖 |
| 配对测试环境 | `E:\Codex\home\cache\phase4-speed-venv\Scripts\python.exe`，Python3.11.9、NumPy2.2.6，模块来源见local_validation.json |
| 时间/退出状态 | 本轮归档UTC=2026-11-04T09:23:45Z；检查起止见local_validation、交付时间见delivery_validation，上海时间=UTC+8；实际退出码0/0/2/2 |
| 运行时/绑定/预热/计时 | torch/KML/OMP/oneDNN未加载，编译器/计算节点NUMA/HBM未测；无实际线程绑定、预热、计时或job ID |
| 成本 | 新增节点小时0、GPU小时0、作业0；未运行远程或超时计算 |

从项目根复核：

```powershell
python -B c2\stage4_sessions\work\S02\tests\test_contracts.py
& 'E:\Codex\home\cache\phase4-speed-venv\Scripts\python.exe' -B c2\stage4_sessions\work\S02\tests\test_paired_inputs.py
python -B c2\stage4_sessions\work\S02\tests\check_equivalence.py --belt 32_skip4 --part pre --microbatch 16 --checkpoint --output c2\stage4_sessions\work\S02\evidence\numerical_not_run.json
```

第三条当前退出2/NOT_RUN。真实torch+numpy环境命令、显式KML选择及资源前提见RUNBOOK；依赖存在或Windows计时不属于C2验收。

准备矩阵：belt2×pre/dec×microbatch64/32/16×CKPT0/1×fresh/seeded AdamW历史=48组，均未执行、指标null。完整12×512/8编码器/原U-Net/64×64，fp32、同初始权重、有效单进程B64、lr1e-4、betas0.9/0.999、eps1e-8、weight_decay0.01；seeded是人工state，不是训练checkpoint。seed0，每belt两placement×每单元4帧=8个配对合成帧，经loader后有放回抽取B64 idx并冻结mask/t/noise。16为M208，32_skip4偏移5、M928。无DDP，有效全局训练batch不适用。

## 4. 正确性

输入协议详见INPUT_PAIRING_PROTOCOL：源描述含可信冻结NPZ/sidecar SHA，核对belt/unit、drives/meas顺序、base_of_pair与states行身份；cur与images从同源同row读取。source顺序保留，帧ID含两个SHA、case/placement/belt/contact/unit/row/baseline；目标不跨belt共享。

本次合成准备使用`per_belt_frozen_cohort_absmax`：电压按逐帧参考绝对均值归一化并×100；图像scale在本belt完整固定源集合计算一次，不随微批重算；非finite/零分母拒绝。正式训练采用每belt或统一scale、统计是否仅来自训练集仍待协调冻结，不能将本准备直接当作正式决定。真实源/sidecar、权威split、行映射和物理单位等条件尚未补齐。

原数值容差不变（VALIDATION_PLAN）：逐张量max_abs与L2 relative=`||c-r||2/max(||r||2,1e-12)`；参考norm<=1e-8只看绝对差。输出/loss、梯度、更新参数及增量max_abs≤2e-5且relative≤2e-6；AdamW moments绝对/相对≤2e-6；step/keys/shape/dtype精确一致。没有看本轮结果放宽。

| 检查 | 实测差异/结果 | 证据 | 状态 |
|---|---|---|---|
| 旧demo目标关系 | 两placement均demo SHA=32源SHA，且!=16源SHA | pairing_review.json，重算保存的remote_context | 快照关系确认；旧16目标配对失败 |
| 配对、参考展开、归一化、帧顺序 | 两belt合成数组与独立公式预期严格一致；电压扰动与图像均值关系通过 | pairing_tests_after.txt、test_paired_inputs.py | 10项真实NumPy检查通过 |
| 拒绝错误输入 | 跨belt/同形图像改写/重复源/非法reference/侧车帧错配/协议乱序/零分母或scale/非finite均拒绝 | 同上 | 本地通过 |
| 分母与更新结构 | 既有Fraction代数负例、正确加权、AST与副本字节检查 | tests_after.txt | 4项通过；无autograd |
| 输出与loss | 原始mean参考和候选接入同一配对v/y0，准备记录输入/初值/随机变量SHA | check_equivalence.py | 模型未运行，无误差值 |
| 输入与参数梯度 | 逐预期梯度集合；pre decoder无梯度，dec mask_tok/预训练heads无梯度 | 同上 | 未运行 |
| optimizer更新与状态 | 一次step、权重/增量、fresh lazy state、seeded非活动state严格保留 | 同上 | 未运行 |
| state_dict/dtype/NaN/缺失梯度 | 逐键/逐tensor检查及真实小张量负控准备 | 同上 | 未运行；小张量autograd也未运行 |
| 依赖缺失 | 默认/NumPy两个解释器均退出2/NOT_RUN | numerical_not_run、numerical_numpy_env_not_run、local_validation | 依赖门通过；模型未运行 |

先测试后实现：新增10项在loader缺失时预期ERROR；首次实现后9项通过，1项因测试错误要求`(images/scale)*scale`逐位还原而失败，最大回乘差1.4901161e-08。随后改为直接对照`images/scale`，10项通过；未改归一化公式或放宽容差，失败日志保留为pairing_tests_first_after。没有torch桩、缩小模型或模拟梯度；NumPy数组检查不属于训练步等价证明。

## 5. 性能与内存

| 配置（两belt及pre/dec分别） | 域数/有效结果数 | 有效批量/精度 | 总步秒数 | 吞吐/最慢域参考 | DDR/HBM峰值 | 状态 |
|---|---|---|---|---|---|---|
| 新协议B64×1 CKPT0参考 | 未运行/0 | 单进程64/fp32 | 未运行 | 未运行 | 未运行 | NOT_RUN |
| 同协议B32×2/B16×4 CKPT0 | 未运行/0 | 同上 | 未运行 | 未运行 | 未运行 | NOT_RUN |
| 同协议B64×1/B32×2/B16×4 CKPT1 | 未运行/0 | 同上 | 未运行 | 未运行 | 未运行 | NOT_RUN |

各配置见planned_matrix；不存在数值/性能原始指标。没有总步时、相对收益、波动、最优配置、同步训练、三有效轮或第二主机。旧demo历史计时与新输入协议分开记账。

静态逻辑清单保留：67,412,226参数，fp32权重257.157MiB、全模型AdamW moments514.314MiB、pre/dec梯度144.942/256.652MiB；历史state建立后的权重+moments+当前梯度小计916.414/1028.124MiB。**不含激活/workspace/输入/allocator/容器/页碎片，不是峰值；torch numel动态核对也未运行。**

32电极B64/B32/B16的单个FF隐层464/232/116MiB，单个h116/58/29MiB；CKPT仅覆盖encoder。SDPA临时分配、decoder激活、输入常驻及DDR/HBM同时占用未知，不将理论尺寸相加当工作集。本轮loader的源字节快照是输入完整性准备，未经加载峰值优化；等价脚本参考快照也不得计作训练峰值。

MEMORY_REVIEW给S03静态大小类与生命周期测点；实际同时存活/热度trace仍缺。DDR RSS/PSS、hugetlb/HBM驻留、tensor存活、arena high-water与累计申请字节需分列，不能互代。未改分配器或缓冲复用。

## 6. 接受条件与限制

已完成：最新复核与旧demo错误证据核对；已有S02归档；配对身份/归一化协议、只读loader和10项NumPy检查；4项既有检查；完整模型脚本接入同一配对输入、预备记录固定张量/初值SHA；48组矩阵、训练步、静态内存、diff与哈希。

未完成：真实NPZ适配/独立输出及逐行来源验收、权威subject split、训练统计冻结、torch输出/梯度/AdamW/CKPT、实际numel/内存/吞吐、1→4→16域、三轮及第二主机。GN/采样J_scale及J全finite未处理，GN=SAMPLING=0不能伪记它们通过。沿S00/PENDING_ITEMS的E01–E05/I01–I06/D01–D04保留责任和恢复门槛，本地合成准备未解除真实输入与运行前置。

**本地准备可评审；M2数值、内存和性能门槛未通过，不建议正式集成。** 回退为停止导入S02独立模块；共享源/入口/manifest/数据未改。未来失败保留证据，不凭loss接近接受，不自动放宽容差。

下一步由协调审核本协议与真实资料，在S01运行器接受后安排有限数值/内存小试；本报告不新增算力或正式batch/LR/schedule授权。集群连接/性能按协调分工处理，本窗口未探测。S07还需另定跨rank mask分母与DDP平均补偿，当前不声明多rank等价；S03不能把静态清单当成实际热度/同时占用或4GB达标。

## 7. 证据索引

任务绝对根：`E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S02`。逐文件SHA（含历史归档）见ARTIFACT_SHA256.txt，索引不自哈希。

| 产物 | 绝对路径 |
|---|---|
| 报告 | `E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S02\REPORT.md` |
| 全交付物哈希 | `E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S02\ARTIFACT_SHA256.txt` |
| 配对协议 | `E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S02\INPUT_PAIRING_PROTOCOL.md` |
| 容差/内存/命令 | `E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S02\VALIDATION_PLAN.md`；同目录MEMORY_REVIEW.md、RUNBOOK.md |
| 配对loader/新增diff | `E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S02\candidate\paired_inputs.py`；同目录paired_inputs.diff |
| 训练步/新增diff | `E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S02\candidate\training_step.py`；同目录training_step.diff |
| 完整模型检查/增量diff | `E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S02\tests\check_equivalence.py`；candidate/equivalence_pairing.diff |
| 合成配对夹具/检查 | `E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S02\tests\paired_fixture.py`；同目录test_paired_inputs.py |
| 旧demo证据复核 | `E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S02\evidence\pairing_review.json` |
| 配对测试三阶段日志 | `E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S02\evidence\pairing_tests_before.txt`；同目录pairing_tests_first_after.txt、pairing_tests_after.txt |
| 实际本地退出码/输出 | `E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S02\evidence\local_validation.json` |
| 模型未运行证据 | `E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S02\evidence\numerical_not_run.json`；同目录numerical_numpy_env_not_run.json |
| 原文件/S00/依赖前后核验 | `E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S02\evidence\source_integrity_before.json`；同目录source_integrity.json、s00_owner_changes.json、dependency_changes.json |
| 环境/副本/静态内存/48组矩阵 | `E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S02\evidence\environment.json`；同目录baseline_manifest.json、static_memory.json、planned_matrix.json |
| 上一轮原样归档 | `E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S02\history\before_pairing_20261104T092345Z` |
| 归档/交付复核 | `E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S02\evidence\revision_start.json`；同目录delivery_validation.json |

未向其它聊天/外部服务发消息，未改COORDINATION状态；报告由用户交总协调审核。
