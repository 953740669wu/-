# R7通过后的下一项：S02 CPU36 C2/KML 数值对照

日期：2026-11-05。总协调已独立接受job2034247的有限36核完整启动证据。先读CPU36_R7_STARTUP_RESULT_REVIEW.md；S01专项复核待补，可以与S02本地包装准备并行，不重复启动测试。

## S01

只读复核S00/CPU36_R7_STARTUP_REPORT.md及evidence/r7_cpu36_2034247的真实合同/监督/汇总证据，补充结论到自己的新报告。确认没有阻断问题即可，不要求重跑模型、重测环境或改版本。发现问题应说明具体证据和影响，不能删除检查求PASS。

## S02

任务目标是把已有严格诊断安全地用于C2的36核配置，直接准备下一组实际数值对照；不重跑已完成的Windows九项因果实验。

1. 从最新round3_20261104T134939Z的diagnose_update.py、diagnostic_common.py、run_c2_diagnostic.sh及C2_HANDOFF出发，在自己的新round目录最小修改CPU/运行包装；根REPORT与旧4核包保留历史身份。参考S01/revisions/R7_CPU36_RUNNER_20261104T151540967239Z的cpu36_contract.py和INTERFACE_FOR_S00_S02.md。
2. 使用已验证C组环境OMP36/MKL36/OpenBLAS1/OMP_PLACES=cores/OMP_PROC_BIND=close。框架导入前捕获实际授权/拓扑并选同域36物理核、留末2核；在实际checker同PID内检查框架后Torch36和全部TID非空子集，允许close下调用线程单核。旧threads4、只查调用线程全集或未绑定子进程的守卫不得继续作为执行入口。
3. 数值模型、loader、有效B64、micro32×2、loss分母、fp32/CKPT0、fresh AdamW参数及原严格阈值保持不变。固定case沿用round3/case/fixed_16_pre.pt，SHA256为4de1fb40eb1c4b43a8747586399f336bf9e37184592d66fdbf711abad8469846；不能在C2重新抽权重/输入，也不沿用已知目标错配的legacy demo做科学数值对照。
4. 第一组只准备16_adjacent/pre、backend=kml、mode=strict的一次完整参考/候选对照。必须确认实际KML/shim/OMP库路径、SHA和调用证据，不静默fallback native。正/负守卫检查应覆盖Torch1、越界和错误CPU数量，不能用本地mock冒充C2模型结果。
5. 交付最小diff、源码/代码包/case身份、新CPU36执行命令及原样通过或失败的判据。只写S02自己的新目录，不改S00或协调文件。先交本地新包供核验；不因真实C2尚未运行而重复做环境安装。

## S00后续执行

S01专项复核无阻断问题、S02新包核验通过后，使用已有登录方式在账号自有全新目录执行一组C2/KML严格对照。每域实际36核、首选分配38留2核，24576MB及同值限制、最多900秒；实际包SHA/LF/Linux语法门槛保持。

本次只做这一组对照，数值失败完整保留，不改容差、eps、模型、样本或检查器求PASS，也不自动追加控制矩阵。普通包装问题按照STATUS顶部的有界修复方式处理。回传实际作业/资源/线程/后端/初值与输入身份、全部逐项数值指标、退出与日志，明确区分运行错误与数值FAIL。

训练内存/HBM收益验收仍等待数值门槛及独立训练内存入口；本轮不扩大32电极、decoder、四域/整节点或长训练。
