# Git窗口：首次真实工程训练归档

日期：2026-11-06；仅唯一Git窗口操作暂存/提交/推送。此处是精确范围交接，不是已提交记录。

## 本轮目标

归档首次真实工程job2043445的已核入口、固定工程样本描述、部署、前置审核、运行原件及协调记录。当前HEAD起点0e6e4c8923587d364a97fa2904d06ffd3de18fed；提交前仍核实际HEAD/分支/origin/暂存，若有并发Git操作先报告，不覆盖他人暂存。

## 精确范围与边界

- 唯一选择清单：同目录GIT_SUBMIT_ENGINEERING_JOB2043445_20261106.tsv，列为scope、path（仓库相对路径）、bytes、sha256；共256行文件，自身不可能自哈希，另把TSV原字节作为归档文件提交。因此本批总257文件，未计Git窗口自己新写的结束交接。
- 范围计数：COORDINATION=14; S00=161; S01=30; S02=51；TSV自身随COORDINATION批提交。
- 00：按其冻结ARCHIVE_FILES列明的源/描述/部署和完整文本/JSON/日志原件及结束状态；不含ZIP、真实NPZ、远端checkpoint。
- 01：前置审核源码/报告/绑定/必要检查，ARCHIVE_FILES.json自身补入；只代表前置技术审核。
- 02：冻结overnight_engineering_20261105目录交付与归档索引；排除共享SESSION_STATUS/ROUND_DELTA、所有新剖析目录，以及原清单列出的ZIP包。SHA/源码索引保留。
- COORDINATION：本轮任务卡、独立运行核对、当前状态及两个明确历史状态快照、归档检查/本说明；不用整个协调目录递归add。
- 08整个任务本批暂缓，包括旧工具/共享状态/正在生成的真实摘要；新一轮02/08另批。旧47项与04/05/06/07待办不混入；不以清空工作区为目标。
- 不强制加入任何被忽略的文件，不下载权重；JSON中的远端数据/权重路径和SHA属于元数据，不代表数据入库。

## 完成标准及执行方式

1. 逐项校验TSV所有文件的bytes/SHA及实际Git忽略规则；清单中任一文件变动/缺失先停对应批并报具体路径，不自动重写清单或扩大路径。已在HEAD完全同字节的文件报告为已存在，不能制造空提交。TSV自身记录本次读到的SHA，在提交后核Git对象字节。
2. 按明确scope分批提交：建议S00 `archive: preserve first real-corpus engineering training evidence`；S01 `archive: record engineering pilot preflight review`；S02 `feat: add isolated real-corpus engineering pilot entry`；协调 `docs: record first engineering pilot outcome and follow-up`。原始字节保留，勿重写LF/CRLF或会写证据的作者审计入口。
3. 每批暂存后核暂存路径集合等于该批明确清单，未发生漂移，再提交；所有批结束逐项核Git对象原始字节与清单完全一致。不得git add .、add整个work目录、checkout/reset/clean或修改作者正在写的文件。
4. 沿用已授权GitHub origin/main普通push；不改远端、不强推。多行提交说明用临时body文件；身份/网络问题按实际报错保留本地提交，不能声称已推送。
5. 推送后实时核远端main、本地HEAD/origin追踪一致，报告各提交hash/范围/推送结果、遗漏/漂移以及未提交范围；更新Git自己的短状态/六行摘要，其结束更新可留下一批，不为了消除modified再无限提交。

## 必须保留的实验结论

唯一job2043445/cn21341成功，25次连续更新/1600帧/1epoch，完整Encoder/fp32/CKPT0/实际36核/KML；恢复记录参数/状态/前向一致且extra_updates0。仅工程小样本，formal split/subject UNKNOWN、val/test未运行；无科学/泛化/稳态性能/生产接受。02/08后续工作尚在进行，不能把新候选或真实摘要算作本批已核成果。权重远端留存，未下载，不把归档当部署或新优化收益。
