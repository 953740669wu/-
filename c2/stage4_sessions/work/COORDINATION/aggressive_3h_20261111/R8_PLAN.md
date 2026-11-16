# R8：全层checkpoint末尾重算裁剪

触发：R5满16域时无checkpoint的域0约14.4秒，原全层checkpoint约10.5秒，单域收益没有保持。完整窗口仍需核验。优先保留低内存路径，减少不必要的重计算；原R6 foreach与R7 attention准备暂后置，不追加并行作业。

现场Torch非重入checkpoint会在最后一个所需saved tensor恢复时提前停止。冻结Encoder为norm_first、dropout=0，最后FFN线性层原forward先做GEMM，再保存输入与权重。候选仅在重算时恢复这两个原样输入，跳过随后不会被使用的输出GEMM。正常前向与原图反向均保持原实现，无额外激活缓存。

保护：如果恢复输入后框架没有立即提前停止，候选直接报错，不允许空占位输出进入模型；占位Function的backward也禁止执行。每步必须实际跳过12次且escaped=0，原197次KML GEMM应变185，只有FFN2前向重算少12次。

先跑原五步完整输出/梯度/参数/AdamW状态误差门，失败就停。通过再一次25步配对并核内存。依赖冻结Torch/checkpoint行为，升级框架须重新验证。若有效且时间足够，再以满16域固定窗检查实际收益；不能拿单域收益直接推广。
