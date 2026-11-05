# S00：S03 Linux C安全场景及独立库构建

日期：2026-11-05（Asia/Shanghai）。状态：**READY_FOR_REVIEW / PASS_CANDIDATE_25_C_CASES_AND_ISOLATED_SO / REAL_HBM_NOT_RUN**。

## 1. 结论

在S02数值FAIL已正常终态/清理且CPU证据无错后，按集中执行说明提交独立S03作业。**job2034987 / cn21338 / 11:54:58–11:55:00 +08 / SUCCEEDED / exit0**。没有并发前项，没有重试或启用真实HBM/模型。

使用同一实际C harness编译冻结源和候选：冻结源runner退出 **1**，25场景中 **15通过/10失败**，有明确预期缺陷TRACE，不是编译/基础设施失败；候选 **25/25通过、runner退出0**。独立无测试替身 `.so` 构建、ELF/符号/依赖和SHA记录完成。

独立库SHA256：**bb0af32c6f34e3fa877dfc35655c2a64a65bf120e3fdcac3a900a0e7299e5643**，72136字节。仅保存在本次S00新目录及完整证据包，未覆盖共享库、未用于任何预加载或生产。

## 2. 接受来源、版本与提交门槛

读取S00_NEXT_S02_R5_S03_C_20261105.md、S03_SAFETY_REVIEW、协调包MANIFEST、LINUX_VALIDATION及实际harness/runner。原样包19成员、29925字节，SHA256：

```text
f8b4998223c8c00765666e43f338ebe9540418d6bc326356172357d925c79a21
```

冻结源SHA256为edbf06f54a779271c97d739e4aaca18ffae306ccd20713443ecaee11c388cb15；候选SHA256为8ec586c60c97bbcdb437fe848b6d9645ea3cfca850952ff9d94c0d36fdaed35d。没有修改C算法、25场景判据或S03作者目录。

新远程根：

```text
/home/share/dengqingtian/opt/stage4_sessions/S00/S03_C_20261105T035154Z/
```

远端原ZIP、19个成员、原ARTIFACT索引逐项SHA通过；S00新增执行包装器字节LF/bash -n和所有Python在Python3.9下编译检查通过。提交程序再次核对19个成员及3项实际包装器文件身份，唯一submit marker后才调用dsub。

S00只新增执行包装层：干净环境、CPU选择、实际命令/输出/退出保存、预期冻结失败判读和有界进程组清理。CPU拓扑帮助模块原样来自R7，SHA为3990bb6ba40e7d4e47037aef245c6bc971191e7ae2c4be8701dd329c408a179d。原19文件运行后SHA全部不变；阶段二/三、数据和生产源码未改。

## 3. 环境、资源、命令和成本

账号dengqingtian，q_hpcai、exclusive=true，cn21338。resAlloc cpu=38,mem=24576，resLimit.mem=24576，job时限300秒。实际授权0–37，同NUMA域38个独立物理核心，父执行进程显式收窄0–35，预留36/37；编译器、runner及其C子进程从该进程继承36核掩码。每步记录该集合；没有把串行场景说成36线程性能。

独立环境通过env -i创建，PATH=/usr/bin:/bin、LC_ALL=C，清除S02的LD_PRELOAD、LD_LIBRARY_PATH、PYTHONPATH、KML和HBM变量；driver在执行前断言这些变量为空。没有安装工具链或引入新的KML环境。

实际工具：**/usr/bin/cc，GCC10.3.1；glibc2.34；ELF64/AArch64**。主要编译命令完整记录于steps.json：

```text
harness: cc -std=gnu11 -O0 -g -Wall -Wextra -pthread
frozen additional macro: -DS03_SOURCE="../frozen/hbm_alloc.c"
library: cc -std=gnu11 -O2 -fPIC -shared -pthread -Wall -Wextra candidate/hbm_alloc.c -o build/libhbm_alloc_s03.so
```

每个命令独立session，有界等待/超时仅终止本项session，作业内总deadline270秒、调度上限300秒；本轮无超时。实际开始结束差 **2秒≈0.000556独占节点小时**，不是数值/模型/内存性能。S02另29秒，两项本轮共31秒≈0.008611节点小时；此前377秒另计，累计S00十作业408秒≈0.113333节点小时，GPU小时0。最终PID字段为“-”。

## 4. 冻结源缺陷、候选25场景与独立构建

| 检查 | 实际结果 | 判读 |
|---|---|---|
| 冻结源harness编译 | exit0，实际include冻结C源 | 不是编译失败 |
| 冻结源25场景 | runner exit1，15通过10失败；no_node等控制通过，低页/读取/策略失败有TRACE | 预期缺陷已暴露 |
| 候选harness编译 | exit0，实际include候选C源 | PASS |
| 候选25场景 | 25/25；runner exit0 | PASS，限OS替身C检查 |
| 候选独立.so构建 | exit0，无故障替身编译宏 | PASS |
| ELF/符号/依赖 | ELF64、DYN、AArch64；libc/加载器，无not found | PASS |

冻结源失败case完整列表：pages_0、pages_15、read_open_fail、read_parse_fail、read_negative、get_fail、set_fail、restore_fail、map_restore_fail、set_restore_fail。原始每case实际返回码、stdout/stderr和字段mismatch在frozen_faults.json，未截断或挑选。

候选的restore_fail/map_restore_fail/set_restore_fail是**预定fatal行为**：child exit1、有fatal restore诊断、无正常return/allocation marker，并按场景保留映射撤销证据；由原runner按这些标准判PASS，不能将所有子进程一律exit0当安全要求。

独立.so来自candidate/hbm_alloc.c直接编译，未包含harness替身。readelf -h/-Ws、ldd及源码/全部build产物SHA原样保留；没有运行policy_probe（该探针未编译）或LD_PRELOAD测试。

## 5. 能证明和不能证明的范围

harness的实际C代码已编译/执行，但mmap使用普通匿名虚拟内存，mempolicy/hugepage等OS边界由测试替身控制；成功路径仅触碰256KB小数据。没有真实hugetlb/HBM、共享页池调整、内核策略转换/恢复、驻留或整arena触页证明。

本轮没有模型、Torch/KML、HBM训练、放置策略或性能搜索，也没有接受全部allocator API/超大请求溢出/HBM_NODE范围/并发安全。独立库的可构建性和25场景通过不等于共享集成或真实HBM就绪。

## 6. 完整回传与后续边界

完整 **54文件**证据已回传，包括原样19文件payload、编译/运行包装、原始全部输出/逐步命令/退出、cpu receipt、25+25场景JSON、ELF/依赖和独立库二进制。zip及逐文件SHA/bytes/原始mtime_ns均核对；原始成员和C候选SHA未变，无失败重试。

本项结论为**限定Linux C场景及独立构建通过**，交S03及总协调审核。S02严格数值FAIL独立保留，不能由本项通过来替代或解锁训练内存/HBM。未经后续明确排期，不预加载本库或部署共享目录。

本地终检另观察到共享目录新建Git及5个快照/配置说明文件。108原始文件SHA未改；外部新增单独登记于evidence/workspace_git_additions_20261105.json，首次新增检测失败记录保留，S00未操作Git/暂存区。

## 7. 证据索引

绝对根：E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S00。

- evidence/s02_r5_s03_c_20261105/JOB_2034987_full_evidence.zip：完整54文件，SHA256 **891b4f80884537e4b536bf27724c40539653c93fcbf3efc97a591fe266964521**。
- evidence/s02_r5_s03_c_20261105/S03/received/job.log、djob_final.json、submission.json、pre_submit_checks.json、COLLECTION_S00.json：资源/终态/完整命令及远端原始时间和哈希。
- evidence/s02_r5_s03_c_20261105/S03/received/payload/linux_evidence/：compiler、glibc、uname、源码校验、冻结/候选编译日志、完整faults JSON/TXT、SUMMARY、steps、ELF/符号/ldd及built_sha256.json。
- evidence/s02_r5_s03_c_20261105/S03/received/payload/build/libhbm_alloc_s03.so及faults_frozen/faults_candidate：本次实际独立产物。
- evidence/s02_r5_s03_c_20261105/S03/review.json：本地完整性/原判据复核。
- evidence/s02_r5_s03_c_request_20261105.json、execution_packages/S03_SAFETY_C_VALIDATION.zip：授权与原样协调包。
- candidate/run_s03_c_job.py、run_s03_c_job.sh、s03_cpu36_contract_frozen.py：S00新增的有界干净执行层，实投版本及SHA在回传原件。
- candidate/audit_s02_r5_s03_c_delivery.py、collect_pair_evidence.py及ARTIFACT_SHA256.txt：独立复核和完整当前索引。
