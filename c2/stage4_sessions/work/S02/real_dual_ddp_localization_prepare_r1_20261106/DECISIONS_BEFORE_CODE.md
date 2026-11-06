# 编码前决定：LOCAL_FIXTURE支持包，实际取证阻断

2026-11-06（Asia/Shanghai）。先核MINIMAL_EVIDENCE_SPEC SHA d1da482f2971281996ac70e9133606933277bb31bfead1a48ed64fbbddaf67c2和29份来源，不导入Torch/反序列化/运行模型。当前卡只授权本地代码与标准库夹具，规格原implementation_authorized=false是原发布时状态，当前卡仅授权这些准备项，不授权实际取证/部署或作业。

唯一主阻断B01_UNBOUND_INSTALLED_NATIVE_VJP：规格要求全部线性的实际逐算子dX。冻结_LinearFn返回gx/gw/gb，可静态设计返回节点的只读post-hook，但完整val/head_coarse走原生F.linear，其3D flatten/view/addmm等实际autograd图和grad_inputs槽位没有C2绑定依据。已有SHARED_RUNTIME_FILES只保存Torch __init__/DDP/NumPy（只有DDP源正文），不是autograd Node/native Linear图契约。本地Windows2.7.1 autograd/graph.py:83—107说明Node.register_hook可读取grad_inputs/grad_outputs，返回None可保持梯度；没有保证某个F.linear输出grad_fn就是Linear VJP或其哪一槽是X。不得硬编码AddmmBackward0/slot1、把共享输入叶梯度当局部dX，或额外backward/autograd.grad/GEMM补算。不是断言Node hook普遍不可行，是目前指定C2来源无法可靠证明完整覆盖。没有完整逐算子observer就不制作可执行模型入口/不发PREPARATION_READY。

逻辑轴：batch-major token线性row=b*208+t，attention token-major row=t*B+b；2D out_proj同样可能由token-major flatten而来，不能仅从shape[13312,512]判定前/后32。局部Windows源码functional.py:5614/6414—6418可提示QKV/out布局，不能当C2同SHA源码。夹具只在显式shape/样本ID/布局来源绑定存在时产生行映射；缺来源、重/缺/乱序样本一律拒绝。具体已装C2 attention布局绑定仍属于B01缺失的逐算子/布局来源证据，不用猜测填字段。

参考数学：未来只允许冻结engineering_training.losses原mean表达式和一次backward。不能调用training.train_step或B64Reference.advance（均执行optimizer.step）。顺序32+32全局mask计数由同一个原64mask求得（不是Tiny4），coarse全局16384、各8192；本地loss系数/参数及输入grad除数全为1。不创建优化器/第二模型；0更新/0DDP/0额外收缩。数字或元数据失败后只整理已有值，不开始新forward/backward路径。

内存设计：P=37995777个fp32参数，P*4=151983108bytes；预算保守计一份初态、一份B64梯度和一份顺序累计梯度，即3P。另计两份h/v/coarse、v/image梯度和loss、1MiB image上界（64x1x64x64）、比较临时256MiB、流式哈希32MiB、输入保留64MiB、文本/索引64MiB、buffers4MiB。总计须低于1GiB，具体证明由标准库整数账本生成。原compare最大h有6815744元素，double转换/差值/abs按不超过4倍8bytes计218103808bytes，256MiB只是条件性工作区上界；必须逐项只比较/流式哈希，若以后实现出现额外全层副本或更大buffer即停止。Torch图/基础模型/库实际工作区不包含在extra预算，未来24GiB实际峰值未验证。原始诊断远端512MiB/文本64MiB分别计账，不序列化初始权重，不回传raw。当前无Tensor保留或输出，只夹具计数。

实际compute身份计划：未来Linux直接Popen([已核绝对C2解释器,'-B',入口,...],start_new_session=True)，不用shell/Windows启动器推断。compute自身在Torch前读PID/PPID/proc stat start_ticks/boot_id/pgid/session/native job+run nonce+exe SHA，写原子握手；监督器核直接PID和PPID/自身start身份，逐个绑定所属后代(start ticks+已核父链)。本轮只解析合成proc文本/身份夹具，不启动、查询或发信号给任何进程。未来只对所有权仍匹配的进程组/后代TERM→有界KILL/reap，必须有actual退出与后代清单证据；仅Popen回收/后来的PID不存在不能PASS。

共同预算：来自同一起点的执行+240、清理+270、收尾+300，每路径不超过90且服从共享240；数字失败锁住新计算。夹具测试deadline/身份/退出事件不会证明Linux真实时序。未来缺实际退出/未知后代就是INCOMPLETE/FAIL，不补造记录。当前没有compute入口、部署/作业命令或运行许可。

先写标准库夹具：显式batch/token-major映射与拒绝歧义/重缺样、顺序分母和1/1/1、A1+B1/各forward-backward计数/禁更新与额外算子、内存及raw/text边界、共享deadline/数值停点、带括号proc stat解析/身份不匹配、仅Popen回收拒绝、缺空/残/旧SHA报告拒绝、缺C2逐算子来源拒绝。然后实现只支持这些元数据契约的最小模块；LOCAL_FIXTURE声明不可提升为实际autograd/KML/Linux/模型通过。
