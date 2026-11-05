# S03 第一轮：HBM 分配器两类安全边界

日期：2026-11-05（Asia/Shanghai）  
状态：**READY_FOR_REVIEW / LOCAL_ONLY / LINUX_C_NOT_RUN / REAL_HBM_NOT_RUN**

## 1. 结论

已完成独立候选、冻结副本、最小 diff、先失败后修复的本地检查，以及 Linux/glibc 构建和故障注入入口。候选只修改 `init()`：**增加 15 行、删除 5 行**，初始化函数之外的源代码不变。建议交总协调审查后由 S00 安排 Linux 验证，当前不建议直接集成共享库。

低于预留 16 页时先将可用容量归零，再作无符号计算；页数读取失败关闭 arena。保存/设置线程内存策略失败时不进行不安全的 mmap；恢复原策略成功后才允许继续。**恢复失败则清理已经成功的映射、输出 fatal 诊断并 `_exit(EXIT_FAILURE)`，不带着无法保证的策略继续模型。** 保留原来的 16 页预留、HBM_MB 上限逻辑、默认 3800 MB、64 MB 启用下限、分配接口及 DDR 路径。

本地 6 项算术复现/源码静态检查：冻结源 **5 项失败、1 项通过**，候选 **6 项通过**。这些不是 C 执行或 Linux 故障注入通过。25 个直接包含实际 C 实现的 Linux 故障场景已准备，**尚未编译/运行**。未生成 `.so`，未连接集群、未提交作业、未开展训练或性能搜索，也未证明本次问题是历史 SIGBUS 的实际根因。

## 2. 前置条件与执行范围

已完整读取本轮启动说明、COORDINATION/STATUS.md、sessions/README.md、S03_HBM.md、REPORT_TEMPLATE.md、S01/HBM_HANDOFF.md，以及 S00/REPORT.md；另核对原始 C2 报告中 HBM 历史记录。当前以 2026-11-05 安全任务说明为范围依据；S03 原任务卡中的放置策略和性能实验继续等待 S02。

本任务根目录：`E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S03`。

| 来源/候选 | 绝对路径 | SHA256 |
|---|---|---|
| S00 冻结来源，只读 | E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S00\baseline\c2\opt\hbm_alloc.c | edbf06f54a779271c97d739e4aaca18ffae306ccd20713443ecaee11c388cb15 |
| 共享源码，只读，终检仍相同 | E:\eitfm_c2_stages2-4_2026-11-03\c2\opt\hbm_alloc.c | edbf06f54a779271c97d739e4aaca18ffae306ccd20713443ecaee11c388cb15 |
| S03 逐字节冻结副本 | E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S03\frozen\hbm_alloc.c | edbf06f54a779271c97d739e4aaca18ffae306ccd20713443ecaee11c388cb15 |
| S03 候选 | E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S03\candidate\hbm_alloc.c | 8ec586c60c97bbcdb437fe848b6d9645ea3cfca850952ff9d94c0d36fdaed35d |

最小 diff：`E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S03\candidate\hbm_alloc.diff`。已核对其与两份源文本完全对应。

开始时 S03 目录不存在，本轮全部写入都在 S03 内。未写共享库、模型、冻结数据、S00/S01/S02 或协调文件。上述两个外部 allocator 来源在收尾时重新计算 SHA，保持不变；未对整个项目或其他任务正在变化的产物作全量身份声明。无 Git 仓库，不使用提交或 worktree。

## 3. 环境、复现方式与成本

本地为 Windows AMD64、Python 3.11.9，`size_t` 为 64 位。PATH 和检查过的既有工具目录未找到可用 C 编译器；WSL 未安装，没有可用 Linux/glibc/NUMA 构建环境。未安装新环境，未尝试在 Windows 加载 Linux `.so`。

Git Bash 存在，但两次只读 `bash -n` 尝试均在启动时失败，退出值 3221225794，错误为 `NtCreateDirectoryObject ... 0xC0000022`。因此 Bash 语法验证也标为未完成；这不是命令已运行的证据。原始错误见 evidence/bash_syntax_attempt.json。

本地复现命令（第一个命令预期退出 1，第二个预期退出 0）：

```powershell
python -B 'E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S03\tests\check_local.py' 'E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S03\frozen\hbm_alloc.c' --json 'E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S03\evidence\before_local.json'
python -B 'E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S03\tests\check_local.py' 'E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S03\candidate\hbm_alloc.c' --json 'E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S03\evidence\after_local.json'
```

完整 Linux 命令在 `E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S03\LINUX_VALIDATION.md`。其流程为：校验交付 SHA → 同一故障检查分别编译冻结源和候选 → 原源应暴露指定失败、候选应 25/25 通过 → 独立构建 `build/libhbm_alloc_s03.so` → 记录编译器、参数、ELF/依赖及实际二进制 SHA → 实际 preload/线程策略/数据小检查。构建目标只在 S03 的独立 build 目录，不覆盖共享 `sw/hbm_alloc`。

实际编译器/`.so` 参数/二进制 SHA：**未生成，不能填写实测值**。预定库参数为 `-std=gnu11 -O2 -fPIC -shared -pthread -Wall -Wextra`，不是本地编译成功的声明。全部 C 构建与真实 HBM 命令均待 S00 核包后执行；本文档不提交作业。

模型、输入、初始权重、精度、microbatch、有效全局批量、预热及计时轮数：本轮均不适用。新增集群作业 0，节点小时/GPU 小时 0；无作业 ID 或集群执行起止时间。

## 4. 正确性和失败策略

先建立 BEHAVIOR.md、C 故障检查和本地检查，保存冻结源失败日志，再复制并修改候选。本地日志原样保留。

原表达式在 64 位无符号语义下，`nfree=0/15` 时比较用的 MB 值分别为 **18446744073709551584 / 18446744073709551614**，均大于默认 3800，原容量限制因而被绕过。这是算术复现，未证明某次实际 Linux mmap 或后续缺页的结果。

| 检查 | 预定结果 | 本轮证据/状态 |
|---|---|---|
| 原有负数转 size_t 的容量条件 | 不能继续保留该条件 | 原源静态失败、候选通过；算术复现已运行 |
| 页数无法读取 | 在策略调用前关闭 arena | 原源静态失败、候选通过 |
| get_mempolicy 失败 | 不尝试临时绑定或 mmap | 原源静态失败、候选通过 |
| 临时 set_mempolicy 失败 | 不 mmap；恢复确认成功后 DDR | 原源静态失败、候选通过 |
| 恢复失败 | 不 mbind/发布 arena；清理成功映射并退出 | 原源静态失败、候选通过 |
| init 外分配接口/逻辑 | 与冻结源文本相同 | 原源、候选均通过；另核对前缀/后缀 |
| C 故障注入 25 场景 | 逐个检查退出、策略参数/顺序、arena 和数据路径 | 已编写，Linux C 未运行 |
| 真实 preload、真实内核线程策略和数据 | 前后策略相同、对齐/读写正确 | policy_probe.c 已编写，未运行 |
| loss/梯度/optimizer/state_dict/科学数值 | 本轮不改模型，不作数值等价声明 | 不适用，S02 独立负责 |

Linux 25 场景包括：无 HBM_NODE；页数 0/15/16/17/47/48/49/2020；HBM_MB=63/64/9000；打开失败、解析失败、负页数；get 失败、临时 set 失败、mmap 失败、mbind 失败；三种恢复失败组合；原策略 DEFAULT/BIND/PREFERRED/LOCAL。后三类致命组合期望退出 1，普通场景期望退出 0 且数据分配正常。完整期望值在 tests/run_faults.py，实现在 tests/fault_harness.c。

行为细节和取舍：

- 0..16 页可用容量为 0；17 页剩 2 MB，但仍低于原有 64 MB 门槛，因此也关闭。48/49 页分别允许 64/66 MB。2020 页默认请求仍为 3800 MB，HBM_MB=9000 仍被限制为 4008 MB。
- 读取失败原来会跳过容量限制，现在保守关闭。get 失败时没有有效原策略快照，所以直接回退，不继续预留。
- 临时 set 失败也进入统一恢复路径；恢复成功才回退 DDR。代价是这种失败分支多一次恢复调用；若这次恢复也失败，即使原策略可能尚未改变，仍选择退出，不宣称它安全。
- mmap 成功和失败都先恢复；在恢复前保存 mmap/set 的 errno，避免恢复调用覆盖原始诊断。mbind 仍在恢复之后，失败时沿用原来的 unmap/DDR 分支。
- 恢复失败并不能被代码“保证恢复成功”；本候选提供的是明确失败退出。使用 `_exit` 避免在不可信策略下继续模型或执行退出回调。清理失败也不会使程序恢复执行。

C harness 直接 `#include` 原源/候选，而非另写一份 allocator。它替换页数 I/O、策略 syscall、hugetlb mmap，使用普通匿名映射和真实 glibc DDR 分配；检查完整保存掩码和模式、临时绑定是否先于映射、恢复是否先于 mbind/发布，以及退出路径。替身检查即使将来通过，也不证明真实内核策略恢复、HBM 驻留、整 arena 触页或并发安全。本轮对这些 C 场景一个也未执行。

## 5. 性能与内存

无性能或训练内存结果。没有同主机 A/B、吞吐、DDR/HBM 峰值、带宽、科学数值或整步加速结论。累计分配次数/字节、bump 高水位不是对象热度或实际驻留高水位。本轮不调整阈值、大小类或放置策略。

## 6. 接受条件、待验证项目与 S02 最少后续数据

本轮候选和交付物可审查，**真实 Linux/HBM 安全验收未通过或未运行，不能据此替换共享库**。S00 在核对具体 SHA 包后统一安排：

1. Linux/glibc 同一 harness 的冻结源缺陷暴露和候选 25/25 检查；保留全部原始输出，排除编译/基础设施错误冒充预期失败。
2. 独立 `.so` 实编译、符号/架构/依赖、实际加载路径和源码/库 SHA 对应；当前二进制不存在。
3. 真实调用线程策略前后核验，覆盖节点允许集、原策略/掩码、设置拒绝、恢复失败退出；替身 syscall 不代替此证据。
4. 实际 2 MB hugetlb 池的低容量和读取失败回退、预留竞争、驻留核查、受控 arena 触页/无 SIGBUS。不能改动共享池制造故障，不能只看 mmap 成功或进程退出后页数。
5. 更完整的 allocator API、超大请求、对齐/realloc/free、耗尽和并发测试仍未完成；本轮通过也不等于全面安全或性能接受。

范围外的具体源码线索仅记录，不在本轮修复：候选第 58 行 `mask[node / 64]` 仍未校验 HBM_NODE 的数组范围；第 92 行 `n + HDR + GRAIN - 1` 对超大请求的溢出边界仍需独立测试。二者是源码风险线索，未执行故障测试，不能描述成已确认历史故障。

S02 不需中断正在准备的 36 核数值对照。待其数值门槛和独立内存入口接受后，后续放置策略只需提供：

- 已接受配置和代码/输入身份：每个 16/32 电极 pre/dec 的有效批量、microbatch、累积、精度、checkpoint 开关、实际线程/CPU 边界。
- 固定训练阶段/步边界内实际同时存活的缓冲峰值、生命周期和释放/复用证据，区分模型/梯度/optimizer/激活/临时工作区，给出测量方法。
- 可定位的重复缓冲/重复访问证据及关联身份；只记录累计分配大小或次数不足以判断热度。HBM 指标需与 DDR 分开，不能用 RSS 代替 hugetlb 占用。

无共享改动需要回滚。候选不被接受时保留此独立包即可；若 S00 做后续独立 preload 小检查，结束后移除该独立加载配置，不触碰共享部署。

## 7. 证据索引

全部交付物 SHA256 见 `E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S03\ARTIFACT_SHA256.txt`，清单自身不作循环哈希；源码身份另见 SOURCE_SHA256.txt。

| 产物 | 绝对路径 |
|---|---|
| 修复前行为约定 | E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S03\BEHAVIOR.md |
| 最小 diff | E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S03\candidate\hbm_alloc.diff |
| 本地算术/静态检查 | E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S03\tests\check_local.py |
| 修复前日志/机器结果 | E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S03\evidence\before_local.txt；同目录 before_local.json |
| 修复后日志/机器结果 | E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S03\evidence\after_local.txt；同目录 after_local.json |
| C 实现故障注入入口，未运行 | E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S03\tests\fault_harness.c |
| 25 场景及断言，未运行 | E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S03\tests\run_faults.py |
| 真实策略/数据 probe，未运行 | E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S03\tests\policy_probe.c |
| Linux 构建、验证、记录 SHA 命令 | E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S03\LINUX_VALIDATION.md |
| 身份/范围/diff 终检 | E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S03\evidence\delivery_validation.json |
| 环境和 Bash 启动失败证据 | E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S03\evidence\environment.json；同目录 bash_syntax_attempt.json |

状态文件未更新，未向其他聊天发送消息；本报告供用户交回总协调审查。
