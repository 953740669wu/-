# S07 R2：当前作业身份修订接口

状态：READY_FOR_REVIEW / LOCAL_ONLY / CLUSTER_NOT_RUN。只准备修订，本轮不申请或执行两域作业。

## 本轮接口变化

使用本轮 `candidate/`，不要执行R1旧探针。原R1完整交付（17项文件及原SHA清单、当时状态/增量）逐字节保留在 `evidence/R1_snapshot/`；原接口见其中 `INTERFACE_FOR_S00.md`。

- 父入口 `load_allocation` 在读取allocation后、核对CPU或启动worker前，要求现场环境 `CCS_JOB_ID` 非缺失且非空白，并与配置 `job_id` 字符串精确相等。
- 每个worker读取manifest后、访问CPU或调用任何Torch导入入口前，分别核对 `manifest.job_id` 和 `manifest.allocation.job_id` 都等于worker现场 `CCS_JOB_ID`。缺字段、空值、旧号或两层不一致均抛出ValueError并非零退出。
- `CCS_JOB_ID` 必须由当前调度作业现场继承；不得从JSON复制、手工伪造或用旧job号补环境变量。S00仍需对照原始调度证据人工核验实际作业号和CPU授权。
- 没有新增CLI参数。allocation模板、逐rank CPU36授权/调度原件及SHA、固定张量/身份、故障接受条件和有界清理均沿用R1。`environment` 子命令仍仅检查导入能力，不是作业身份或通信通过。

## 复核与将来的S00命令

当前只允许离线标准库检查；下列路径指向本轮完整副本。已有PyTorch环境路径及来源核验按R1接口，不安装或替换软件。

```bash
export S07_RUN="/实际新隔离目录/S07_R2"
export S07_PY="/home/share/dengqingtian/opt/stage4_sessions/S00/ENV_20261104T130730Z_R4/venv/bin/python3"
export PYTHONDONTWRITEBYTECODE=1
"$S07_PY" -B -c 'import hashlib,json,pathlib,sys; b=pathlib.Path(sys.argv[1]); d=json.loads((b/"SOURCE_MANIFEST.json").read_text()); bad=[x["path"] for x in d["delivery_files"] if hashlib.sha256((b/x["path"]).read_bytes()).hexdigest()!=x["sha256"]]; print({"sha_mismatches":bad}); sys.exit(bool(bad))' "$S07_RUN"
"$S07_PY" -B "$S07_RUN/tests/test_job_identity.py"
"$S07_PY" -B "$S07_RUN/tests/test_probe.py"
```

身份检查使用模拟环境/CPU/框架入口替身，不调用Torch；原回归仍包含标准库子进程退出/截止时间检查。本轮Windows实际结果：新增6项通过；原16项15通过、1项Linux组清理跳过。不是Linux作业身份现场验证或Gloo通信验证。

**以下通信命令仅供修订核验后另行授权的两域job，本轮不得执行。** 在该job内按R1核验实际环境，保留现场CCS_JOB_ID及原始调度证据，从模板另存 `allocation.json`，其中job_id须与现场精确相等：

```bash
"$S07_PY" -B "$S07_RUN/candidate/run_checks.py" --allocation "$S07_RUN/allocation.json" --output "$S07_RUN/checks_current_job"
```

若现场变量缺失/不符，父入口写FAIL摘要且不启动worker；若worker继承的现场身份不符，worker在CPU绑定/Torch导入前退出，原监督器按既有故障判据清理。单凭非零仍不能算故障注入检查通过。

资源边界保持：单节点两个不同授权38物理核域，rank0=A0→其域前36核、rank1=A1→其域前36核，各留末2核；A0∩A1为空，逐CPU列表来自该job授权原件，不复用单域allocation。总24GiB、≤300秒仍只是方案；本轮无76核两域授权/申请/实际job。

保留完整回传：实际命令/环境/CCS_JOB_ID、原始调度分配及终态、allocation、manifest、两rank JSON/log、summary/checks、bytes/SHA/原mtime。固定张量/故障判据不变，正式全局batch、学习率和schedule仍待定；真实通信、训练和性能全部未运行。
