# Torch2.7.1 DDP接口核对

默认隔离Python3.11无Torch/NumPy；S02冻结READY指向的已有venv实际为Torch2.7.1+cpu/NumPy2.2.6，Gloo可用，未安装依赖。已用它做真实autograd和本机TCP两rank小DDP。运行入口在任何模型更新前核实际Torch版本必须2.7.1、DDP构造签名包含全部指定参数，并保存安装源路径/SHA、真实Torch/NumPy身份。若C2现场API不符即失败，不降级参数或继续训练。

本地原FileStore检查停在before_pg至25秒父截止，原件保留，原因未定。改为明确的Windows localhost TCP检查后，沙箱内报10013/10049；相同代码/25秒边界在沙箱外单次通过。不能将本机TCP通过说成Linux文件rendezvous、C2原始初始化或完整模型训练通过。Linux检查保持file://且不自动回退；原R7、训练的文件rendezvous及PG120均未改。

随后补充的完整fp32小B64配对触发原数值阈值：13项中val.weight/pos.weight/tf.weight三项FAIL，具体误差见REPORT及evidence。两rank归约梯度一致与输入梯度缩放通过不能替代该数值门槛。最终本地结果为17过/1失败/1 Linux skip，早期18过1skip不作为最终状态；不调整阈值/参考或继续数值试跑。

核对PyTorch官方[v2.7.1 distributed.py](https://raw.githubusercontent.com/pytorch/pytorch/v2.7.1/torch/nn/parallel/distributed.py)构造函数581—599、735—742和forward 1500—1508，以及[2.7官方接口](https://docs.pytorch.org/docs/2.7/generated/torch.nn.parallel.DistributedDataParallel.html)。使用CPU device_ids=None/output_device=None、init_sync=True/broadcast_buffers=True、bucket_cap_mb=25、find_unused_parameters=False、gradient_as_bucket_view=False、static_graph=False。只选这一配置，不做bucket搜索；不注册comm hook、不用no_sync/join。

官方[v2.7.1 reducer.cpp](https://raw.githubusercontent.com/pytorch/pytorch/v2.7.1/torch/csrc/distributed/c10d/reducer.cpp)的set_divide_factor以进程组大小为除数；未安装自定义hook时，密集梯度复制到bucket时缩放，再SUM归约。因此本地backward用2×局部平方和/全局分母；DDP参数梯度不再除2，输入梯度由S02原适配器除2。这里是官方固定tag语义核对，不能替代实际安装二进制/小DDP或完整模型现场验证。

完整训练只调用ddp(*values, mask)；wrapper.encoder为原完整Encoder，两个head和loss平方和都位于wrapper.forward内。canonical Encoder仅用于参数/状态检查、参考比较及零更新恢复probe；训练不经ddp.module绕开forward。每步所有canonical参数必须有有限梯度，原37995777参数及优化器覆盖都检查。

DDP的_get_ddp_logging_data原始字段记录到每步结果。其时间字段是实现采样/平均的观察量，不能把它或backward壁钟当孤立网络延迟；另外记录分母归约、状态同步和参考门禁等待。没有同job单域25步对照，speedup=NOT_MEASURED。
