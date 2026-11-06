# 固定首批零更新定位：目标C2证据绑定后的本地准备R2

状态：交原02窗口；可与唯一Git窗口并行发送。本批不重复纳入02已归档且未变的根短状态，只提交02不可变R1档案；02仅写R2新目录及自己的根状态，不影响Git冻结文件。卡已发布，不代表02接收/启动。B01设计证据已解除；原R1阻断交付永久保留。

## 本轮目标和授权

将01已接受的目标API/专用输入边/attention布局要求转成具体、可独立审核的观察器及零更新诊断入口源代码。允许仅在新目录实现代码、文档，执行针对性的标准库元数据/替身夹具、Python3.9 AST语法/包清单/SHA检查。不是数值修复候选，不修改原算子或模型。不导入Torch、执行模型或目标源码，不启动真实诊断或Linux进程生命周期测试；不SSH、部署、安装提权、提交job或操作共享Git。

仅写S02/real_dual_ddp_localization_prepare_r2_20261107/及自己的短状态/六行摘要。不覆盖R1目录/包、原规格、原比较器、参考实现、数据和旧FAIL。必要复用以精确来源绑定为主，避免复制全项目。R2新材料不追加到正在执行的Git冻结批；Git回执不等于准备已开始。

## 参考文件

以E:/eitfm_c2_stages2-4_2026-11-03/c2/stage4_sessions/work/为根：

- 自己SESSION_STATUS.md/ROUND_DELTA.md及R1 PREPARATION_BLOCKED.json，只用来继承边界，不重复已解决的缺六源/未知Node槽位探索。
- S01/real_dual_ddp_c2_binding_review_r1_20261106/SOURCE_BINDING_REVIEW.json，SHA256 9296833a48c0485a42b6b05600688d088d2d16510f260d618bda134b3bbddbff。
- 同目录PREPARATION_REQUIREMENTS.json，SHA256 913e268fc424d30b56bf95f1023d919b39188985d6e022ee53c53c43ca269c01。接口、源码行号、布局表、覆盖和拒绝条件以此为直接实现要求。
- S00/real_dual_ddp_c2_source_binding_r1_20261106/SOURCE_BINDING_PACKET.json，SHA256 b0a0c1e11fb0ba26987f69cfc13b24eb15dc97820f141cfa835857af56edd93f；六份原文/身份只读。
- COORDINATION/REAL_DUAL_DDP_C2_SOURCE_BINDING_R1_20261106.md方法增补，SHA256 528027e6e639a6f389357aafdda9179d22f2f9e3b4a288902d88ea11cfa0c04f。
- S01/real_dual_ddp_proposal_review_20261106/MINIMAL_EVIDENCE_SPEC.json，SHA256 d1da482f2971281996ac70e9133606933277bb31bfead1a48ed64fbbddaf67c2；原规格与增补分别绑定，不改写原件。
- COORDINATION/S01_C2_BINDING_ACCEPTANCE_20261107.json；冻结S02真实参考中的模型/KML/engineering_training和原compare，按01要求读必要位置。

## 完成标准

1. 编码前写简短DECISIONS_BEFORE_CODE.md，说明被动观察具体接入点、调用/ctx/参数映射、布局、引用生命周期、保留量/序列化和有界退出方案。若新发现实质冲突，明确具体证据和影响；不得静默降低覆盖或改变原计算。
2. 实现实际F.linear边界的窄范围适配及原_LinearFn.backward返回观察，保证冻结原调用恰好一次、参数和返回对象不变，覆盖packed QKV和functional out_proj，不能只依赖out_proj模块hook。注册G与native专用输入边dX的被动Tensor hook，return None；finally移除handle、还原适配、释放图/张量引用。
3. native val只观察既有v[...,None]，head_coarse只观察既有h.mean(1)；不得以共享v/h.grad替代、造clone/detach/新Function代理、猜Node槽位、额外backward/autograd.grad/GEMM。KML gx/gw/gb与调用身份关联；pos的gx=None按实际requires_grad明确合法，不能制造缺失回调记录。
4. 严格实现01布局表：QKV [208,B,512]及out_proj [208*B,512]为r=t*B+b；其它token线性为r=b*208+t。按原sample ID分片规范化哈希，不能将token-major前6656连续行当首32样本。模式/source/shape/stride/参数/回调重缺或未审hook/dispatch等不符即拒绝。
5. 未来诊断入口只准备源代码：原首64、seed/mask/scale/初值；原完整B64 mean一次forward/backward，对照顺序32+32一次；0 optimizer更新/0DDP/0额外收缩；顺序全局分母、所有系数1且不再除2，全153参数/输出损失/输入梯度与原比较器阈值保持。不得调用会step的helper。本轮不运行入口。
6. 实现有界流式哈希/比较和内存计账，104MiB输入不得整块复制进32MiB哈希工作区，不保留各层全部X/G。重新给实际实现的拷贝/缓存/handle/serializer上界，不把909.1553MiB旧条件预算当实测。原extra1GiB/raw512MiB/text64MiB上限不变；无法满足则明确阻断，不扩限。
7. 保留未来共同240执行+30清理+30收尾/300秒、单路径90秒、实际compute创建身份与所属后代退出证据要求；本轮只做元数据/替身检查，不能宣称真实Linux回收通过。CPU36/24GiB/300秒均为未来拟议上限，不是新job许可。
8. 先写针对改变点的最小标准库夹具，再实现并验证：原调用恰好一次与对象不变、hook注册/移除及异常还原、角色/ctx映射、token-major取样/重缺拒绝、流式工作区计账、原数值契约/零step/共同deadline门禁。替身不得导入Torch、加载权重或执行目标库；标LOCAL_FIXTURE，不证明autograd/KML/数值/峰值/真实进程退出。不重复运行Tiny或无关旧套件。
9. 交INTERFACE_READY.json（只接口，不启动00）以及源码、最小diff、来源/包SHA、SOURCE_BOUND_COVERAGE.json、保留量和实际本地检查、NOT_RUN、精确归档清单。可审核代码/自查/授权检查齐全才交PREPARATION_READY.json，明确preparation_only=true、execution/training_authorized=false；这是待01独立代码审核的准备声明，不是执行放行。具体实现阻断则交PREPARATION_BLOCKED.json，不以只有元数据契约包冒充完整入口。
10. 更新自身短状态与六行摘要，返回READY或BLOCKED绝对路径和包SHA。明确实际运行均0（Torch/模型/autograd/数值/DDP/SSH/job），标准库本地夹具按实际记录。

## 下一步

02交付后由总协调核身份并另交01独立代码/数学/内存/退出审查；如需00部署准备另定具体卡。当前01/00/07/08待命，不能自动启动后续。实际计算必须在具体包/审核/资源齐备后另交用户明确决定；用户“不追加集群作业”约束保持，原FAIL不变。
