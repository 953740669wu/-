# S01夜间专项审核范围

仅核 ENGINEERING_REAL_CORPUS_PILOT_V1 的具体冻结交付；缺就绪依赖时不发布PASS。

1. 接口、代码包、源码清单、descriptor、部署包路径/bytes/SHA一致，读取前后无漂移；原R8正式门禁文件保持原身份。
2. manifest精确为本卡14300版；至多2个case、各8个16_adjacent单元、合法完整NPZ/sidecar，同belt/unit/row、base_of_pair/states、参考均值归一化*100，训练样本image scale一次拟合。
3. 显式engineering_only/UNKNOWN split与subject/无val；暴露记录selected与consumed区别，失败仍保留，后续subject追溯排除最终test。
4. 完整原Encoder、fp32/CKPT0/native SDPA/KML、mean双loss/连续AdamW、新mask、多batch、一epoch或200更新，不用demo，不额外更新恢复。
5. 必要检查覆盖实际改动，必要疑点仅做小型独立检查，不跑完整模型或旧矩阵。
6. 唯一job：单节点单NUMA38/实际36预留2、24576MB同limit、exclusive、900秒；全入口840+清理30+收尾30、唯一提交标记、全部自有后代清理和完整失败收集；Linux未验部分列作唯一job实际验收项。
7. PASS仅在四类就绪文件齐备后绑定精确身份；否则FAIL/BLOCKED明确定位，不更改作者源，不授权第二job。等待依赖至REVIEW_PROGRESS期限，每30—60秒查固定文件，不占计算节点。

尚未出现作者就绪文件，当前只是审核计划，不是放行记录。
