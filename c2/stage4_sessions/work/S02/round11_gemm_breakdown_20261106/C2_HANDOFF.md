# R11未改基线KML调用分解：S00/01交接

顶层INTERFACE_READY.json及最终GEMM_READY.json为固定交接。先核所有path/bytes/SHA，再部署本包并核SOURCE_SHA256.json。只用原baseline SHA=e6c5c4411c453c8168939cd51d737a7e9d8232bdfff05da3967805a5e917ff26；没有R10候选、20更新A/B或新优化默认。

新协议ENGINEERING_REAL_CORPUS_GEMM5_V1；旧数据协议/descriptor及原数值门槛保持。顶层INTERFACE.json是新观测接口；为避免误改旧数据门禁，原engineering_data.py和原8b1b…接口字节一起放在data_gate/，入口显式从该目录导入。原descriptor SHA=b88ea9745147acf7fa70d51dc27c727f22f14e98af5dff1b80a9047e95648cd6不变，旧runtime ledger路径只读，新账本位于本次输出目录。

S00远端只新建`/home/share/dengqingtian/opt/stage4_sessions/S00/S02_GEMM5_<唯一时间>/payload`。本包无安装或调度提交逻辑；S00仍须按本轮任务卡准备原生job/NUMA/资源门禁、唯一marker、全链时限、所属后代清理及新协议收集，S01精确SHA绑定PASS后才执行一次。旧2043445/2048959/旧marker无效；S02不提交。

以下仅为审核后计算节点内的应用命令（占位目录由S00替换为新绑定目录）：

```bash
export S02_ENGINEERING_DESCRIPTOR=/home/share/dengqingtian/opt/stage4_sessions/S00/S02_GEMM5_NEW_REVIEWED_RUN/ENGINEERING_DESCRIPTOR.json
export S02_ENGINEERING_DESCRIPTOR_SHA256=b88ea9745147acf7fa70d51dc27c727f22f14e98af5dff1b80a9047e95648cd6
bash /home/share/dengqingtian/opt/stage4_sessions/S00/S02_GEMM5_NEW_REVIEWED_RUN/payload/run_gemm5.sh
```

可在登录侧仅用现有R4 Python运行inspect_engineering.py，核元数据/固定manifest/选择/文件SHA，不导入框架、不读取NPZ数组、不训练；输出须新路径。主包装在计算节点也先执行这个门禁。

资源：单NUMA38分配/实际36物理核留2，DDR24576MB同limit/exclusive、HBM0、job最多900秒；全入口840+kill/清理30+收尾30，内部720秒停新更新。OMP36/MKL36/OpenBLAS1/cores/close，沿用R4 Python/KML/OMP/shim与同PID全TID守卫，不设置interop。5更新完成即停，不安装、扩样、重试或跑满900秒。

完整Encoder/fp32/CKPT0/native SDPA/原mean双loss/AdamW不变；原1600帧用于train统计，B64/seed0原前320训练帧、5新mask、连续AdamW；核原init/scale/frame IDs/mask/KML149次数及15项原loss。保存/恢复沿用工程函数及旧工程checkpoint标签，identity绑定本次新源码/配置；额外更新0。无正式subject/split/val/test或效果接受。

第1—2步不挂观测，第3—5步分别临时包裹原counted gemm、原_sgemm及Linear两个调用点；参数原样调用一次，四处hook在finally恢复。训练结束、所有诊断/保存/恢复期间不挂hook。每步最多256条，必须149条完整一一对应；最多3份`gemm_step_N.json`，每份<=1MiB，写前检查、不截断。漏配/多配/不支持/超限或源/原loss/CPU/库失败即停，保留失败文件/账本，不切backend。

记录实际shape/stride/dtype/contiguous、ta/tb/beta、m/n/k、raw_sgemm标量参数、输出storage-alias布尔、线程/父调用及单调ns边界。role仅按已核Linear上下文与flags标forward/dX/dW，其余UNKNOWN。计时仅覆盖这149次直接kml_ops调用，不覆盖Torch内部全部BLAS。A/B是进入gemm时已准备的操作数，Linear前向reshape和bias预填在此边界之前，不能把本次差值叫完整Linear准备时间。ctypes wall含Python转换/库内部打包/调度/计算；外层差值含gemm内部准备/分配/计数与部分观测开销，不能称纯微内核或精确无观测准备时间。记录metadata前后及native-hook bookkeeping开销，Linear上下文/计时器成本仍非完全分离。跨线程/嵌套区间不可简单累加当程序wall；本轮不是A/B、吞吐或优化接受。

必收集`payload/outputs/gemm_JOBID`：result/steps/EXPOSURE_LEDGER、3份GEMM文件、CPU分配/库/命令/日志/退出/timeout、checkpoint身份和零更新恢复；另S00调度/资源/所属PID清理原件。权重仅远端留存，不下载进Git。成功必须5步/320训练帧/3份149条完整记录/原15 loss/CPU/库/源/恢复/清理齐；缺项不能PASS。失败也交可核身份的终态。RSS是process-lifetime采样HWM，不当内存测试或全job最终峰值。

本地测试`tests/test_gemm_observer.py`明确LOCAL_FAKE_CBLAS_ONLY；没有实际KML或完整Encoder运行。GEMM_READY只表示S02准备和本地必要检查完成，不替代S01审核或S00唯一作业的真实验收。
