# 交 S03 的 allocator 静态疑点

当前协调边界明确分配器源码修改归 S03。本 S01 不修改、编译或加载 allocator；S00 旧审查中建议 S01 检查低页数的分工，以当前协调说明为准。

冻结文件：`E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\S00\baseline\c2\opt\hbm_alloc.c`。

SHA256：`edbf06f54a779271c97d739e4aaca18ffae306ccd20713443ecaee11c388cb15`。

第 51 行：

```c
if (nfree >= 0 && (size_t)(nfree - 16) * 2 < mb) mb = nfree > 16 ? (nfree - 16) * 2 : 0;
```

在 `nfree=0..15` 时，无符号转换会把负值变为大数，可能绕过 arena cap。第 57–61 行还涉及 get/set mempolicy 与恢复，部分 syscall 返回值未检查。以上是源码静态疑点；没有编译或故障注入，不是已证实的历史 SIGBUS 根因。

建议 S03 先冻结目标平台与实现前断言，覆盖 nfree=0/15/16/17、读取失败、get/set/restore policy 失败及 mmap/mbind 失败，确保失败时保留可解释的 DDR fallback/退出，未触达的 hugepage 不能被当作实际 HBM 驻留。再按独立库路径构建与核查 SHA256。

S01 已提供非零退出传播、barrier 内部超时及进程监督候选；这些能终止失败运行，不能修复 allocator 或证明 CKPT+HBM 数值/稳定性。
