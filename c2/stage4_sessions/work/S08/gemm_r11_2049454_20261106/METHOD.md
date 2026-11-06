# R11 实际GEMM记录口径

只读S00 round11 RUN_COMPLETE明确锚定的元数据；新job2049454、ENGINEERING_REAL_CORPUS_GEMM5_V1，不放宽旧PILOT/PROFILE5解析门禁。INPUT_VERIFICATION.json保存交接、3份实际记录、result/steps/audit/contract/reference及收集索引的path/bytes/SHA，冻结observer、baseline KML及帧身份哈希函数均核源码SHA。解析开始前和结束后重核原件。只写本轮S08目录；不读取NPZ、图像/电压或权重，不执行Torch、BLAS、训练或SSH。

每记录必须满足：样本step和call_index连续唯一；1个原生调用；thread_id=ctypes_thread_id；g_start<=c_start<=c_end<=g_end；两个wall与配对差值精确等于纳秒区间差。父调用若存在，要求同线程、包含、无缺失/环。由原始A/B存储shape及ta/tb推导m/n/k，核输出shape、fp32/contiguous/stride和报告的无alias；根据已冻结Linear context和flags核forward/dX/dW，不凭shape猜角色。

CBLAS参数独立按原baseline核：row-major101，transa/transb按ta/tb为112或111；alpha=1；lda/ldb等于原连续存储行长；ldc=n；实际beta在given_out时为请求beta，否则为0。native参数记录必须全等。观察器在节点上对原14个位置参数、指针及给定out做了检查；S08核元数据与冻结检查源码，不接触tensor，因此不能独立重建原地址或验证内存内容。

外层gemm_wall覆盖原计数GEMM调用：分配/计数/参数设置/原生调用及观测hook bookkeeping；不含进入GEMM之前的Linear reshape、dtype转换、contiguous或bias铺开。内层ctypes_wall覆盖原_sgemm(*原参数)调用，含Python/ctypes转换和原生库打包/调度/计算，不是纯微内核时间。outer_minus_ctypes是每对区间差，含观察器原生hook bookkeeping，不自动等于纯准备或分配成本。observer_before/after在外层外，完整插桩/上下文开销没有匹配对照，仍UNKNOWN。

按role及完整签名分组：m/n/k、ta/tb、请求/实际beta、given_out、实际A/B shape/stride和全部原生layout/trans/alpha/leading dimensions。每组分别算step3/4/5的调用数、两个边界区间并集、每对差值和，再分别求跨样本min/median/max；另提供逐调用耗时与差值的min/median/max。不能用median(outer)-median(ctypes)代替median(每样本配对差)，也不能累加不同组或角色的独立中位数冒充全程中位。

同线程重复/嵌套区间用并集去重，保留raw sum、per-thread union、同线程移除量。跨线程同时报告各线程并集之和与所有线程投影到同一单调时钟的区间并集；前者不是wall，后者仅是观测GEMM覆盖区间，不是程序wall。配对差值和与outer/ctypes覆盖并集之差分列，存在嵌套时两者一般不等。当前3份均只有记录调用线程1758130，parent全空且无重叠，因此本次组内sum恰等于union；不推断原生库没有工作线程。

SHAPE_RANKING按每采样参数组ctypes覆盖中位排序，同时列outer排名；CALL_RANKING按447个单次ctypes_wall排序并保留outer排名。group含每个(step,call_index)引用；每条call含原文件path/bytes/SHA、JSON pointer、线程/parent、签名及两组单调起止时间，足够回查原始记录。缺记录或冲突先写CALL_VALIDATION并停止，不截断、不补值或升级接受。

最小LOCAL_FIXTURE先写后实现：正常配对；线程/边界错；shape/flags/leading dimensions错；丢配/alias；角色不从尺寸猜；嵌套/重复并集；跨线程覆盖不等于线程和。人工计时不是实际矩阵运行结果。实际loss/data/init/mask/CPU36/恢复仅核原记录及参考锚，不重算模型。

复现入口：`python -B analyze_gemm.py`，仅使用本轮INPUT_VERIFICATION显式指定的文件，拒绝覆盖已有生成JSON。该入口生成基础JSON及shape表；GEMM_SUMMARY.md为结合VALIDATION和原记录上下文的人工核对说明。R12固定N列分块尚无数值/性能结果；R11诊断时长不作正式对照，不按FLOPs或调用边界耗时保证收益，不提交新job。
