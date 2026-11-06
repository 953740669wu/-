# R9：唯一一次真实工程五步性能剖析

2026-11-06，Asia/Shanghai；依据用户要求推进真实样本工程训练和优化、现已交02/08完成摘要，作下一轮明确有界安排。只先读最新短状态/变化摘要，缺项和具体新部署审核时再展开必要证据。

## 已核交付与此次安排

- 08已完成job2043445真实SUMMARY，19项交接/16项结果核对为作者实际结果，CLI无issues；协调另核7份摘要绑定原件bytes/SHA，与原运行事实一致。该轮无剩余执行任务，不重跑工具或训练。
- 02 R9本地剖析准备完成；完整Encoder、原1600工程帧/16unit/seed0/B64、原mean/AdamW/fp32/CKPT0/KML不变。原训练耗时占程序67.46%，不代表已知attention/linear/反向/AdamW内部排序。
- 固定代码包：work/S02/round9_profile5_20261106T023240Z/package/S02_R9_PROFILE5_CODE.zip，69674bytes/25成员；SHA=15621eaa3328e407059c352d86a0f49ee68bfea39f02a68503ded6f94099abe3。源码清单SHA=2a86fd01cab96a85cb2f0f4c8ed998edb956ef81255dfd5ceb950d41264de741；PROFILE_READY/PROFILE_CONTRACT/README及REFERENCE_FIRST5均在该轮目录。
- 协调核9份就绪绑定、24份源与ZIP字节、CRC及Python3.9 AST，定向读新增probe/contract/训练/入口；6项小型检查按作者记录，不重跑完整模型。证据R9_PROFILE5_S08_SUMMARY_REVIEW_20261106.json。Linux profiler能力仍未知，不能以本地准备PASS代替现场结果。
- 本卡给出**新的唯一一次R9有界执行安排**，不复用job2043445授权/marker。只在01对具体新代码/新部署/原数据描述给SHA绑定专项PASS后，00直接执行一次；不需再让用户中转放行。本卡不改已冻结PROFILE_READY中“发布时未授权”的历史字段，不触发root实际提交。
- 资源：单节点单NUMA38分配/实际36预留2、DDR24576MB且limit同值、exclusive、HBM0，最多900秒；整个应用840+清理30+收尾30，内部720秒停止新更新。唯一job，不自动重试、不扩样/扩预算/补跑；不操作其它任务或生产源。
- 工作量：同seed0前5次连续更新，1—2预热、3—5分别采样CPU事件，实际训练320帧；全部1600帧仍用于同一工程归一化统计。达到5步即停，无正式val/test，不延长为完整epoch或长训练，不加载/覆盖旧checkpoint。
- 输出限制：最多3份trace各8MiB、3份events各1MiB；每采样最多50000事件、256个KML包裹标记，事件数在单步结束检查，不能说采集中实时截断。能力缺失/超限/数值或来源/CPU/KML/预算异常即停，无截断、无backend回退或重试。
- KML包裹含Python/分配/ctypes/原生时间，不称精确内核时间；嵌套inclusive时间不相加，跨线程CPU和不直接除wall称占比。剖析扰动单列，3步结果不称正式吞吐/稳态加速。

## S00：新部署及条件满足后唯一执行

**本轮目标**：准备匹配PROFILE5协议的新部署，交01审核；通过后直接一次现场采集并跟踪终态。

**参考文件**：自己的短状态；本卡；02 R9的PROFILE_READY.json/PROFILE_CONTRACT.json/README.md、冻结包和来源清单；原job2043445描述/环境/完整清理方式只读参考。

**完成标准**：

1. 先只读查实际队列/原提交目录/本轮marker，去重且不操作其它任务。只写S00新round9_profile5_20261106/，远端新建/home/share/dengqingtian/opt/stage4_sessions/S00/S02_PROFILE5_<新唯一时间>/payload；原ENGINEERING_PILOT输出和checkpoint不改。新入口自身要求新目录/新job，不能为了跑通绕过这些门禁。
2. 原工程descriptor字节/SHA必须仍为b88ea9745147acf7fa70d51dc27c727f22f14e98af5dff1b80a9047e95648cd6；manifest、原16个NPZ/sidecar/源身份前后不变。同一已选case，不另选数据，不再寻找正式split作为前提。现场元数据/LF/bash-n/源与ZIP字节先核，不在登录节点跑模型。
3. 适配新的PROFILE5协议、成功/失败/unsupported/limit/incomplete状态、原生job交接/实际资源/CPU36/全部所属后代清理；新账本写profile_JOB目录，旧descriptor指向的运行账本只读。不得原样使用只接受旧PILOT协议的成功判据或收集器。
4. 在本轮S00_DEPLOYMENT_READY.json发布部署包/源码索引/元数据检查/资源/命令和停止条件的path/bytes/SHA，锚定原02 PROFILE_READY及descriptor，供01读取。发布后冻结，不热改已核包。可先完成部署，不等用户再次转发。
5. 等work/S01/round9_profile5_review_20261106/S01_REVIEW.json明确decision=PASS_FOR_ENGINEERING_PROFILE5、review_complete=true且绑定全部最新SHA。提交前重新核代码/部署/审核/descriptor等身份、实际队列和独占唯一marker；同一有界安排仅一次dsub。FAIL或不一致不自行改判、不重提。
6. 收完整5步记录、每步原baseline loss比较结果、帧/mask/初始化/scale/KML身份、3trace/3events、CPU/库/分配/调度/退出/清理和新暴露账本；checkpoint只留远端收路径/bytes/SHA与零额外更新恢复记录。追踪本job到终态/PID清空；若排队超过60分钟仍未启动，可取消自己本轮排队job并留报，不重提。
7. 成功必须5次连续AdamW/320帧/2预热3采样、前5步原loss门槛、全部必需采样及来源/CPU/KML/恢复证据齐；缺事件、超限或数值失败按原字段停止。现场能力不支持也有价值，准确记录UNSUPPORTED而非转跑其它方案。
8. 本轮可有限等01就绪：每30—60秒只读查固定文件，累计最多90分钟，不占计算节点等待、不装后台服务；超时保存停点。结束更新短状态/六行摘要、完整结果交接和精确归档清单，不操作Git暂存。

## S01：新剖析包与部署专项复核

**本轮目标**：复核02 R9及00具体新部署，绑定SHA放行本轮唯一有界执行；不重复旧工程审核或原25步数值。

**参考文件**：自己的最新短状态；本卡；02 R9 PROFILE_READY、源码/最小diff/原first5参照/检查原件；S00/round9_profile5_20261106/S00_DEPLOYMENT_READY.json及具体交付；旧01审核仅作来源边界参考。

**完成标准**：

1. 只写S01/round9_profile5_review_20261106/及自身状态。先核原模型/算术/帧序/mask/初始化/统计及loss比较门槛保持、2+3事件时序、事件/文件/标记限额、不支持/超限拒绝、恢复不多更新，以及旧冻结源/账本不会被覆写。
2. 对00审核新原生job身份/CPU36/资源/唯一marker、全入口硬时限和所属后代清理、新协议的完整成功/失败判据及3trace/3events收集。不能把本地mock当Linux真实信号清理已测；未现场触发部分准确保留。
3. 作者6项检查已通过时只核其覆盖与原件；存在具体疑点再补最小独立检查，不重复完整模型/旧5315或所有旧runner测试。审查记录不能修改作者源码、原PROFILE_READY/contract或旧01冻结审核。
4. 写固定S01_REVIEW.json，decision=PASS_FOR_ENGINEERING_PROFILE5或FAIL/BLOCKED，明确review_complete及代码包/源码清单/contract/reference/descriptor/部署包/部署索引/资源等精确绑定。通过后00可按本卡直接执行，不等总协调在线；记录仍非科学/稳态性能或生产接受。
5. 00部署未到时可先审02代码；按同一90分钟有限等待约定接后续，不结束后声称后台继续。发现实质问题交定位，停止放行，不代改作者源。结束更新短状态/六行摘要/精确待归档清单。

## 其余窗口与Git

- 02已完成本地准备，待01具体意见及00本轮结果，暂不改冻结包/做第二候选；08真实摘要已完成待归档，无需重做。
- 原真实训练257文件批次Git窗口已记录普通推送GitHub完成，HEAD=f1ed9f23943263cbe07b700a93c5503e6220a577（协调只读核本地HEAD一致，远端实时核依据Git窗口）。不要修改上一批冻结TSV或补入新文件。08真实摘要和02 R9等新成果下一批另列精确范围，核验后提醒唯一Git窗口；准备好不等于C2接受。
- 03/04/05/06/07不扩；现场结果回来先按新增耗时证据选择一个优化点，不开展无界搜索。各任务只报本轮六行变化，必要时才展开报告。
