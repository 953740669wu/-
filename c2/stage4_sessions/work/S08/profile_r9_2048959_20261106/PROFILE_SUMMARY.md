# R9 job2048959：三份真实采样归因

结论：先核KML线性/反向边界，再独立核布局复制路径。三次采样都支持这个排查顺序；尚不能指定最大矩阵、纯KML内核时间或copy的源tensor。仅工程剖析观察，不是性能接受。

cn21338；连续5次AdamW/B64、320训练帧，16单元/1600帧用于固定归一化。1—2预热，3—5采样。输入协议为ENGINEERING_REAL_CORPUS_PROFILE5_V1；交接、6份采样bytes/SHA和采样限额已核，具体身份见INPUT_VERIFICATION.json。未用旧PILOT汇总器。

阶段wall（秒；各列是独立计时，不相加父子事件）：

| step | 类型 | zero前 | forward/loss | zero后 | backward | optimizer | step合计 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 预热 | 0.001058 | 1.691317 | 0.000439 | 3.348911 | 0.157520 | 5.200396 |
| 2 | 预热 | 0.001036 | 1.532610 | 0.000549 | 3.010924 | 0.141917 | 4.688027 |
| 3 | 采样 | 0.044972 | 1.571089 | 0.000470 | 3.480861 | 0.173312 | 5.272537 |
| 4 | 采样 | 0.001107 | 1.515943 | 0.000411 | 3.485786 | 0.173939 | 5.178975 |
| 5 | 采样 | 0.001044 | 1.400948 | 0.000468 | 3.171818 | 0.172542 | 4.748488 |

采样3—5的forward/loss、backward、optimizer中位分别为1.515943、3.480861、0.173312秒。

profiler外层开销（秒；不包含已混在step内的插桩成本）：

| step | setup/start | stop | postprocess/export | 外层合计 |
| --- | --- | --- | --- | --- |
| 1 | 0.000000 | 0.000000 | 0.000000 | 0.000000 |
| 2 | 0.000000 | 0.000000 | 0.000000 | 0.000000 |
| 3 | 0.001481 | 0.224506 | 4.648733 | 4.874721 |
| 4 | 0.000998 | 0.229874 | 5.165259 | 5.396131 |
| 5 | 0.000904 | 0.250035 | 5.492760 | 5.743700 |

程序wall 82.124880秒；5步合计25.088423秒；profiler外层16.014551秒；调度另计94节点秒。采样内插桩开销UNKNOWN，不以预热差或旧跨节点结果推断。

事件self CPU排名（毫秒；括号内为各采样调用数，不是程序wall占比）：

| event | step3 self ms | step4 self ms | step5 self ms | ranks 3/4/5 | calls 3/4/5 |
| --- | --- | --- | --- | --- | --- |
| S02/KML_python_gemm_envelope | 3035.600 | 3025.857 | 3174.820 | 1/1/1 | 149/149/149 |
| aten::copy_ | 417.229 | 416.739 | 284.686 | 2/2/2 | 1003/1003/1003 |
| aten::_scaled_dot_product_flash_attention_for_cpu_backward | 242.569 | 245.121 | 180.481 | 3/3/3 | 12/12/12 |
| aten::_scaled_dot_product_flash_attention_for_cpu | 231.773 | 213.523 | 127.855 | 4/5/5 | 12/12/12 |
| aten::fill_ | 150.434 | 236.799 | 136.642 | 6/4/4 | 154/154/154 |
| aten::clamp_min | 142.520 | 126.374 | 90.754 | 7/6/8 | 12/12/12 |
| aten::add_ | 160.545 | 113.285 | 111.379 | 5/7/6 | 356/356/356 |
| aten::add | 139.953 | 96.528 | 22.769 | 8/8/17 | 26/26/26 |
| aten::sum | 73.669 | 92.544 | 89.639 | 9/9/9 | 56/56/56 |
| aten::mul_ | 71.463 | 72.643 | 93.447 | 10/10/7 | 306/306/306 |

三份均10845事件、130 distinct keys，仅导出top80。KML self CPU始终第1、149次；copy_始终第2、1003次。JSON保留跨样本min/median/max与rank，未导出key不填0。

KML逻辑归属与同线程区间并集（毫秒）：

| parent路径 / phase | calls 每样本 | step3 union ms | step4 union ms | step5 union ms |
| --- | --- | --- | --- | --- |
| _LinearFn / forward_loss | 50 | 798.393 | 826.411 | 1017.997 |
| _LinearFnBackward / backward | 99 | 2242.562 | 2205.942 | 2161.634 |

447个包裹全部可由parent链、同pid/tid和完整包含区间唯一归属；各样本均pid1306257/tid1。实际包裹无嵌套重叠，去重差0；实现仍取区间并集，不累加LinearFn/phase父inclusive。trace tid1是FunctionEvent标识，不能据此说原生KML只有一个工作线程。
第3步索引例：forward KML event62→parent49(_LinearFn)→phase event3；backward KML event2036→_LinearFnBackward→phase event1888。完整447项起止/parent/祖先ID在ATTRIBUTION_INDEX.json，且绑定各trace SHA。

copy_逻辑祖先分类（毫秒；每个copy仅分一类，不是其tensor来源证明）：

| phase / owner | calls 每样本 | step3 union ms | step4 union ms | step5 union ms |
| --- | --- | --- | --- | --- |
| backward / ViewBackward_reshape_path | 96 | 244.096 | 212.577 | 171.565 |
| backward / attention_backward_path | 12 | 16.208 | 13.814 | 7.976 |
| backward / layer_norm_backward_path | 12 | 11.455 | 11.610 | 7.292 |
| backward / other_observed_ancestors | 38 | 21.981 | 55.327 | 45.183 |
| forward_loss / _LinearFn_forward_boundary | 62 | 96.125 | 98.193 | 31.573 |
| forward_loss / other_observed_ancestors | 18 | 23.770 | 21.651 | 17.422 |
| optimizer / optimizer_path | 765 | 3.593 | 3.566 | 3.675 |

关键细分：96次ViewBackward路径为clone←reshape←ViewBackward0，耗时171.565–244.096ms；62次Linear前向边界拆成50次clone←contiguous与12次clone←reshape。optimizer的765次为_to_copy/to下的add_/mul_/div路径，调用多但本次copy区间仅3.566–3.675ms。不能按调用数代替耗时排名。
未观察到copy_位于KML包裹或_LinearFnBackward子树内；其余复制有attention、layer norm、select_backward等可见祖先。ViewBackward对应何处前向、具体源/目的tensor、shape/stride和原生库内部复制仍UNKNOWN。JSON保留完整祖先链分组与代表event_id，可由02在冻结源码中定向核查。

建议：优先核99次反向KML调用的实际边界和安全布局/临时分配，再分别核62次前向边界copy及96次ViewBackward复制。下一项最小证据是与冻结源码对应的逐调用shape/stride/alias身份；当前不能凭排序删除contiguous、认定reshape均复制、缓存会更新的权重或把包裹耗时称内核时间。任何候选须原严格数值检查及另行授权的同机无profiler A/B；本轮未提交job。
未知与边界：纯KML内核时间、逐调用矩阵shape、复制tensor来源、采样内插桩成本均未知；OS线程数不等于物理核数，不改线程默认。不与cn21341旧训练wall算加速率，不把process-lifetime采样HWM称稳态或整个job最终峰值。无正式val/test、subject映射或科学接受。
方法及复现：METHOD.md、analyze_profile.py；6个LOCAL_FIXTURE归属/缺事件/嵌套去重检查通过。原证据与权重不写入本轮，未读NPZ/权重、未训练、未连接集群。原件前后SHA复核见VALIDATION.json。
