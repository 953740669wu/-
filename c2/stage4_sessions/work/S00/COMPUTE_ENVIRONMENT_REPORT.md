# S00 计算节点运行环境补充核查

日期：2026-11-04（Asia/Shanghai）。状态：**COMPUTE_IMPORTS_PASS / S01_IMPORT_PREFLIGHT_PASS / FULL_MODEL_NOT_RUN / PILOTS_PREPARED**。

本轮依据用户明确要求补做计算节点实际导入和资源核查，不是登录成功或包元数据检查。已有S00证据交接接受状态不变；没有建立新的性能基线，没有运行完整模型前反向/AdamW或内存优化测试。有限小试安排见CLUSTER_EXECUTION_PLAN.md。

## 1. 实际结果

最终作业 **2026223**，账号dengqingtian，计算节点 **cn21417**，q_hpcai，2026-11-04 **21:09:33–21:09:53 +08**，调度器状态SUCCEEDED、jobExitCode=0。实际完成：

- 同一个隔离venv进程真正import torch和numpy，版本分别2.7.1+cpu、1.26.4；tiny autograd和torch.from_numpy桥接通过。
- KML在torch初始化之后实际dlopen，sgemm/bgemm/sbgemm三个导出符号可见。不是仅检查文件存在，也没有执行KML性能算子或证明完整OMP/算子正确性。
- 用S01 R4包中的原样runtime_preflight.sh/runtime_probe.py执行真实预检，结果PASS：已接受R2源码SHA、两份legacy NPZ身份、numpy/torch/kml_ops与候选s4_models模块导入、实际shim/KML映射均通过，记录15个已加载库文件的SHA。
- 候选模型只是模块导入，没有实例化完整训练、numactl模型调度、前反向、optimizer.step、HBM或吞吐验收。S01此前R4已完成的Linux进程清理/合成协议没有重复运行。

## 2. 可复用解释器与路径

```text
/home/share/dengqingtian/opt/stage4_sessions/S00/ENV_20261104T130730Z_R4/venv/bin/python3
```

该解释器的真实二进制为系统Python3.9.9，sys.executable保留venv路径；NumPy安装在venv自己的site-packages，torch读取现有只读共享树。它不是完整复制了torch及所有依赖的自包含环境，后续运行前仍须冻结/复核共享库身份。

| 项目 | 本次实际来源 |
|---|---|
| torch | /home/share/songzhenlong/eitfm/sw/torch_kml/torch/__init__.py |
| numpy | /home/share/dengqingtian/opt/stage4_sessions/S00/ENV_20261104T130730Z_R4/venv/lib64/python3.9/site-packages/numpy/__init__.py |
| KML实际映射 | /opt/HPCKit/kml-lib/sme/kblas/multi/libkblas.so.1.26.0.RC1 |
| OpenMP实际映射 | /opt/HPCKit/bisheng-lib/aarch64-unknown-linux-gnu/libomp.so |
| 本轮S01预检的shim | /home/share/dengqingtian/opt/stage4_sessions/S00/ENV_20261104T130730Z_R4/S01_payload/lib/libkml_sgemm_shim.so |
| NumPy BLAS | venv的numpy.libs/libopenblas64_p-r0-17488984.3.23.dev.so |
| torch BLAS | 共享torch_kml/torch.libs/libopenblasp-r0-1a7698bc.3.29.so |

可复用环境文件为execution_packages/cluster_runtime.env：设置venv PATH、PYTHONPATH、KML/动态库路径、固定NumPy和线程变量，不含密码。S01 shell会重设PYTHONPATH，因此单纯把NumPy加到外层PYTHONPATH不够；venv site-packages已实际验证能在其原样shell下保留可见性。

原环境在计算节点缺NumPy。本轮从PyPI取得Python3.9/aarch64 NumPy1.26.4 wheel，仅安装在S00独立目录；wheel SHA256为d5241e0a80d808d70546c697135da2c613f30e28251ff8307eb72ba696945764，与官方PyPI版本元数据一致。没有安装/更新共享torch、系统Python或其他任务环境。NumPy版本与S02的Windows NumPy2.2.6不同，后续C2结果须作为独立环境记录，不能覆盖Windows失败记录。

## 3. CPU与内存：授权量和主机量分开

该作业实际resAlloc为 **cpu=1、mem=4096MB**；进程os.sched_getaffinity和Cpus_allowed_list均为 **CPU 0**。虽然host_cpu_count=608，不能使用其它607核。Mems_allowed_list为0–31，不代表获准使用所有内存或已经完成单域内存绑定。

同节点观测到MemTotal约565GiB、MemAvailable约445GiB，**只是整机状态，不是本作业额度**。当前账号读取其memory/cpuset/cpu cgroup文件返回Permission denied，内核内存硬限没有独立读出；资源授权证据来自Donau实际分配记录。未申请提权，也未把文件不可见写成没有限制。后续模型作业应明确申请内存上限并刷新实际CPU/NUMA、可用内存/绑定和资源证据。

这批短作业均已结束，不能作为仍然可用的S01/S02模型allocation。模型小试的38核/4核及24576MB等资源目前只有准备方案，尚未提交。

## 4. 全部尝试、失败与成本

| job | 节点 | 状态/执行秒数 | 原因/结果 |
|---|---|---|---|
| 2026157 | cn21417 | FAILED / 1s | 探针对不可读cgroup调用is_file抛PermissionError，未执行模块导入；不是Torch失败或OOM |
| 2026164 | cn21417 | FAILED / 1s | 修正探针后，三种已列解释器/torch树组合均报No module named numpy |
| 2026200 | cn21417 | SUCCEEDED / 12s | 系统Python+共享torch_kml+S00隔离NumPy路径，真实导入/桥接/tiny autograd/KML加载通过 |
| 2026223 | cn21417 | SUCCEEDED / 20s | 固定venv以及未修改的S01实际导入/输入/库预检通过 |

四作业均仅申请1CPU/4096MB；调度记录exclusive=true。开始/结束壁时合计 **34秒，约0.00944节点小时**，不能按1/608缩小。各调度时限300/240/180/120秒，配置时限合计14分钟是申请上界，不能当实际用时。没有GPU小时或模型训练时长。失败探针源码和日志原样保留；S01/S02目录、已接受候选与数据未修改。

## 5. S01/S02执行前提与限制

- S01：现有R4 Linux协议已通过；本轮补了计算节点import/legacy输入/库身份预检。下一项是受控的完整真实启动链，仍未执行。新S01准备包在已接受源码外只增加环境/小试包装器，源码文件不改。
- S02：已读其最新round2报告，完整16-pre代表配置在Windows未过原定数值容差；没有把它误写成尚未运行。C2准备包保留该严格检查、完整架构/有效B64和原阈值，只计划一组明确标识actual_KML的配置，不自动扩大矩阵。C2即使通过也不抹去另一环境的失败。
- S02内存：数值门槛未过，而且没有已接受的独立轻量训练内存入口；当前NOT_READY。不能在保留参考快照的equivalence脚本内测一个RSS然后宣称训练峰值或内存收益。
- 新性能基线仍要按总协调接受的S01运行器、输入协议及资源排期，单域→四域→整节点推进。上述导入PASS不是模型/内存/性能通过。

## 6. 证据与包

绝对根：E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S00。

- evidence/compute_environment_verified.json：最终可复用环境、资源、S01预检、库SHA和全部作业索引。
- evidence/compute_env_job_2026157.json、2026164.json、2026200.json、2026223.json：实际djob、日志和原始结果，文件名前缀均为compute_env_job_。
- evidence/numpy_wheel_source.json：官方PyPI URL及wheel SHA匹配证据；runtime/wheels保留安装wheel。
- candidate/probe_compute_env.py、run_env_probe.sh、run_s01_preflight_probe.sh：最终S00探针；早期失败/成功版本另存evidence/compute_env_<job>_probe.py。
- execution_packages/S01_pilot_prepared.zip、S02_pilot_prepared.zip及PACKAGE_MANIFEST.json：准备包和逐文件SHA；**模型小试未执行**。
- evidence/pilot_package_syntax.json：三个新环境/小试shell经本机Git Bash沙箱外bash -n均退出0；不把语法检查当作这些模型小试已在Linux执行。
- CLUSTER_EXECUTION_PLAN.md：顺序、准备/提交命令、资源与停止条件。

完整当前交付物SHA见ARTIFACT_SHA256.txt。密码没有写入包、命令文件或证据；登录入口仍为VPN后的dengqingtian@10.44.9.4交互认证。
