# 今晚S02工程入口交付

仅ENGINEERING_REAL_CORPUS_PILOT_V1。原R8正式入口和门禁不变；无正式划分/subject映射，无val/test、无泛化结论。INTERFACE_READY.json已先行发布，接口不可热改。

S00将冻结包按SOURCE_SHA256.json逐项核SHA，解压到自己本轮远端目录的payload。不要安装环境，不改变已有KML/OMP/shim路径。ENGINEERING_DESCRIPTOR.json字节必须与DATA_READY.json、S01专项复核绑定的SHA一致；descriptor内runtime_exposure_ledger_path必须是这个payload/outputs/EXPOSURE_LEDGER.json的新路径，初始暴露清单不得覆盖。

以下为分配到计算节点后、S01 PASS_FOR_ENGINEERING_PILOT绑定同一交付后的唯一应用命令；本文件不含提交指令，调度/唯一标记/后代清理/收集由S00部署包装负责：

```bash
export S02_ENGINEERING_DESCRIPTOR=/home/share/dengqingtian/opt/stage4_sessions/S00/ENGINEERING_PILOT_20261105T154333Z/ENGINEERING_DESCRIPTOR.json
export S02_ENGINEERING_DESCRIPTOR_SHA256=b88ea9745147acf7fa70d51dc27c727f22f14e98af5dff1b80a9047e95648cd6
bash /home/share/dengqingtian/opt/stage4_sessions/S00/ENGINEERING_PILOT_20261105T154333Z/payload/run_engineering.sh
```

S00应先在登录侧仅运行标准库元数据/哈希门禁（不会读取NPZ数组或导入框架），保留输出作为部署检查；此检查会读固定所选文件以核SHA，不训练：

```bash
/usr/bin/python3 -B /home/share/dengqingtian/opt/stage4_sessions/S00/ENGINEERING_PILOT_20261105T154333Z/payload/inspect_engineering.py \
  --descriptor "$S02_ENGINEERING_DESCRIPTOR" --descriptor-sha256 "$S02_ENGINEERING_DESCRIPTOR_SHA256" \
  --output /home/share/dengqingtian/opt/stage4_sessions/S00/ENGINEERING_PILOT_20261105T154333Z/engineering_metadata_gate.json
```

资源：单NUMA38分配、36实际物理核、预留2；exclusive；DDR请求和limit均24576MB；作业900秒，全部入口timeout840秒、kill-after30秒、余30秒收尾。OMP36/MKL36/OpenBLAS1/cores/close。原同PID守卫先绑定后导入框架，在初始化、每步前后、保存、恢复及发布时核实际Torch36/OMP36和全部TID。调用线程允许单核绑定。保留实际KML库路径/SHA、GEMM计数与线程边界证据。

数据：manifest按任务卡14300版SHA核验前后，所有单元固定，seed2026选择和文件SHA再次核验；变化SOURCE_CHANGED停止，不换样。按同unit/belt/pair/base_of_pair与states配对，参考mean(abs(v_ref))*100原算法；仅工程train图像absmax拟合一次。无正式val，也不调用evaluate。完整Encoder37995777参数/fp32/CKPT0，原native SDPA与KML linear，原mean双loss和AdamW完全复用。seed0只打乱一次，batch64、不重复补尾、1epoch或200更新先到；当前1600帧规划25步，720秒后停止新步以预留保存/恢复。

暴露：初始清单SELECTED_RESERVED/NOT_STARTED；运行清单在模型前创建，读取前LOAD_ATTEMPTED，读取后LOADED_FOR_ENGINEERING_TRAIN_STATISTICS；每次forward前持久化frame IDs为POSSIBLY_USED_IN_INTERRUPTED_UPDATE，核梯度/AdamW/CPU和落步日志后CONSUMED_CONFIRMED。恢复探针另记录前两帧及0更新。异常时保留原清单/运行清单/日志，不把已选等同已消费。未来按真实subject追溯并排除工程暴露受试者的最终测试；当前不能保证未碰未知测试对象。

必收集：outputs/engineering_JOBID全目录（result.json、steps.jsonl、stdout_stderr、退出/timeout、CPU分配与命令、checkpoint/final.pt身份和恢复结果）以及payload/outputs/EXPOSURE_LEDGER.json。checkpoint权重仅远端保存，不进Git。result中的RSS峰值为process_lifetime；计时拆分读取/批物化/训练/诊断/保存恢复/未归属，不能当稳态性能或优化收益。失败/INCOMPLETE立即停止，不重试、不扩资源；缺Linux证据仍须由这唯一作业实际检验。
