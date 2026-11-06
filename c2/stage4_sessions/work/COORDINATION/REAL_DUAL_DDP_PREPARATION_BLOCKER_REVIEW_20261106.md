# 本地取证准备B01阻断的定向审核

仅交原01窗口，等待本批Git提交完成后再发起，避免改动本批冻结的01短状态。卡已发布不等于已接收/启动。原02已按要求交阻断终态，未交PREPARATION_READY。

本轮目标：核B01_UNBOUND_INSTALLED_NATIVE_VJP是否被已保存证据准确支持，并确定解除阻断所需的最小材料或方案调整；不要重复静态提案或要求02在相同缺源条件下重做准备。

参考文件（以E:/eitfm_c2_stages2-4_2026-11-03/c2/stage4_sessions/work为根）：自己的短状态；S02/real_dual_ddp_localization_prepare_r1_20261106/{PREPARATION_BLOCKED.json,CAPABILITY_ASSESSMENT.json,DECISIONS_BEFORE_CODE.md,RETENTION_PROOF.json,LOCAL_CHECKS.json,NOT_RUN.json,evidence/SOURCE_INPUTS.json}；自己real_dual_ddp_proposal_review_20261106/MINIMAL_EVIDENCE_SPEC.json及原FAIL；必要时才看具体支持代码/已保存运行时来源。

完成标准：
1. 先核SHA。仅写S01/real_dual_ddp_preparation_blocker_review_20261106/及自身状态；不改作者包、原规格或旧FAIL。
2. 判断阻断是已保存C2节点/槽位/布局来源缺失，还是实现层面不可行；不得把前者扩大成Node hook普遍不可行。区分Windows API设计依据与实际C2绑定证据。
3. 对native val/head_coarse逐算子dX、attention逻辑样本布局以及共享输入多消费者风险分别核查：现有离线原件能证明什么、不能证明什么；v叶合并梯度不能代替val局部VJP。不得硬编码未知槽位/额外反向或改算子补证。
4. 复核909.1553MiB保留量的假设及14项LOCAL_FIXTURE的覆盖边界；这些都不是实际Tensor峰值/autograd/KML/Linux退出测试，不必重跑夹具。
5. 将最小下一步具体化为一个选项：若已有离线来源可解则给精确路径/SHA/API依据；否则给MISSING_BINDING_SPEC.json，列最少目标版本/文件或需观察的运行字段、获得方式、是否必须新运行/新SSH、预期证伪条件。若认为原规格某观测要求不是回答原问题所必需，可提出明确的规格修订建议及损失的结论范围，不能自行降级原规格/降低数值阈值。
6. 本轮只读文件/哈希和文档，不取新源、不联网/SSH、不导入Torch、不运行模型/autograd/DDP/夹具/进程查询，不申请job、安装或提权。
7. 输出BLOCKER_REVIEW.json、必要MISSING_BINDING_SPEC.json、简短REPORT和精确归档清单；给ACCEPT_BLOCKED/REVISE及证据范围。更新短状态和六行摘要，返回绝对路径。
8. 若没有现存来源可解除阻断，明确还需要什么具体操作和授权边界；不能继续循环分派相同静态检查，也不把本次审核当实际执行许可。

02/07/00/08待命。协调收到01结果后决定精确离线补源、明确规格修订或向用户呈必要且具体的最小运行请求；当前不追加集群作业。原始B64/fp32、compare/阈值/FAIL保持。
