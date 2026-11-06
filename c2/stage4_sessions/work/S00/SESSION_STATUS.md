# S00简短状态

- 更新/轮次：2026-11-06 Asia/Shanghai；OVERNIGHT_ENGINEERING_20261105完成，任务目录按夜间卡固定保留。
- 终态：唯一2043445/cn21341 SUCCEEDED/jobExitCode0；ENGINEERING_PILOT_COMPLETE_NOT_SCIENTIFIC_ACCEPTANCE，1epoch/25更新/1600真实帧完成，无重试、无活动S00 job。
- 放行/去重：S01完整PASS_FOR_ENGINEERING_PILOT绑定代码/源码清单/部署/descriptor/接口及资源；审核SHA=da7e84289a905466bc5bfdaa1e9cf7a1b80c41ace0cfaae63488d11ae8f6e408，提交前实际队列、原目录marker/所有SHA再核，一次dsub/原生交接完成；其它任务未操作。
- 数据：工程14300版manifest SHA=bdd146040bddf2ddd47fb9d571d5d2f40e5fa20fbd30d0c0d11239893e647032前后未变；seed2026确定s0285/s0593各8个16_adjacent单元，固定同belt/unit/row，正分母/finite/原数据SHA全过。旧正式REALDATA_SOURCE_AUDIT.json仍DATA_NOT_READY，不创建split/subject映射/val/test。
- 资源/模型：38授权/实际前36留2、DDR24576MB同limit/exclusive/HBM0、job900/全入口840/清理30/收尾30；完整Encoder37995777、fp32/CKPT0/KML/native SDPA及原mean双loss/AdamW，未开decoder/compile/bf16/微批或其它探针。
- 真实更新：25个batch各64，无填充/重复，frame索引恰好0..1599且源SHA/row/baseline一致；mask25个不同SHA，AdamW1..25连续，全部loss finite。首/末不同batch total15.21107/5.69206只是训练观察，不称效果验收。
- CPU/KML：59次完整线程快照无错误，最多36 TID且均在selected0..35；实际Torch intra36/interop608未加setter，非连续监控。训练KML3725/进程总3823调用，实际库身份原件保留。
- 耗时/RSS：应用wall86.6905秒，step总58.4772/中位2.32994秒；读取0.9140/批物化0.0223/可区分诊断6.8429/保存恢复4.0923/其余16.3418秒。逐步采样到的process-lifetime HWM最大7258705920bytes，非单步独占或job最终峰值。调度起止96节点秒、usage95秒分列；已知累计23job/1292节点秒。
- checkpoint：远端payload/outputs/engineering_2043445/checkpoints/final.pt，456135327bytes，SHA=ec491c46c06f94a7fac54d5f80010866311743e1f722947cb680cdaf3579e403；模型/AdamW/RNG/cursor/身份精确恢复，固定前向差0、extra_updates0；权重留远端未下载/续训。
- 暴露/清理：initial与runtime清单分开，25 confirmed_updates与steps帧完全一致，16单元均CONSUMED_CONFIRMED、in_flight=null；必须待真实subject映射后追溯排除最终test，当前不保证未知test未暴露。所有所属后代自然退出，remaining_live/processes空、all_reaped=true、调度PID清空；本次未现场触发TERM/KILL分支。
- 证据/交接：overnight_engineering_20261105/{RUN_COMPLETE.json,RUN_AUDIT.json,RUN_REPORT.md,EXPOSURE_LEDGER.json}；evidence/JOB_2043445_evidence.zip，543118bytes/102文件，SHA=53feb1041cc17472d8ec6777ec8ec64e2d8fd4a286a518be42f2d49298e82b00。归档bytes/SHA/原mtime索引全过，missing=[]/source_status=UNCHANGED；RUN_COMPLETE绑定received目录/索引SHA供08直接读取。
- 下一步/边界：交S01/08只读工程复核/整理；无待执行job，不自动续训/扩样/重提05/07。正式划分和科学/性能接受仍未建立；旧包/失败/正式门禁均保留。精确待归档名单ARCHIVE_FILES.txt，未操作共享Git暂存/提交推送，数据权重不入Git。
