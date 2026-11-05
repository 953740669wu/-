# 首次 Git 快照审查

日期：2026-11-05（Asia/Shanghai）。范围冻结：2026-11-05T03:57:33.445650+00:00。

## 快照含义

仅记录当前本地工作区，包含未接受候选、历史失败及未运行项目；不表示阶段四优化全部验收，也不改变原报告、哈希或正式入口。已读取阶段四 README 与协调 STATUS.md；项目及 E:\ 均无 AGENTS.md，也未发现原仓库、上级仓库或嵌套仓库。新建 main，未设置远端。

## 范围与字节检查

原始盘点 23843 个文件，共 2008372786 字节。冻结入库 2651 个文件，共 16786746 字节，另外纳入本说明和 GIT_SNAPSHOT_FILES.tsv；清单不包含自身及本说明以避免自引用。

入库文件及原始字节 SHA256 逐项见 GIT_SNAPSHOT_FILES.tsv。现有入库文件与初始化后首次只读盘点的 SHA256 一致；另核验原有 2652 份代码、报告及文本证据，均无内容变化。提交前后另核对 Git 对象与工作区原始字节。原始代码、报告、任务产物仅作读取，没有格式化或换行转换。新增文件只有 .gitignore、.gitattributes、GIT_USAGE.md、本审查和逐文件清单；仓库本地 core.autocrlf=false，没有改全局配置。

保留 JSON、7 份运行 .env、候选、测试、报告、文本日志和哈希清单；最大现有入库文件约 1.51 MiB，为线程采样 JSONL。认证材料扫描只记录规则、路径及行号，不输出匹配内容；未发现明文认证材料。认证参考资料保守排除。

## 未入库项目

共排除 21196 个原有文件，1991594077 字节，留在原位置，不删除。按 .gitignore 规则统计：

| 规则 | 文件数 |
|---|---:|
| `.venv/` | 20794 |
| `tmp/` | 245 |
| `download_cache/` | 60 |
| `c2/stage4_sessions/work/S01/revisions/R7_STARTUP_AUDIT_2034247_20261105/replay_received/` | 54 |
| `*.zip` | 22 |
| `c2/stage4_sessions/work/S00/evidence/vpn_manual_*` | 5 |
| `*.marker` | 4 |
| `patch_check/` | 4 |
| `diff_check/` | 3 |
| `patch_check_r2/` | 2 |
| `*.whl` | 1 |
| `*.pid` | 1 |
| `*.pt` | 1 |

主要项目：S02 round2 的 .venv/ 与 download_cache/；S02 round3 的 case/fixed_16_pre.pt（271979513 字节）；S00 runtime/wheels/ 依赖轮子；各任务 ZIP 运行/部署包；S00 tmp/ 重放与依赖；S01 replay_received/ 和 patch_check/diff_check 生成副本；进程/一次执行标记；VPN 认证参考资料。相关报告、case 清单和包哈希仍入库，依赖这些外部文件的实验需另按原说明恢复文件并校验。

冻结时未发现正在更新的拟入库文件，活动文件遗漏为零。后续窗口新建或修改的文件属于冻结后的工作区变化，应另行审查提交，不覆盖工作区。

暂存后发现 S00 正在回传新结果：`c2/stage4_sessions/work/S00/evidence/s02_r5_s03_c_20261105/`。该目录在冻结后新增，整体留待后续提交，不加入此次快照，也不将新结果解释为本次验收结论。目录内 `received/payload/build/` 的无扩展名 ELF 可执行文件属于生成二进制，按新增的 `build/` 规则忽略；其余源码、报告和 JSON 保持可见，以便后续独立审查。

收到用户提交身份后复查，冻结后的未暂存文件共 96 个：上述回传目录内 93 个，另有以下 3 个新增文件，一并留待后续独立提交：

- `c2/stage4_sessions/work/S00/S02_R5_C2_STRICT_REPORT.md`
- `c2/stage4_sessions/work/S00/S03_C_SAFETY_REPORT.md`
- `c2/stage4_sessions/work/S00/candidate/audit_s02_r5_s03_c_delivery.py`

已冻结的暂存文件未被其他窗口修改；快照仍以原冻结清单为准，不追随其他窗口后续产物滚动扩大范围。

## 共享目录操作约定

本轮仅当前聊天操作暂存区和提交；不切换任务分支，不 reset/clean/覆盖工作区，不创建或迁移 worktree。后续按 GIT_USAGE.md 指定单一 Git 操作者，逐个明确路径暂存，检查暂存差异和认证材料再提交。首次提交姓名/邮箱需由用户提供，不虚构身份。
