# S01 B01 准备阻断定向审核

结论：**ACCEPT_BLOCKED**。02准确报告了“现存材料不足以绑定实际C2 native VJP/布局”，没有证明Node hook普遍不可行，也没有证明实际观察入口已经实现。现有离线材料不能解除原规格的B01；不得在同样缺源条件下再要求02重复准备。原MINIMAL_EVIDENCE_SPEC、原比较器/阈值和最终FAIL均不改。

先核PREPARATION_BLOCKED SHA=`ef06bbab565c30b2c81298b48a48a678c847618e4e751d2bc2529c961cdce1d7`及直接交付，再核29项输入、10项源清单和11成员包，共51个唯一文件bytes/SHA一致。原规格与SPEC_SNAPSHOT同为 `d1da482f2971281996ac70e9133606933277bb31bfead1a48ed64fbbddaf67c2`。证据见 BLOCKER_AUDIT.json；只做文件/文本/整数复核，未运行作者代码、夹具或任何Torch操作。

保存的C2运行时清单仅列torch/__init__.py、nn/parallel/distributed.py、NumPy初始化文件，实际保存源码字节的只有DDP文件；既有R4合约和DDP SHA不能绑定native F.linear的backward节点、grad_inputs槽位或attention行布局。Windows2.7.1的autograd/graph.py说明Node hook可读梯度并返回None，functional.py展示attention的token-major变换，这些是设计依据，不是实际C2目标文件证明。结论只限已枚举来源，不宣称整个磁盘都没有材料。

|疑点|可确认事实|不能据此确认|
|---|---|---|
|native val dX|冻结Encoder使用val(v[...,None])，原loss也直接使用v作为target；v.grad汇合预测与target分支。|v叶梯度不是val局部VJP；不能猜AddmmBackward0某槽位或额外autograd.grad重算。|
|native head_coarse dX|冻结loss调用head_coarse(h.mean(1))；h还接head_v分支。|h.grad不是head_coarse局部VJP；形状相同/共享storage不证明边归属。|
|attention逻辑样本|R11 B64形状/ABI及Windows前端示例已保存。|[13312,512]本身不证明行前半为前32样本；C2 batch_first/transpose/flatten/fastpath来源仍未绑定。|
|自定义KML|冻结_LinearFn.backward明确返回gx/gw/gb，源码可支持被动返回观察的设计。|不自动证明目标运行时观察器已安装、实际返回/计数/TID/库验证通过。|

909.1553MiB预算的整数加和正确：953318436bytes，距1GiB余120423388bytes；包含三份参数规模状态、两份输出/输入梯度值、256MiB串行比较、32MiB哈希、64MiB输入、64MiB文本和4MiB buffers。原始参考值180466704bytes低于512MiB。这是**有条件的保留量估算**，不是Tensor分配、allocator缓存、autograd/KML工作区或24GiB峰值实测。尤其linear2的B64 X有109051904bytes（104MiB），整块contiguous/转bytes复制会超过32MiB哈希工作区；必须落实按逻辑行分块、无全层快照及未计副本拒绝，当前未实现。

14项LOCAL_FIXTURE源码和既有日志相符，覆盖行映射公式/缺样拒绝、1/1/1缩放、路径/截止/字节上限、模拟proc身份/清理事件、报告拒绝和缺少覆盖标签等。两CLI案例也只读写LOCAL_FIXTURE元数据。require_observer_coverage检查的是声明角色集合，rows检查的是格式合法的provenance字符串；这些字段不能替代真正的目标源码SHA/边归属证明。没有实际autograd、KML、Tensor内存、Linux TERM/KILL/reap或可部署模型入口，本轮无需重跑夹具。

**推荐的唯一下一选项：待批准的方法澄清 + 定向C2前端绑定材料包**，见 MISSING_BINDING_SPEC.json。本建议不删局部dX覆盖，也不降低数值门槛：原生val的已有输入是新建unsqueeze视图，head_coarse的已有输入是新建mean结果；若目标源码和具体观察实现证明该输入边只供这一线性调用消费，可在这个已有非叶输入边被动读取局部dX，并在已有输出边读取G，避免依赖未知Node grad_inputs槽位。不得增加clone/detach/requires_grad代理输入、改变算子或以叶梯度冒充局部VJP；不能证明专用边/映射时仍BLOCKED。

原规格“return/node observer”方法条款与02覆盖角色必须由协调**显式澄清/修订为新版本**，不能给旧字段随意填标签过关。若获批准并验证专用边，保留同一数学局部VJP与数值覆盖；不再声称知道native内部节点名称/槽位或内核细节。此建议不是现有实现可行性的实测结论。

最少补源为实际R4 Torch根下 `_tensor.py`、`nn/modules/linear.py`、`nn/modules/activation.py`、`nn/modules/transformer.py`、`nn/functional.py`、`version.py`六份已安装文件字节及路径/realpath/bytes/SHA/目标身份清单；复用已保存__init__/R4身份，并绑定实际native扩展/核心库文件身份元数据。只要Windows版本号、上游标签或更多DDP源码都不够。该包支持核Tensor hook语义、原生Linear调用边及attention前端布局；不是重新索要完整系统/源码树，也不要求先做新的数值实验。

获得方式：若持有人已有确切目标副本可离线交付，无需SSH；本轮已列材料中没有。否则需另行明确授权S00只读、定向导出这六文件和身份清单，可能需要新SSH/远端文件读取权限，**不需要为补源提交计算job、导入Torch、运行夹具/模型/反向或取新上游源**。本轮没有做这些操作。若文件/构建身份不可读或目标前端不支持专用边证明，停止并交具体缺项，不能安装/提权、重试实验或退回硬编码Node槽位。

材料到齐且方法澄清获批后才重新交02；解除的是重新设计/实现审核的证据前提，不能直接生成PREPARATION_READY或执行许可。未来模型运行仍须具体新实现/SHA/预算/生命周期复核和独立授权；旧900秒或拟议300秒许可均不能借用。若坚持原Node/return方法不修订，则还须目标native节点/槽位/视图拓扑的可追溯绑定证据；现有材料仍不能满足，不在本轮自动另排运行来取得。

原最终FAIL、DIAGNOSIS_REVIEW、收尾结论、原规格均重核未变。仅写本S01新目录及两份短状态，输出BLOCKER_REVIEW.json / MISSING_BINDING_SPEC.json / ARCHIVE_SCOPE.json；不取新源、不SSH、不导入Torch、不执行测试/模型/收缩/DDP/进程查询/作业，不修改作者原件或共享Git。协调收到后决定方法澄清与补源授权，不重复分派相同缺源检查。
