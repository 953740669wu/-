# S03 Round 2：节点、大小溢出与必要 API 边界

日期：2026-11-05（Asia/Shanghai）  
状态：**READY_FOR_REVIEW / LOCAL_DELIVERY_CHECKS_PASS / NEW_LINUX_C_NOT_RUN / REAL_HBM_NOT_RUN**

## 本轮结论

新候选增加 14 行、删除 3 行，修正节点解析、两处大小单位换算、请求舍入、arena 容量判断和 posix_memalign 对齐入口。原策略恢复、free/realloc、精确尺寸复用、默认阈值和 16 页预留保持不变。先写直接包含实际 C 实现的新增检查和行为约定，保存其 SHA，再复制/修改候选。

**本地已运行 7 项交付完整性检查并通过；新增 50 个 C 场景尚未编译或执行。** 旧候选的 21 个预期失败、29 个控制通过是待验证判据，不能写成已观察结果。未生成新 `.so`，不建议在 Linux 验证前集成。没有运行真实 HBM、训练、性能或集群作业。

本轮根目录：`E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S03\round2_api_bounds_20261105`。下文路径均相对此独立目录。

## 来源与既有证据

按 HANDOFF_PROTOCOL 读取自己的 SESSION_STATUS/ROUND_DELTA、总状态表和本轮协调文件 S03 章节；按需读取 S00/S03_C_SAFETY_REPORT.md、实际候选/旧 harness、原始 candidate_faults.json 和 frozen_faults.json。未重读完整历史或重跑旧 25 场景。

只读重算 S00 job2034987 原始结果：生产冻结源 15/25 通过、10 个指定失败，上轮候选 25/25 通过；三个恢复失败场景按原判据退出 1、无正常返回标记。回传候选与本地旧候选 SHA 相同；重新计算回传旧库 SHA 为 bb0af32c6f34e3fa877dfc35655c2a64a65bf120e3fdcac3a900a0e7299e5643，与旧证据一致，未加载它。

该接受仅限 OS 替身下的实际 C 检查和独立构建，不证明真实策略恢复、HBM 驻留、整 arena 触页、并发或模型正确性。原始文件身份、计数与来源绝对路径保存在 evidence/previous_acceptance_review.json。这是证据审阅，不是本轮新执行。

| 源文件 | SHA256 |
|---|---|
| 上轮候选 / 本轮 frozen/hbm_alloc.c | 8ec586c60c97bbcdb437fe848b6d9645ea3cfca850952ff9d94c0d36fdaed35d |
| 本轮 candidate/hbm_alloc.c | d1f5dbbfb6aa4a973dcc4d12607f62a8b2be5166690897dfd5ea35e067c7d7a2 |

旧候选、旧报告/测试/索引等 19 个文件在本轮开始和收尾逐项校验 SHA，不变。只新增本 round，并更新获授权的 S03/SESSION_STATUS.md、S03/ROUND_DELTA.md。没有改旧 REPORT/清单、共享源码/库、模型、数据、其他任务、协调文件或 Git/暂存区。

## 最小修改和取舍

- HBM_NODE 使用 strtol 完整解析十进制，拒绝转换失败/溢出、尾随字符、负值和 >=128，再转换为 int 和形成掩码。0–127 是现有两 word 掩码和 maxnode=128 的能力范围，不表示机器真实有 128 个 NUMA 节点。保留 strtol 的前导空白和正号，拒绝尾随空白。非法值在页数 I/O 和策略调用前关闭 arena，继续原 DDR 路径。
- HBM_MIN_KB 左移前检查 SIZE_MAX>>10；HBM_MB 先作原页数 cap，再检查 SIZE_MAX>>20。极大 MB 请求能安全 cap 至 64 MB 时仍正常使用；缩减后仍无法表示则关闭 arena。本轮不另改其他环境变量的解析语法。目标 LP64 下，非负 long 页数减预留再乘 2 在 size_t 中可表示，不无故重写已有页数计算。
- 请求在 header/grain 加法前检查可表示上限，溢出时只跳过 HBM，继续原 DDR 分配/ENOMEM，不缩小请求。容量判断改为先比较舍入大小和剩余字节，容得下后才形成推进后的指针，避免先计算越界/回绕的 bump+sz。
- posix_memalign 在初始化前验证对齐是 >=sizeof(void*) 的二次幂；非法时 EINVAL，*out 不变。合法 <=64 对齐保留 HBM，较大对齐保留 DDR。DDR 失败仍返回 ENOMEM、*out 不变。
- free/realloc 实现不变，仅补数据保留、复用、失败和 DDR 转发检查。realloc(p,0)、非法指针、double-free 未纳入本轮接口接受，不追加新的零大小行为约定。

最小 diff：candidate/hbm_alloc.diff；行为约定：BEHAVIOR.md。两者和冻结源均随包交付。

## 新增实际 C 检查：50 个，未运行

tests/bounds_harness.c 直接 include 实际候选 C；编译宏切换到本轮 frozen 即可使用同一检查验证旧候选。tests/cases.py 的预定判据在修改前固定，不重复旧 25 场景。

| 组别 | 数量 | 主要覆盖 | 旧候选预期失败 |
|---|---:|---|---:|
| 节点 | 15 | 8 种非法值；0/16/63/64/127、正号、前导空白 | 8 |
| MB/KB 换算 | 5 | 左移临界合法/首个溢出值；极大 MB 安全 cap | 2 |
| 请求/arena | 10 | 舍入上限、指针回绕、API ENOMEM、尾部恰好/不足、grain 前/等/后 | 5 |
| 对齐 | 12 | 0/1/3/4/24/48 拒绝；8/16/32/64/128/4096 对齐及 HBM/DDR | 6 |
| free/realloc/DDR | 8 | NULL、耗尽后复用、grow/shrink、失败保留旧对象、DDR 转发/失败/回退 | 0 |
| 合计 | **50** | 新候选预期 50/50，无 sanitizer 错误 | **21** |

预期失败必须是退出 1 且有 CHECK_FAIL；仅 sum_last_safe/pointer_wrap 另允许对应退出 1 的 UBSan runtime error。信号、超时、编译/基础设施失败不计为缺陷暴露，29 个控制仍须通过。runner 区分实际用例通过与预期缺陷审核通过，保存每个 stdout/stderr/退出和源码/可执行文件 SHA。

替身控制页数 I/O、NUMA syscall、hugetlb mmap 和指定分配失败；普通 DDR 分配、复制、释放使用 glibc。非法节点让旧版停在 I/O 替身，检查不应发生的 I/O，不故意执行越界 stack 写。正常最多 64 MB 普通匿名虚拟映射，极大长度在替身中直接失败。测试符号改名，不 interpose sanitizer 自身分配。即使后续通过也不能当作真实内核/HBM/并发证明。

## 本地验证增量与复现

Windows AMD64、Python 3.11.9，当前 PATH 未找到 cc/gcc/clang/tcc/zig，没有可用 Linux/glibc C 环境。本轮未安装环境、未再次尝试已知无法启动的 Bash、未运行 C 或 `.so`。

实际 7 项交付校验：冻结身份；diff 对应；free/realloc/复用和策略清理代码不变；先写检查/约定 SHA 不变；50 场景及 21/29 判据清单；Python 语法；旧 19 文件未变。它们不检查 C 运行行为，也不以源码匹配冒充 C 执行。

```powershell
python -B 'E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S03\round2_api_bounds_20261105\tests\verify_delivery.py' --check-previous --json 'E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S03\round2_api_bounds_20261105\evidence\local_validation.json'
```

Linux 完整命令：`E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S03\round2_api_bounds_20261105\LINUX_COMMANDS.md`。S00 核包后在独立目录/已约定 36 核边界内执行，命令自身不提交作业，也不 preload 库或模型。

预定 harness 参数：`-std=gnu11 -O1 -g -Wall -Wextra -pthread -fsanitize=undefined -fno-sanitize-recover=all`。预定库参数：`-std=gnu11 -O2 -fPIC -shared -pthread -Wall -Wextra`，目标为独立 build/libhbm_alloc_s03_round2.so。命令记录真实编译器、参数、退出、ELF/符号/依赖、源码/库 SHA；**本轮未执行，新二进制 SHA 不存在**。

## 待验证和下一步

1. 总协调核包后由 S00 运行新检查：旧候选 21 个指定失败/29 个控制，新候选 50/50；结果不符先保存证据定位，不改判据求通过。
2. 新 `.so` 实际编译与身份核验。没有此证据前不集成共享库；旧库 SHA 不作新库证据。
3. 真实内核策略/驻留、并发、多线程统计、完整桶表耗尽和完整 allocator API 仍未验收。S02 数值/内存前置不由本轮接受。
4. 不启动真实 HBM、共享页池调整、模型 preload、热度/策略或训练性能搜索。新增作业和节点/GPU 小时均为 0，无活动进程/job 或未完成工具操作。

## 证据清单

以下均在上述本轮绝对目录内，全部文件 SHA 见 ARTIFACT_SHA256.txt（自身不循环哈希），源码另见 SOURCE_SHA256.txt。

- candidate/hbm_alloc.c、candidate/hbm_alloc.diff、frozen/hbm_alloc.c。
- tests/bounds_harness.c、tests/cases.py、tests/run_cases.py、tests/verify_delivery.py。
- BEHAVIOR.md、LINUX_COMMANDS.md。
- evidence/tests_before_candidate.json：候选复制/修改前固定的 C 检查、runner、清单及约定 SHA；C 未运行。
- evidence/local_validation.json：7 项本轮实际交付检查；evidence/environment.json：工具环境/未运行项。
- evidence/previous_acceptance_review.json：只读核验旧原始证据的身份/计数；evidence/protected_previous_files.json：旧 19 文件 SHA。

交接入口为 S03/SESSION_STATUS.md、S03/ROUND_DELTA.md，均已记录本轮结果、阻塞和下一条动作。
