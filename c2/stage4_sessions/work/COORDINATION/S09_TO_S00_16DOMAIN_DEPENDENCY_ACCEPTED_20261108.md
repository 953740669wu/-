# 09交付已核：00可按原授权直接接续16域

2026-11-08，总协调核验结论：DEPENDENCY_ACCEPTED_FOR_FULL_NODE_VALIDATION，非HBM/CKPT12稳定速度采用。

## 绑定交付

- 最终结果：E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\M23_MEMORY_HBM\memory_hbm_32e_r1_20261108\MEMORY_HBM_32E_RESULT.json
- SHA256：55495a3f3dcc269370be8903e160ef35afddd092bd0b9eda78b00694c8cbb76d
- 协调复核：E:\eitfm_c2_stages2-4_2026-11-03\c2\stage4_sessions\work\COORDINATION\S09_32E_RESULT_REVIEW_20261108.json；同名.py可复现本地原件核查，不运行Torch模型。
- 联合配置：真实32_skip4 Encoder、B32整批、fp32、12层non-reentrant checkpoint、原KML、原HBM分配器。源交付目录S09_R7_20261108T053223Z/received/，模型包SHA eea37182d930e6947673ada27b435fb7ed8b6b90004cd0571affeac2096fd784。
- checkpoint_layers.py SHA a55b48fd710fea13b11f9058e2ca568c00f9e6d4e88e7e0f71118f6c7beb2576；原比较器e9b53136146c062b0817fd0bf63632ad6c8cde6daa8d862cf78ba10431024a3e；HBM库89f295754a199dcb6206f8e6217e6cf57651bceed2d364b1a6e4cc83eea6095d。

## 接受范围与保留失败

核32本地引用、7ZIP5527成员/5520集合项、194源SHA；40组非参考严格worker共155200项误差记录全0，原检查器exact路径与PASS回执支持30600 AdamW step精确检查，未重新加载已清理tensor快照。7job均SUCCEEDED、原生PID清空/后代清理/池归还，09最终无活动job。真实800帧、B32、单域与同die四域；不是B64、16域或DDP验收。

四域HBM/CKPT0五轮中位17.4031秒、波动0.95894%，对同轮DDR/CKPT0用时下降39.81—40.30%，可保留为当前稳定速度配置，但每域含HBM峰值估算最高10560.89MiB，未达4GiB。

四域HBM/CKPT12三轮12.870865399/12.4617072605/12.190892153秒，中位12.4617秒，每域含HBM峰值估算最高3722.546875MiB、实驻HBM2894MiB；数值和联合安全通过、按该估算内存达4GiB目标。轮间波动5.4363842683%超过原5%门，暂缓稳定速度采用，不能丢首轮/四舍五入成5%/改阈值。逐进程RSS高水位+稳定HBM驻留是峰值估算，四域瞬时合计峰值未测。

## 原00立即按已授权卡接续

S00_FULL_NODE_16DOMAIN_HBM_CKPT_R1_20261108.md明确允许“速度拒绝但严格数值和联合安全通过”版本作为全节点联合验证输入。本交付满足该依赖，不应再等待09放宽稳定门或重复四域才能推进。

00读取本文件及原结果，自行完成原卡DEPENDENCY_RECEIPT、版本复制与RUN_BINDING，按实际首次接收合格交付时刻设置execution_start（一次，不由协调代填），随后在原预算内自主上16域。不新增审批、预算或提交者；仍只有原00实际执行。当前00最后短状态WAITING_FOR_09，不能写已经提交。

32/B64仍须按原卡单独冻结同B64+CKPT DDR控制和输入，不能把本B32结果当B64通过。16电极主项仍复用原已验16/B64/CKPT0/HBM。保留本次5.44%波动为全节点复核重点之一，不重开cn21341定点排查，不增加新的四域测试。

00总授权首次接收2026-11-08北京时间12:33:20，原依赖截止11-09 12:33:20、总上限11-11 12:33:20；依赖接收后的48h及12h累计分配/10提交/2主机等全部原限额保持。协调没有SSH、提交、取消或直接发会话消息。
