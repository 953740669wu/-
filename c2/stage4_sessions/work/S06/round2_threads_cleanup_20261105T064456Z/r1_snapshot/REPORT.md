# S06：torch.compile预备轮

日期：2026-11-05（Asia/Shanghai）。状态：**READY_FOR_REVIEW（预备交付） / LOCAL_ONLY / CLUSTER_NOT_RUN**。C2执行、数值通过和性能候选接受均未达成。

## 1. 结论

已交付无安装、有界、导入隔离的最小探针及S00 Linux入口。本机无Torch，实际探针以ModuleNotFoundError退出1，后续阶段停止；这是本地环境阻断证据，不是C2的Torch/权限失败。未新增性能或数值结论，不建议集成模型改动。

先复核已有负面结果，明确排除旧网格搜索：

| 项目 | 既有记录与源码复核 | 本轮证据边界 |
|---|---|---|
| KConv2d显式im2col | C2_OPTIMIZATION_REPORT卷积段记载慢3–9倍、历史误差≤1e-5；当前kml_ops的_cols使用F.unfold，反向重建列并F.fold | 本轮未取到原始opt_kconv日志，未重做数值/计时 |
| 全局MKLDNN=0 | 报告记录fallback im2col超时；当前模型仍保留该环境开关 | 不禁用MKLDNN、不重跑 |
| bf16卷积反传 | 历史16-belt/B16整步102秒、卷积反传97.7秒；另有autocast415秒记录，属不同配置 | 保持CPU fp32，不做精度实验 |
| profile | 历史KML/shim的16-belt卷积反传约2.0秒、前向1.2秒、合计约43%；32-belt卷积约5.2秒，copies/fills/逐元素约3–4秒 | 历史配置与波动不同，不能相加或充当本轮profile |
| compile | 历史报告称Inductor读root-only syssentry egg-info失败；计划F建议隔离site路径 | 本地归档未找到原始syssentry traceback；C2当前错误未复现，不能断言仍失败或已修复 |

原计划E的≥3 TFLOP/s、3.3→≤1.2秒与F的非GEMM≤15%均未测。无收益证据也未产生，不标NO_GAIN。

## 2. 前置条件与执行范围

先读HANDOFF_PROTOCOL、总表、S06_DECODER、SESSION_STATUS_TEMPLATE、REPORT_TEMPLATE、sessions README，再按需读原报告卷积/compile/profile及原计划E/F、S00环境证据。总表的“未启动”是旧协调快照，本轮用户已授权预备工作；S06未改总表。性能候选仍等内存评审。

修改前核对当前源码及大小/mtime/SHA；同一读取前后stat一致。`baseline/s4_models.py`、`baseline/kml_ops.py`是当前项目根逐字节副本，未应用S01/S02模型改动：

| 当前源码 | SHA256 |
|---|---|
| s4_models.py | 9ff6417b80c42cee0df02fc52e1892b20cd7cd0abda36c7272bb8957a42fc2c2 |
| kml_ops.py | e6c5c4411c453c8168939cd51d737a7e9d8232bdfff05da3967805a5e917ff26 |

参考文件身份见source_identity.json（15项来源、源码/环境引用、Git HEAD和mtime）；环境历史四库身份见baseline/environment_expected.json。结束时重新比较原始模型/KML与副本，见evidence/final_verification.json。源码副本零diff；未改核心、阶段二/三、输入/manifest、共享库或其它任务目录。共享Git已有其它任务改动，未切分支/操作暂存区，不把外部状态变化归为S06改动。

## 3. 环境、复现方式与成本

本地DESKTOP-54BJCD6，Windows AMD64，Python3.11.9；torch/numpy均缺失。evidence/local_environment.json及local_probe_r1b/imports/result.json记录实测解释器、平台、隔离flags/sys.path、源码SHA与原始异常。

S00历史job2026223/cn21417（2026-11-04）曾导入Python3.9.9/aarch64、Torch2.7.1+cpu、NumPy1.26.4及现有KML/OMP；这些是已读取的旧证据，不是S06本轮远程核查。该记录没有torch.compile验证。探针核对同版本/模块路径及torch_cpu、shim、KML、OMP四库SHA，漂移即停。

新入口与原执行环境的差别限于诊断控制：`-I -S -B`、显式原依赖路径、S06缓存/临时目录、编译并发1、关闭错误静默回退。模型执行仍为原CPU fp32、KML_LINEAR=1、LINEAR_DTYPE=fp32、MKLDNN开启、KML_CONV/CKPT/CHANNELS_LAST关闭；不引入HBM或新精度。探针的小输入不等于历史完整B64配置。

本地命令：

```powershell
python -B c2/stage4_sessions/work/S06/tests/test_probe.py
python -I -S -B c2/stage4_sessions/work/S06/candidate/run_probe.py --out c2/stage4_sessions/work/S06/evidence/<全新本地目录>
```

S00完整Linux命令、资源、核绑定、执行前提和回传见C2_HANDOFF.md；candidate/run_linux.sh不提交作业。建议申请上界660秒/独占节点、38分配核/36实际核、8192MB DDR；每段120秒/合计600秒/外层640秒终止，不扩大矩阵。预计最大0.1833节点小时；本轮实际集群节点小时0、job0，未创建远程目录。C2活动进程/已有job未查询，不能称集群空闲。

## 4. 正确性与新增小检查

先写7项小检查，初次因探针尚未实现而失败（tests_before.txt）；实现后发现Windows strict路径解析PermissionError，修正为路径存在性/目录检查并保留失败证据。最终7/7通过，属于准备逻辑检查：

- 要求-I/-S；恶意PYTHONPATH/sitecustomize及.pth不执行。
- 缺依赖目录拒绝；源码SHA漂移拒绝；当前源码与冻结副本一致。
- 子进程失败不报PASS；超时非PASS。

两份候选Python通过Python3.9语法解析；这不是Python3.9实际执行或Torch数值验证。Bash首次受限进程中因MSYS NtCreateDirectoryObject权限失败；随后仅在受限进程外执行bash -n，exit0。没有执行Linux入口，也没有因此连接集群。

| 检查 | 预设标准 | 本轮实际状态 |
|---|---|---|
| 隔离与错误传播 | 拒绝环境注入、缺路径、SHA变更；失败/超时非PASS | 7项准备检查通过 |
| 真实探针本地执行 | 导入失败留下原异常且停止 | torch_import：ModuleNotFoundError，父子exit1；后5段not_run |
| tiny pointwise/conv/block输出和梯度 | fp32逐元素rtol=atol=1e-6；max_abs、L2差/max(ref L2,1e-12)；shape/dtype/finite/缺失梯度 | 全部未运行，无误差数值 |
| KML/ctypes/autograd捕获 | explain原始graph/break原因，再Inductor fullgraph严格路径，不自动fallback | C2未运行；data_ptr/ctypes为源码可见风险，不是实测break证据 |
| loss/optimizer/状态更新 | 完整模型原标准保持 | 本轮无模型候选，未运行 |

原解码器Block从未经修改的模块加载，使用原首块128→128、时间维512、无attention；仅B1/8×8诊断。KML另用128×512避开原tiny fallback。未更改完整模型分辨率/架构/损失。原始完整UNet/Encoder没有实例化或执行。

## 5. 性能与内存

没有C2微算子、整步、内存、四域、整节点或第二主机结果。探针只预留首次编译+前反向和两次预热后原始时间字段；检查成本单列说明，不作训练吞吐或摊销推断。需要多少训练步摊平编译成本目前无法计算。无速度/内存收益或科学等价结论。

## 6. 阻塞、回退与下一步

已完成本轮预备交付；后续执行依赖S00独立排期。当前具体缺项是本地Torch缺失、C2隔离依赖是否齐全未知、CXX/链接器/Inductor代码生成未执行、syssentry现场错误与KML graph break尚无本轮证据。未安装Torch/依赖、重编框架、注册custom op、改权限或扩大性能搜索。

回退只需不用探针；生产源码与运行环境未替换。S00收到包后先校验SHA/历史运行时身份和分配CPU/DDR，再按命令执行一轮；失败原样回传，不自动换版本或继续搜索。只有内存阶段评审后才考虑完整性能候选。

## 7. 证据索引

统一绝对根：`E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S06`。

- SESSION_STATUS.md / ROUND_DELTA.md：当前快照及本轮六行变化。
- C2_HANDOFF.md / candidate/run_linux.sh：S00可执行入口与边界。
- candidate/probe.py / run_probe.py / tests/test_probe.py：探针、超时/失败传播、小检查。
- baseline/：两份零diff源码、历史运行时参考和期望环境身份。
- source_identity.json / evidence/final_verification.json：来源与结束身份核验。
- evidence/tests_before.txt / tests_fixture_failure.txt / tests_after.txt / syntax_checks.json：真实失败/修正/最终准备检查。
- evidence/local_probe_r1/：首次实现的Windows路径权限失败，非syssentry或C2错误。
- evidence/local_probe_r1b/：修正后的Torch缺失、父进程失败与后5段未运行；cache为空的专用缓存目录。
- ARTIFACT_SHA256.txt：本轮文件相对路径及SHA（清单自身除外），用于S00逐文件校验。
