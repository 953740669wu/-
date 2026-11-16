# R21 FP32 Math SDPA 数值检查

R20闭合并确认无在途作业后才允许部署提交。针对历史CPU flash attention内SLEEF慢步位置，切换至本机安装PyTorch的MATH后端；全16域独立五步，对照R16域4完成的原版五步快照。仅FP32，不改变训练数据、掩码、损失、优化器和完整checkpoint，也不叠加FTZ/foreach/尾部裁剪。

原tensor_abs=2e-5、state_abs=2e-6、relative_L2=2e-6、near_zero=1e-8、floor=1e-12及optimizer步号exact保持。不同运算顺序可能改变位级SHA，与R18相同将历史最终模型SHA作为诊断记录，不能替代原完整张量误差门。任一原误差门失败即拒绝，不开启测速。候选数值通过也不能仅凭严格检查耗时宣布吞吐收益。

实际调用包裹原SDPA，逐次核Math唯一启用标志、CPU FP32输入、每步24次完整checkpoint调用；仍核直接KML形状/调用及实际库来源。900秒、最多80更新、逐域单步120秒停止；外部原版快照逐项字节/SHA和元数据绑定。准备不等于Linux运行或通过。
