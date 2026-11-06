# S08 今晚工程结果整理

状态：LOCAL_PREPARED。只读工具，不提交集群、不读 NPZ、不加载 checkpoint、不作正式质量或性能验收。真实输入以 S00 本轮 `RUN_COMPLETE.json` 指向的唯一收集目录为准；没有该交接时，仅有明确标注的 LOCAL_FIXTURE 示例。

接口锚：S02 `INTERFACE.json` SHA256 `8b1b540b8adeb4f4e49233c262b113c7c437f7a6e30b9f6d13113a96891dc669`。仅接受 `ENGINEERING_REAL_CORPUS_PILOT_V1` 的观察记录；旧正式门禁不改动。工具检查工程标记、manifest/interface 身份、完整逐步记录的一致性和帧/暴露清单的来源一致性。输入哈希保存在摘要内，供后续与 S01/S00 的绑定记录核对；工具本身不替代独立审核或认证远程来源。

## 用法

只使用已有 Python 标准库，建议 Python 3.9+。显式指定一个本轮证据根目录，不扫描历史、不自动发现其他 job。

S02 当前输出布局为 `payload/outputs/engineering_<job>/` 内的 `result.json`、`steps.jsonl`、`exit_code.txt` 和可能的 `runner_status.json`，暴露清单在 `payload/outputs/EXPOSURE_LEDGER.json`。因此将收集后的 `payload/outputs` 指为根目录、将唯一 `engineering_<job>` 指为运行子目录。若 S00 保留了更外层目录，传入对应的显式相对路径即可。

```powershell
python -B E:/eitfm_c2_stages2-4_2026-11-03/c2/stage4_sessions/work/S08/overnight_engineering_20261105/summarize.py --evidence-dir <本轮收集的payload/outputs绝对路径> --run-subdir engineering_<唯一job编号> --output-dir E:/eitfm_c2_stages2-4_2026-11-03/c2/stage4_sessions/work/S08/overnight_engineering_20261105/real_summary_<唯一job编号>
```

如果收集目录已将四个文件放在同一层，省略 `--run-subdir`。清单位置不同可用 `--ledger-relative-path <证据根内相对路径>` 明确指定。两类输入路径均必须留在显式证据根内。输出只能写本 S08 本轮目录，须与输入分离；已有输出不覆盖。缺输入仍生成缺项报告，证据路径错误不会自动换目录。

返回码 0 表示记录检查没有发现缺项，状态为 `ENGINEERING_OBSERVATIONS_RECORDED`；返回码 2 表示 `EVIDENCE_GAPS`。两者都不代表科学、性能或生产接受。`INCOMPLETE`、非零退出、损坏日志和来源不一致均保留；无法确认的暴露须保守排除复核。单位状态 `CONSUMED_CONFIRMED` 仅表示已有确认使用，不能推断该单位全部行均已训练。

## 轻量摘要格式

- `SUMMARY.md`：原运行状态/退出码、实际与计划更新数、逐步两项 loss/total、读取/训练/诊断时间、case/unit 的实际记录帧数、RSS/HWM 范围、整体时间字段、CPU/KML 和 checkpoint/零更新恢复的证据转述、所有缺项。
- `SUMMARY.json`：同一观察的机器可读形式，另保留输入 path/bytes/SHA、数据与代码身份、真实帧顺序、库路径/SHA、暴露清单及中断/恢复探针状态。CPU 检查点只保留摘要；完整线程快照应读已绑定哈希的原始 `result.json`。
- 耗时只对明确记录的数据给出范围/中位数；缺字段为 UNKNOWN/空值，并报告缺项。整体 wall 是入口进程的记录范围，不冒充调度节点秒；节点秒与清理终态须查 S00 调度/清理原件。
- RSS/HWM 为 process-lifetime。无完整计时范围不计算提速百分比；无 val/test 只整理训练工程观察，短程 loss 波动不触发调参。

## 本地验证与后续输入

运行 `python -B -m unittest discover -s E:/eitfm_c2_stages2-4_2026-11-03/c2/stage4_sessions/work/S08/overnight_engineering_20261105 -p test_summarize.py -v`。

8 个标准库夹具覆盖正常、缺字段、失败/缺步、manifest 漂移、重复帧、非有限数、损坏日志、暴露来源冲突与字段类型异常。`evidence/LOCAL_FIXTURE_normal/` 和 `evidence/LOCAL_FIXTURE_interrupted/` 是人工数据及 CLI 示例，不是真实训练；`evidence/LOCAL_CHECKS.json` 保存实际验证结果及输入前后哈希比对。

只读检查 S00 固定 `RUN_COMPLETE.json` 后才选择真实输入。若没有该文件，本轮交付工具并结束，后续会话按短状态继续；没有后台监视器或活动 S08 job。

精确待归档文件见 `ARCHIVE_FILES.txt`。其中只含本 S08 代码、说明、状态和小型本地夹具/检查证据；无真实语料、权重、环境或集群输出。未操作共享 Git 暂存、分支、提交或推送。
