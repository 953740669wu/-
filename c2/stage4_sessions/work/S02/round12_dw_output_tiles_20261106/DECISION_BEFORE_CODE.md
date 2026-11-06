# R12唯一方案与预先声明的筛选

源R11 job2049454/cn21338绑定记录已核SHA。目标dW每步12次，A[13312,512]、B[13312,2048]，输出[512,2048]，RowMajor/Trans/NoTrans，alpha1/beta0，lda512/ldb2048/ldc2048。此处为FFN第二线性层的权重梯度g.T@x，不改forward/dX/bias。

唯一方案：只匹配CPU/fp32/已加载KML/contiguous输入、ta=True/tb=False/out=None/beta0/acc32False和精确(m,n,k)=(512,2048,13312)。新C仍为一次分配的最终contiguous[512,2048]；列0与1024分别直接调用_sgemm，n均1024、k均13312、A指针不变、B/C指针分别加0或4096bytes，lda512/ldb2048/ldc2048均保持。不创建子矩阵contiguous副本、不拆K/有效batch、不做部分梯度累加、不缓存权重。

边界：第二块最后B元素=(13312-1)*2048+1024+1023=13312*2048-1；C最后元素=(512-1)*2048+1024+1023=512*2048-1。两块输出列互不重叠；ptr须至少4byte对齐；新C存储不alias A/B。其它shape/flags/out/精度全部走原路径。原_sgemm ABI、alpha/beta/转置含义不改。

预先计数：baseline逻辑149/native149/target12；candidate逻辑149/native161/target12，两块native24。恢复小batch K=416不触发。计数都显示，不把两次native隐藏成旧149。

风险：完整K并不保证库使用同一累加/舍入实现；两次调用可能重复打包或变慢。必须用原tensor/state/exact比较器，首次ABI或本地数值FAIL保留并关闭本方案，不改块宽、fixture尺度或阈值、不换方案搜索。实际KML不在本地，native替身通过也不能称KML通过。

编码前固定检查次序：①目标完整地址/ld/列边界、guard canaries和调用次数；②其它输入fallback、对齐和alias拒绝；③完整目标形状native-CBLAS替身输出；④目标线性forward/输入梯度/dW/bias梯度；⑤连续5步原AdamW参数/delta/状态。failfast，首次失败即结束。

数值夹具预定：seed2026；独立目标A/B均randn*0.01；线性x=randn*0.05、w=randn*0.01、bias=randn*0.01、上游gy=randn*0.001。AdamW目标参数初值randn*0.01，使用同一目标A/B在5步分别乘固定1+step/100的梯度，不重置状态。夹具与真实语料分开，既不生成真实输入也不宣称覆盖所有数值分布；真实数据的完整Encoder严格5步仍须C2。

本轮不执行集群/不默认集成。通过本地必要检查后仅交同节点总900秒提案：实际KML目标筛选→完整Encoder严格5步配对→独立新进程baseline/candidate各25更新，前5预热后20观察，总完整模型最多60更新。预算不足INCOMPLETE、不缩步续跑；原源/CPU/库/数据/诊断/保存恢复保留。
