# 精确Git交接：有限诊断与只读收尾

本批范围仅GIT_SUBMIT_DIAG_CLOSEOUT_20261106.tsv逐项path/bytes/SHA，加该TSV自身（自引用例外），不得扩目录。
基线HEAD f84281cb27be72fd9a4b8fb7ddb7654a338be1f5，已验收268批次及旧TSV保持原样。本批是新提交，不能amend旧批。

接受理由：01 EVIDENCE_CLOSEOUT_REVIEW给ACCEPT_ARCHIVE_WITH_PRESERVED_LIMITATIONS，review_complete=true、execution_authorized=false；历史证明补齐0，5 SUPPORTED/4 UNSUPPORTED/6 NOT_RECORDED仅描述证据范围，实际compute/后代15秒清理仍UNKNOWN。只归档保留限制的诊断，不称数值/清理实测PASS、训练成功或执行许可。

范围含：原55份暂缓诊断文件、01/07本次只读收尾作者清单及索引自身、当前两窗口状态、Git上批结束状态、协调268验收/只读收尾卡/新02静态提案卡/状态交接和本批控制文件。原55条由DEFER_UNCLOSED_DIAGNOSIS转为RELEASED_FOR_LIMITED_ARCHIVE_NEW_BATCH，见GIT_DIAG_CLOSEOUT_BATCH_20261106/DEFERRED_55_RELEASE.json；历史524待核和422明确排除继续保持，不重新加入。

执行要求：
1. 唯一Git窗口先核自身状态、分支/HEAD/暂存及是否本批已经提交；变化须先续接核对，不能重复提交。核每行当前bytes/SHA与TSV身份，任何漂移停止对应scope回报，不重跑freeze.py或自行刷新批准清单。
2. 仅精确路径暂存，按scope提交；TSV自身归COORDINATION。核暂存和已提交对象原始bytes/SHA及准确范围，不允许换行转换改变原字节。旧失败和明确UNKNOWN原样保留。
3. 不git add .、不git add -A、不递归扩目录、不强制加入忽略项，不切共享分支/reset/clean/强推；普通推送既有origin/main并核实时远端、本地HEAD、origin/main一致。
4. 提交后逐项核范围与原字节，回传各scope commit/数量、总核验数、推送和远端结果；自身结束状态的新改动记下一批余项，不自动追加提交。
5. 按前批余项台账移除本批批准归档的55条；524历史待核/422明确排除仍逐项保留，冻结后新增材料记NEW_AFTER_SNAPSHOT，不为清空工作区追加。02新的提案工作可以并行，其目录不在本批范围。
6. 无数据/权重/原始.pt张量/ZIP/环境入库。只读归档不执行作者脚本、模型、测试、DDP或集群作业。

总协调仅核已存在文件及生成清单，未进行Git写操作。冻结后所有状态变化需另行清单，不静默替换当前批准SHA。
