# S00 远程核查摘要

日期：2026-11-04。状态：REMOTE_VERIFIED / HISTORICAL_RECOMPUTED / NEW_CLUSTER_BENCHMARK_NOT_RUN。

已按用户明确授权保存限定证据。数据来源为evidence/remote_details.json、remote_context.json及remote_launcher_latest.json；前两次审批事件及授权解除过程在approval_boundary.json，不是当前阻塞项。完整辅助/环境源码和完整日志未传回；后续收紧为摘要、依赖哈希与输入统计后成功完成。

- 账号dengqingtian、节点10.44.9.4、落点login10，项目/home/share/songzhenlong/eitfm可读不可写。密码未落盘，未新增密钥或修改全局SSH配置。所有SSH会话正常退出。
- 生产manifest核查11900单元、1190000对、119个case，代码/配置标识与预期一致，SHA256见remote_details。生产s2/s3/s6与本地同SHA；s1指定位置缺失或不可读。manifest的finite/status字段是原记录，不代替所有样本的独立检查；真实subject split仍缺。
- /usr/bin/python3为3.9.9、aarch64，当前账号通过共享torch_kml能找到torch2.7.1+cpu分发元数据，同一调用未找到numpy分发元数据。没有import torch或验证实际KML/OMP加载。当前账号环境不能自动继承项目拥有者的私有环境。
- 登录节点gcc10.3.1及clang等命令存在，不能作为计算节点SME/内存环境验收；本次没有训练、微算子或编译性能实验。
- 调度器与q_hpcai已确认。17:00快照当前账号有2024892/2015576两个运行作业，均非S00作业。查询songzhenlong作业返回Permission denied；login10只看到其T/Ts/Z状态python进程，不据此推断计算节点是否空闲。

## 源码版本

归档启动器a21a…保存在baseline。17:00副本ea27…增加sample_foreign采样、CORES_PER_DOM上限及wait指定PIDs；17:07结束检查发现共享文件已变，17:09再次取回0da6…，其差异仅为启用PYTHONFAULTHANDLER及扩大故障grep关键词。最后快照读前后SHA稳定；不能承诺共享路径之后不变。

两个远程快照的Python汇总段均与归档逐字一致，本地检查证明缺域/旧JSON的误报仍适用。新版本虽扩展了日志诊断，仍没有逐PID退出码、完整域门槛、三轮门槛、配置/时效身份校验或内部barrier故障传播。未修改原代码，交S01处理。

sample_foreign.py只记依赖SHA256，不含正文；模型、KML、HBM/shim源码与归档一致。共享HBM/shim .so哈希已记，不代表历史运行时哈希已知。

## 输入与历史计时

两个frames.npz各9342516字节、各2帧，训练字段finite且分母非零。images是float16[2,64,64]；电压为float32[2,208]/[2,928]；J为float16[208或928,4096]，未做J全finite扫描。payload哈希确认两处demo images都来自32电极源单元，且与16电极源单元不同。这是已证实的目标对齐问题，S00不改样本，仅保留历史计时语义。

135份原逐域JSON内容、SHA256、mtime和有限日志摘要已经保存。重新计算540条域测量、48条轮次/工作负载记录，详细数值见remote_measurement_table.md：

- B64 preferred：47/48份JSON，第2轮d4缺失，四项工作负载该轮均无效；完整域只剩第1/3轮，不能保留三轮稳定性PASS。
- DDR B32：48/48份JSON，三轮payload波动0.550%/5.607%/4.642%/2.995%，16-dec未过5%。无逐域退出记录及运行时输入/库冻结，不能正式接受其余三项。
- HBM B32：32/32份JSON仅两轮，波动9.387%/4.059%/2.338%/1.402%；均未满足三轮门槛。
- DDR B32整节点来自cn21348，HBM B32来自cn21338，不是同主机配对；四域DDR/HBM同为cn21338，但只有一轮，DDR有慢域。
- 32-pre合计约21fps掩盖慢域；DDR B32第2/3轮最慢step约214/226秒，16×min只有2.394/2.266fps。独立进程合计不是DDP吞吐。
- 旧B64 CKPT HBM共32日志、0 JSON；摘要证实SIGBUS及约3小时runner等待，DONE不能证明成功，归S01复测。
- HBM arena/累计申请/bump高水位不能冒充实际驻留或带宽；RSS不含全部hugetlb。没有本次实测峰值。

## 交接

建议接受源码和证据交接，性能及科学正确性未验收。S01先接受运行器；S02须明确输入目标协议和固定有效batch；S06须核实当前账号依赖与计算节点工具链。计算资源尚未分配给S00，未提交新作业、未创建远程候选目录、计算节点小时为0。后续资源排期见RUNBOOK和REPORT第6节。
