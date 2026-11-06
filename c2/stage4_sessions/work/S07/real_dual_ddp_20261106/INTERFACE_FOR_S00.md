# S07真实双域DDP固定交接

先读INTERFACE_READY.json；冻结交接以TRAINING_READY.json为准。新包package/S07_REAL_DUAL_DDP.zip，具体bytes/SHA/文件数/检查数由后者及SOURCE_MANIFEST绑定；S02必须是reference_binding.json指向的唯一冻结包。S02 REFERENCE_READY.json作原字节sidecar传入，不修改其中Windows路径；运行时另传真实Linux reference-root，18个相对文件逐一校验。只允许一个baseline/kml_ops实例。

## 本轮本地停点（必须读）

Windows/Torch2.7.1实际autograd图、空local mask、独立RNG、输入梯度缩放已核；TCP两rank梯度逐项一致/清理通过。进一步完整B64小模型对照按原阈值出现FAIL：val.weight、pos.weight相对9.410191e-5，tf.weight绝对3.723800e-5/相对1.142869e-4。13项中3项未过，原始度量/失败日志保留，没有放宽或删测试。输入梯度缩放及两个head梯度等其余项过，不据此宣布数值过。该本地native Windows结果不能充当C2/KML结果；S01必须在具体版本审核中明确处理这项失败，S00不得把早期小通信PASS或旧LOCAL_CHECKS当放行。

默认Python无Torch；已有只读S02 venv为Torch2.7.1+cpu/NumPy2.2.6。原FileStore本地25秒截止、沙箱TCP10013/10049失败保留；同一TCP检查在沙箱外有界运行后到达backward，两rank梯度一致。没有提升集群权限、安装依赖或提交job。严格小B64配对失败后停止此诊断，不换fixture/参考/阈值。

## CLI与共享起点

```bash
"$S07_PY" -B "$S07_RUN/candidate/train_ddp.py" run \
  --config "$S07_RUN/training_config.json" \
  --allocation "$S07_ALLOCATION" \
  --reference-root "$S02_REFERENCE_ROOT" \
  --reference-ready "$S02_REFERENCE_READY" \
  --descriptor "$S02_ENGINEERING_DESCRIPTOR" \
  --output "$S07_OUTPUT" \
  --job-start-ns "$JOB_START_MONOTONIC_NS"
```

JOB_START_MONOTONIC_NS来自本次job的公共起点，不能在调用S07时重置；训练、环境/所有检查合计到起点+840秒截止，清理+30、收尾+30，总900。训练PG120；前5严格B64门槛，过才接着第6—25步。退出0仅表示全部25步/5门槛/状态同步/恢复成功；1为失败，124为公共截止。原R7四case不重复。

## 本地/现场检查

四文件实际19方法：test_contracts.py=7、test_lifecycle.py=6、test_result_identity.py=4、test_training_torch.py=2。Linux必须19过零skip，且S02原7方法及一切前置仍共享840秒；不能仅看unittest退出0而忽略skip。S07 Windows最终为17过/1原数值FAIL/1 Linux后代清理skip。默认无Torch解释器的两个skip不能替代已有环境实测。

```bash
export S07_TEST_ALLOCATION="$S07_ALLOCATION"
export S07_REFERENCE_ROOT="$S02_REFERENCE_ROOT"
export S07_REFERENCE_READY="$S02_REFERENCE_READY"
"$S07_PY" -B "$S07_RUN/tests/test_contracts.py"
"$S07_PY" -B "$S07_RUN/tests/test_lifecycle.py"
"$S07_PY" -B "$S07_RUN/tests/test_result_identity.py"
"$S07_PY" -B "$S07_RUN/tests/test_training_torch.py"
```

这些是自建短子进程的数学/退出检查；不运行训练故障case、不给真实训练注入失败。Torch检查的父不导入Torch，两子进程在Linux各先核原生job和对应域绑核，再导入；测试父必须继承本次两域完整授权，不能先taskset到rank0而使rank1超出继承。Linux小检查固定file://，Windows小检查显式TCP，无自动fallback。实际训练始终Linux file://，PG120不变。

## 原件收集

收manifest/participants/ready/rendezvous、两rank正式JSON/steps/events/log/exposure、reference.exposure、gate_metrics、supervisor事件/summary、checkpoint_index、环境/API/库/KML计数、CPU/数据/源身份。rank.json只代表最后原子提交的完整状态；缺/空/残/旧身份仍FAIL。阶段NOT_RUN/IN_PROGRESS/FAIL_OR_INCOMPLETE原样，失败时不要补造完整25步。

保留隐藏`.rank[01].json.*.tmp`以及其它`.json.*.tmp`、exposure临时文件、原始空/半份日志的路径/bytes/SHA/远端mtime，不把temp当正式rank报告。任何`.pt`、`.pt.tmp`及其它可能包含模型权重的文件均留远端，回完整/部分checkpoint的路径/bytes/SHA索引；不能因后缀.tmp就下载大权重。取两rank原state_identity而不是比较包含rank身份的整个checkpoint文件。

前5/后20训练时间、参考共存HWM、恢复重复前向与实际训练/参考更新/独特帧分列。S00接新TRAINING_READY准备外包，S01对内外包/参考/数据/config/本卡具体SHA最终结论后按卡处理；不自动重试/补跑/延预算。S07无job，C2完整模型DDP/严格五步/25步/恢复均NOT_RUN。
