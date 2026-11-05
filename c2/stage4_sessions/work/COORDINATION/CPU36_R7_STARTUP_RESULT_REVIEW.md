# R7 CPU36 有限完整启动：总协调复核

日期：2026-11-05。决定：**ACCEPTED_BOUNDED_CPU36_MODEL_STARTUP_EVIDENCE**。

## 已接受的范围

总协调独立核对S00回传证据并在独立临时副本重放R7汇总，通过本次单域36核模型启动/运行合同检查。不是只接受S00报告中的PASS字符串。本聊天没有另行SSH、提交作业或运行模型。

- 作业2034247、cn21340，调度SUCCEEDED、exit0；申请38核单域，实际选0–35、留36–37，24576MB及同值调度内存限制，900秒上限。
- 完整证据包SHA256为cf5db0ce6ac812c719b5879e26c68955f26fbfa23154a6bea96f31962bcb9755；54文件均与ZIP/清单一致，哈希、字节数及原mtime_ns元数据完整。
- 接受的原R7 ZIP SHA256仍为288a74181c36ec87b3953be5cde7e26575e45c219e9f446a21fca0683659119c；11个成员与实际回传payload逐字节一致。旧失败/诊断证据身份未变。
- 16_adjacent pre+dec、B32、fp32/KML、CKPT0三轮REPS1完整，各轮模型exit0、无超时。同job预检PASS_IMPORT_ONLY，主机/作业与模型一致。
- 每轮6个checkpoint，共18个；框架初始化后Torch intra-op均36。父监测571/547/565份，共1683份，全部采样完整、TID掩码非空且属于选中36核，无越界或消失线程记录。调用线程[0]按真实值保留。
- 独立临时副本仅按真实远端mtime_ns恢复时间，最大Windows舍入90ns；原样R7 summarize返回PASS，所有轮次指标及spread与远端一致。received原件未改。

描述性短测pre约21.61–22.25 fps、dec约8.48–8.59 fps，三轮波动约2.96%/1.24%。单域REPS1和LEGACY_TIMING_ONLY输入只能支持本次有限启动检查，不能作为正式速度、长期稳定性、科学数值/效果或训练内存收益验收。没有同配置参考/候选加速比；旧peak_mem_GB字段不是规范配对内存测量。

可机器核查的总协调结果在CPU36_R7_STARTUP_RESULT_REVIEW.json；来源为S00/CPU36_R7_STARTUP_REPORT.md及S00/evidence/r7_cpu36_2034247。

## 下一步

S01补充针对同一份真实证据的运行器专项复核；其报告尚未收到，不冒称双重审核完成。无需再提交同配置启动job。

S02可立即并行准备36核同PID包装和一组C2/KML严格数值对照。具体任务见R7_PASS_NEXT_S02.md；实际提交前补齐S01无阻断问题结论，并核验S02新包。此次接受不解除原S02数值FAIL，不接受训练内存/HBM/四域/整节点/DDP或生产部署。
