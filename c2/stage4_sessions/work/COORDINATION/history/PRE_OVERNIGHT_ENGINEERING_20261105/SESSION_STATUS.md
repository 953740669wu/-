# 总协调简短状态

- 更新/轮次：2026-11-05；REALDATA_AUDIT_R8_REVIEW。
- 用户决定：优先冻结语料实际样本小训练、边跑边优化；确认corpus_shape_20261102且只用已有正式受试者划分，不允许新工程split。单域训练不依赖05 C ABI或07通信全部通过。
- 本轮依据：优先读00/02最新短状态/六行摘要；因数据阻塞及新包核必要S00审计与S02报告/核心读取、训练、恢复及包装源码。未重读全部历史、未重跑19项或旧5315。
- 数据现状：00现场审计corpus_shape_20261102/manifest.csv现14300单元/143万对/143case，SHA=bdd146040bddf2ddd47fb9d571d5d2f40e5fa20fbd30d0c0d11239893e647032；原11900版增加2400单元/24case，code/config相同不能代替冻结身份。数据存在，非样本读取/物理数值验收。权威split/subject映射未找到；用户答不清楚路径。
- 真实小试范围：16_adjacent encoder pre原模型/mean/AdamW、fp32/CKPT0/KML/HBM0；train最多2subject×8units，正式val存在时最多1subject×4units；batch<=64、1epoch/200更新先到，38/36核、24GiB、单job900秒。
- 输出/停止：变化真实batch与mask、逐步两分量loss、正式val前后（如有）、checkpoint/恢复核验/数据清单；finite/身份/梯度/资源失败停，loss短程波动只报告。不称decoder/最终科学效果/正式性能收益。
- 新交付核对：S02 R8 ZIP=54204字节，23文件逐项大小/SHA/ZIP原字节一致、CRC/3.9 AST通过，SHA=fe322692aa68b93c78c10fc12e06e26ffdb6b54b4775cae3f8c24422cbd40d95；19本地检查按作者记录，尚不作C2/真实数据验收。只更新协调状态/证据，不改作者代码或来源。
- 下一步：先明确冻结语料版本和已有正式split/subject映射；仅按新线索追溯来源，不重复846路径扫描。不清楚不等于允许新建划分/接受新版；02保持R8待命，数据齐备后再核实际描述与部署。真实NPZ读取/训练job仍0，root无远端提交。
- 其余/Git：READY_R5_FP32_R3历史批次716文件已普通推送GitHub（Git窗口实时核远端）；协调只读核本地HEAD/origin追踪均0e6e4c8923587d364a97fa2904d06ffd3de18fed、暂存空。该归档的P1尚未实现/R5未实跑是历史边界，不覆盖后续P1否决/R5实跑FAIL。清单外47项及后续新成果另审，不自动提交。
- 主线不变：05/07已有成果保留后置，01/03/04/06/08不扩；新训练输入版本REAL_CORPUS_PILOT_V1、train-only统计与原demo分账；新交付核验后提醒唯一Git窗口归档源/配置，数据/权重保持忽略。
