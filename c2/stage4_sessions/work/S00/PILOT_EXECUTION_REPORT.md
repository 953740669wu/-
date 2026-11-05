# S00：S01 单域启动尝试与 S02 绑核修正

日期：2026-11-04（Asia/Shanghai）。状态：**READY_FOR_REVIEW / S01_STARTUP_FAILED_STOPPED / FULL_MODEL_NOT_REACHED / S02_BINDING_FIXED / S02_MODEL_NOT_RUN**。

## 1. 结论

按用户授权实际提交一次S01小试，申请和分配均为38 CPU、24576MB，显式mem资源限制24576MB，900秒、单NUMA域、独占节点。job **2026356** 在 **cn21338** 于 **21:46:29–21:46:30 +08** 启动后失败，jobExitCode=2。失败在S00新增shell包装器，尚未进入CPU guard、S01预检或完整模型计算。不是模型数值/性能失败，也不是OOM。

原因：本轮调整包装器目录限制时，在Windows用Path.write_text重新写入，引入CRLF。Linux日志为`set: pipefail: invalid option name`；此前远程bash -n也已报错，但提交操作没有以该检查成功为前提，因此仍提交了这一次作业。这是S00打包与提交流程错误，不应归责S01候选。

遵守用户“失败即停止”，**没有重提S01、没有扩大规模、没有提交S02作业、没有训练内存测试**。原失败包/日志保留，当前修正版另存，不覆盖历史失败证据。

## 2. 范围与冻结身份

本地与远程均只写S00独立任务目录。远程实际根：

```text
/home/share/dengqingtian/opt/stage4_sessions/S00/PILOT_S01_20261104T134538Z/
```

实际提交包SHA256：`5bb0a6718ec8ae3eb794e7f05f0faae9addd22342df0253833234320427a7616`，逐字节留存在evidence/executed_packages/S01_job_2026356.zip，对应清单为PACKAGE_MANIFEST_job_2026356.json。

S01的8份接受源码、S02的10份来源文件、原模型/候选/数值阈值均未修改。所有原始108个项目文件另做终态SHA复核。共享项目/输入/manifest及其它任务目录不改。

本轮已修正当前包装器为UTF-8/LF；verify_delivery.py改用原始字节检查CR，覆盖execution_packages下的sh/env，避免read_text自动换行转换掩盖问题。未来提交命令必须在Linux bash -n成功后才能执行dsub；见更新的CLUSTER_EXECUTION_PLAN.md。修正版仅做验证，没有模型重试。

## 3. 资源、命令与成本

实际请求与分配证据见evidence/s01_pilot_job_2026356.json：q_hpcai、dengqingtian、cn21338、exclusive=true；resReq/resAlloc cpu=38、mem=24576；resLimit.mem=24576；jobWallClockLimit=900。调度记录hwThreads=0-37；包装器早退，未取得模型进程的实际affinity/NUMA测量，不能把调度记录冒充进程验证。

实际提交形态：

```bash
dsub -J -q q_hpcai -R 'cpu=38,mem=24576MB' -RL 'mem=24576MB' \
  -a 'numa[count=1,distribution=pack]' -T 900 --env none --cwd "$R/payload" \
  -oo "$R/job.log" env S01_RUN="$R/payload" bash "$R/payload/pilot_s01_startup.sh"
```

该命令已执行一次；**本轮不再执行**。原参数为单域16_adjacent/pre+dec、B32、fp32、KML、CKPT0、HBM0、3轮REPS1，但模型未到达，不能填造三轮结果。

此次调度开始结束壁时1秒≈0.000278节点小时；加此前4个环境作业34秒，累计35秒≈0.00972独占节点小时。不是CPU核小时/608，GPU小时0。修正版语法和标准库绑核fixture在login10上仅执行微小非模型检查，不作为计算节点训练资源或吞吐。

## 4. S02 绑定修正与检查

S02 shell现在保存调度注入的4核集合，确认恰好4核且同NUMA域，然后显式使用：

```bash
numactl --physcpubind="$S02_CPUSET" --membind="$NUMA_NODE" \
  "$C2_PYTHON" -B "$S02_RUN/run_s02_checker_bound.py" \
  --belt 16_adjacent --part pre --microbatch 32 --history fresh --threads 4 \
  --kml --output "$OUT/equivalence.json"
```

这是准备命令，未运行实际S02模型。OMP_PROC_BIND=false保留显式4核进程掩码，OMP_NUM_THREADS=4，OpenBLAS/MKL线程变量仍按固定环境。新增run_s02_checker_bound.py通过runpy在**同一个Python PID**执行原样tests/check_equivalence.py；不另起一个仅预检的进程来替代checker验证。

该进程在导入前、真实torch导入且set_num_threads(4)后，以及checker退出时核对os.sched_getaffinity(0)与预定4核精确相等；同时检查各线程CPU集合不越界。checker_affinity.json记录PID、预定/实际CPU和各线程集合。源码/阈值/模型/有效B64不变。torch预导入发生在checker设seed/建模之前，不改变其数值比较实现。

修正包在实际Linux通过4项bash -n（S01/S02各自env和wrapper），并完成三个微小fixture正负控：

| 测试 | 预期 | 实测 |
|---|---|---|
| 显式4核，同一PID执行微小checker | 退出0；前/后各阶段4核与PID一致 | PASS |
| 预定4核与实际4核不一致 | 在checker运行前拒绝，非零退出 | EXPECTED_REJECTION |
| 微小checker自行缩小CPU集合 | 退出阶段检出变化，非零退出 | EXPECTED_REJECTION |

fixture仅用标准库及假的torch/numpy模块测试绑定守卫，不运行真实数值checker，也不能据此宣称真实Torch/完整模型的CPU绑定已验收。真实后端下的进程内证据将在未来条件满足后的S02作业内产生。完整原始结果在evidence/fixed_pilot_package_linux_verification.json。

## 5. 更新包身份

当前可复核包（尚未模型重试）位于execution_packages：

| 包 | SHA256 |
|---|---|
| S01_pilot_prepared.zip，LF修正版 | 747f9c36354136afa3383a3d836c7e3db7568a043d1712fb2f03765068b4ec5e |
| S02_pilot_prepared.zip，精确4核与同进程守卫 | de1f683449e4bad6ecab9b98254a669941e3765870b4c705a4ba6c88d2f4795b |

PACKAGE_MANIFEST.json含包和逐文件SHA，PILOT_MANIFEST_S00.json在各包中。失败实投包与当前修正版是两个不同版本，不混用它们的SHA或检查结果。

## 6. 未完成的门槛与停止状态

S01完整启动小试仍未通过，需要后续单独恢复本次停止点；本轮不自动重试。S01模型结果复核通过之前，S02只保留修正包，不能提交那一组C2/KML等价作业。S02既有Windows完整模型严格数值FAIL继续有效；不放宽阈值、改AdamW或更换样本获取PASS。

S02数值未通过之前不执行训练内存测试；独立轻量训练内存入口也仍待S02提供。新性能基线仍未建立，单域→四域→整节点顺序不变，本次没有四域/整节点或额外配置。

## 7. 证据索引

绝对根：E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S00。

- evidence/s01_pilot_request.json：本次请求/资源/提交包SHA。
- evidence/s01_pilot_job_2026356.json：调度完整回执、失败日志、CR字节数及停止状态。
- evidence/executed_packages/S01_job_2026356.zip、PACKAGE_MANIFEST_job_2026356.json：实际失败包及当时清单。
- evidence/fixed_pilot_package_linux_verification.json：真实Linux语法、绑核fixture正负控。
- execution_packages/pilot_s02_equivalence.sh、run_s02_checker_bound.py：精确CPU绑定与进程内守卫。
- execution_packages/PACKAGE_MANIFEST.json：当前包SHA与逐文件SHA。
- tests/test_s02_affinity_wrapper.py：Linux轻量fixture测试，不加载真实Torch或完整模型。
- evidence/execution_package_validation.json、delivery_validation.json、source_integrity.json、ARTIFACT_SHA256.txt：终态交付/源码/哈希核查。
