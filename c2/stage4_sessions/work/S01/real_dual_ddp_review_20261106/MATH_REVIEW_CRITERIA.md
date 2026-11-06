# S01 独立数学与版本审核要点

本轮取W=2，各rank32、全局64。此文件是实施前审核依据，不是数值或执行PASS。

令rank r的两个平方误差和为Sv[r]/Sc[r]，元素数nv[r]/nc[r]，全局Nv=sum(nv)、Nc=sum(nc)。完整B64目标为L=sum(Sv)/Nv+sum(Sc)/Nc。默认DDP平均参数梯度时，本地反向目标应为Lr=W*(Sv[r]/Nv+Sc[r]/Nc)，于是(1/W)*sum(dLr/dtheta)=dL/dtheta。不能简单平均不等masked数的本地mean。仅分母/日志统计脱离梯度归约，平方误差和的本地反向图保留。

输入梯度不属于DDP参数reducer，本地反向产生W倍该片输入梯度，故与B64相应slice对照时除W；DDP后的参数梯度不能再次除W。Nv/Nc为零必须失败，本地零mask采用仍在图上的空选中sum或等价可微零，不重采样或加epsilon。

PyTorch2.7官方文档说明默认跨rank平均梯度；v2.7.1 reducer.cpp set_divide_factor使用process-group size，mark_variable_ready_dense在无comm hook时按此除数装入bucket。若候选注册hook，必须逐实现核均值语义而不能套默认。forward需通过DDP包装的完整Encoder+两head+loss计算图，不能从ddp.module直接执行训练forward。state/checkpoint访问module本身不是训练绕过。

来源（只作API/语义依据，不冒充已装C2源码身份）：
- [PyTorch 2.7 DDP文档](https://docs.pytorch.org/docs/2.7/generated/torch.nn.parallel.DistributedDataParallel.html)
- [v2.7.1 reducer.cpp](https://raw.githubusercontent.com/pytorch/pytorch/v2.7.1/torch/csrc/distributed/c10d/reducer.cpp)（set_divide_factor及mark_variable_ready_dense）
- [v2.7.1 distributed.py](https://raw.githubusercontent.com/pytorch/pytorch/v2.7.1/torch/nn/parallel/distributed.py)（DDP init/forward/reducer配置）
本地Windows2.7.1+cpu distributed.py只读SHA已存BASELINE_IDENTITIES.json；实际C2 API/库/导入身份仍由07/00新交付及现场gate验证。未用最新stable替代固定2.7.1。

其余必核：
1. 原25个B64批/1600独特帧，前32/后32无重缺样；原post-model-init mask RNG流，DDP构造/参考初始化/恢复隔离，逐步mask/frame/reference hash对齐。
2. rank0前5个原完整B64参考/AdamW连续更新，原compare字节与tensor/state/relative/exact阈值不变；输出、分量loss、输入/全部参数grad、参数/delta、AdamW/buffers、原键映射齐全，快照及时释放。
3. gate成功才同一DDP模型/optimizer继续6—25；最多25全局/50rank+5参考=55物理更新，参考320帧不计训练吞吐；失败原样停止。
4. 每步原名/shape/dtype/张量字节的参数/AdamW同步hash，非整个checkpoint文件hash；最终原Encoder/optimizer、rank RNG、独立mask RNG、游标、归一化、源/数据身份保存并真正执行零额外更新恢复。
5. 单一baseline kml_ops实例/实际KML-OpenMP-shim/无静默native，Torch intra-op36与全部TID在各自selected36内，参考和DDP实际调用分别计数而不套旧149。
6. 两域76分配72实际留4、DDR总24576MB同limit/exclusive/HBM0；新PG120秒，原R7 pg5/case30不重复；从同一job起点840执行+30清理+30收尾到900，所有前置与应用共享，所属PID/后代有界回收。
7. 结果分列前5含参考诊断与后20、同步/等待/最慢rank/诊断/壁钟及HWM范围；无同job单域对照即不算加速。只有收到RUN_COMPLETE并按analysis_inputs核真实metrics/步数/恢复/清理才给实际结果结论。
