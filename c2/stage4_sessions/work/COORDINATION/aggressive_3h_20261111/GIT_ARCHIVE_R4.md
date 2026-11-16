# 三小时长任务闭合归档 R4

仅归档已闭合目录 R4_HBM_POLICY 的本TSV精确路径，加TSV自身。结论见各目录DECISION.json或ADOPTION.json。

先完成GIT_ARCHIVE_R1.tsv的128对象批。此批的提交基点须为0d5f2887ef2ba2edc4e8ec350ca33fe6c0f18bc3的正常后代，并包含首批128对象且逐blob与首批清单相符；不得合并、改写或重复旧批。读取当前HEAD、index及实时远端后，按精确清单核路径/大小/SHA，任何漂移或无关暂存停止并回报。

包含源码差异、实际绑定、原生终态、完整数值与计时时序、HBM驻留和清理；完整传输包与未选取原件有COLLECTION_INDEX索引。未修改依赖按既有C1来源和源码SHA追溯。排除动态库、压缩包、原始数据、模型、环境文件与凭据、重复线程采样。活动作业、活动状态和未闭合候选继续暂缓，不整目录暂存。

仅唯一Git窗口按TSV普通提交推送main。核index及commit的每个blob，回传commit、父提交、对象/字节总数、遗漏/额外、实时origin/main和index状态。当前窗口独立复核后更新交接。
