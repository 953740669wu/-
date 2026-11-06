# 下一批精确提交：双域准备与未提交终态

批准范围：GIT_SUBMIT_DUAL_DDP_NO_RUN_20261106.tsv各行，加该TSV自身原字节（自引用例外）。除此之外不得扩大。按scope分批提交；TSV自身归COORDINATION，不能在自身内容中记录自己的SHA。最终交接消息提供其SHA；Git窗口执行前核对。

## 接受与暂缓

已接受归档：02冻结参考；07冻结候选及数值FAIL正式证据；01最终FAIL审核；00部署准备/拒绝未提交终态；08未运行摘要；协调任务卡/验收/交接/六份历史状态及本轮控制文件；Git上一轮结束状态；补漏审计原件。归档不表示候选集成或训练/性能接受。S00保存的原13项失败指标随本批归档，07原临时运行目录仍按作者archive_only排除。

S01诊断复核已经完成，结论ACCEPT_PARTIAL_DIAGNOSIS_NOT_TRAINING_ACCEPTANCE；支持分组收缩累计精度敏感性，但新DDP影响、实际worker/后代15秒内清理证据等未闭合。本批暂缓07和01两个numeric_diagnosis_r1完整目录，详见GIT_DUAL_DDP_BATCH_20261106/DIAGNOSIS_DISPOSITION.json和REMAINDER_DISPOSITION.json。01/07当前短状态纳入当前快照，不能据此把暂缓目录追加进来。当前不重跑诊断/训练，不新增集群作业。

历史处置：8条旧记录明确SUPERSEDED_OLD_SUMMARY_ORIGINAL_SHA_NOT_RETAINED，原SHA未保留，后续合并版本已提交；12条迁移记录有已提交的相同原字节。详见HISTORICAL_DISPOSITION.json。旧TSV原样保留，不补造、不把旧8行说成逐版本完整归档。历史余项逐路径明确归属、原因和下一动作；未重新核验的旧准备/S04/S05/S06等暂缓，重复副本/本机文件按原规则排除，全部保留本地。

## 唯一Git窗口执行要求

1. 先读本说明、TSV、处置台账及自己的短状态。核当前分支/HEAD、暂存区和远端。编表基线HEAD为cb342a1f3f9fc0b2bea66f342138f68acc2950e6；若已改变先核是否已归档，不重复提交。禁止git add .、git add -A、强制加入忽略项、切共享分支、reset/clean或强推。
2. 每行逐项核当前path/bytes/SHA256；状态文件也用本批新快照，不沿用作者旧索引中的状态SHA。任何差异停止对应scope并回报，不自行刷新批准清单。索引自身已纳入，禁止递归扩目录。
3. 每个scope只暂存清单中的精确路径，核暂存对象原始bytes/SHA和暂存范围后提交；若Git属性/换行转换改变原字节，先解决精确原字节问题并复核，不直接提交。空/失败日志按原字节保留。
4. 按scope形成可追溯提交，COORDINATION包含本TSV自身；提交说明明确preparation/numerical FAIL/no job，不称训练成功或性能提升。正常推送既有origin/main，核HEAD、origin/main与实时远端一致；不得更改remote或强推。
5. 提交后逐项验证Git对象bytes/SHA与本清单一致，确认范围无遗漏/额外文件。回传各scope commit、文件数、总验证数、本地commit与远端push结果；更新自己SESSION_STATUS/ROUND_DELTA并注明此次更新是清单冻结之后的下一批余项，不自动补交。
6. 余项按REMAINDER_DISPOSITION逐项核对；后来新增文件另记NEW_AFTER_SNAPSHOT，不能为了清空工作区加入。本批不包含ZIP、数据、权重、环境、known_hosts及作者明确排除的重复副本。

## 核验与文件

本批工具build_manifest.py只读取Git/作者文件并生成COORDINATION清单/台账，不运行作者测试或进行Git写操作。唯一Git窗口不得为忽略变化而自行重跑它生成新批准版本。
AUTHOR_IDENTITY_CHECKS.json记录冻结源核对和可变状态旧索引差异；冻结源任何漂移使编表失败。所有批准文件最终再核当前SHA。GIT_ARCHIVE_GAP_AUDIT_20261106为18:49历史审计快照，最新余项见本批REMAINDER_DISPOSITION，不能混用计数。
