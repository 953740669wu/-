# S06 R3：隔离负例测试修订

2026-11-05；LOCAL_ONLY / CLUSTER_NOT_RUN。本包从S06 R2原包派生，唯一既有文件变化为tests/test_probe.py中的test_isolation_requires_I_and_S；candidate/全部四文件、模型、环境参考、其它检查及README_R2.md逐字节不变。

负例改在明确不带-I/-S的独立Python子进程执行，断言非零退出及原始RuntimeError拒绝原因。原-I/-S隔离正例保持。此修订不放宽isolate，不改线程、清理或数值实现。

当前交付包为S06_R3_PAYLOAD.zip；解压到新的任意目录后，在payload目录检查：

```bash
sha256sum -c ARTIFACT_SHA256.txt
python3 -B -m unittest discover -s tests -v
python3 -I -S -B -m unittest discover -s tests -v
```

本地Windows两种启动方式各26项：23通过、3项Linux实际组清理/信号掩码检查跳过，exit0。不是52项独立检查；Linux三项尚未运行，也不代表实际Torch、C2、compile、卷积或性能通过。

README_R2.md保留线程/清理实现、旧来源和运行边界。其隔离检查命令现已在本地按原参数通过；旧包名仅属R2历史。本轮未连接或启动集群，也不因本文件授权新作业。仅交协调复核本R3包及SHA。
