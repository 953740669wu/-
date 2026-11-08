# M23 HBM 续跑实际命令

运行在原 M23 独立目录下的 `ubsan_hbm_continue_20261108`。原批次资料和 Git 清单只读。各轮 `M23_RUN_BINDING.json` 记录原授权已用量、剩余排队、绝对截止、原生 dsub argv、冻结包、源码、比较器所用数据描述及依赖身份。计算端每域 38 核获配、36 核计算、2 核保留。

## 私有依赖

在 Windows 本地工作区用 `curl.exe --proto '=https' --fail` 下载官方 RPM 与公钥，SCP 上传本轮远端 `deps/`。登录端通过 SHA256 后在该私有目录执行以下命令。

```bash
mkdir rpmdb extract
rpm --dbpath "$PWD/rpmdb" --initdb
rpmkeys --dbpath "$PWD/rpmdb" --import RPM-GPG-KEY-openEuler
rpmkeys --dbpath "$PWD/rpmdb" --checksig --verbose libubsan-*.rpm | tee signature.txt
(cd extract; rpm2cpio ../libubsan-10.3.1-66.oe2203sp4.aarch64.rpm | cpio --extract --make-directories './usr/lib64/libubsan.so.1.0.0')
sha256sum extract/usr/lib64/libubsan.so.1.0.0
readelf -h -d -V extract/usr/lib64/libubsan.so.1.0.0
ldd extract/usr/lib64/libubsan.so.1.0.0
```

签名、ELF、依赖与具体 SHA 见 DEPENDENCY_PROVENANCE.md 和各轮 `received/job_evidence/dependency/`。

## 登录端、编译和作业

使用原已核验的 C2 主机密钥池。每轮在独立目录内对上传的绑定与包执行 `sha256sum --check --strict`，再 `unzip -n -q M23_PAYLOAD.zip`。首轮上传包与绑定，四域后续轮只上传绑定并从首轮私有目录逐字节复制同一包。登录侧执行 `/usr/bin/python3 -B prepare.py "$PIN"`，用原 C2 venv 运行 `inspect_metadata.py --output LOGIN_METADATA_CHECK.json`，然后 `/usr/bin/python3 -B recheck_fixed_inputs.py > FIXED_INPUTS_BEFORE.json`。唯一提交入口为 `nohup /usr/bin/python3 -B submit_once.py "$PIN" </dev/null > login_submit.log 2>&1 &`。它保存原生 argv、提交 marker、作业 ID，并在 RUNNING 时发布 CPU/内存调度收据。实际提交和隔离参数见 `received/submission.command.json`。

- 单域 DDR request=limit 24576 MB，原生 `numa[count=1,distribution=pack]`，墙钟 1500 秒。四域 DDR request=limit 98304 MB，`numa[count=4,distribution=pack]`，墙钟最多 1800 秒。实际 CPU 及同 die 拓扑取自 `domain_map.json`。原 00 换到 cn21341 后，四域明确排除 cn21340、cn21341。
- 原 UBSan 正负控和 C50 用 `-fsanitize=undefined -fno-sanitize-recover=all`，加私有 `-L` 与 RUNPATH。验签库和实际 ldd 路径另有证据。正常训练库由 `/usr/bin/cc -std=gnu11 -O2 -fPIC -shared -pthread -Wall -Wextra candidate/hbm_alloc.c -o build/libhbm_alloc_s03_round2.so` 构建，具体绝对 argv、版本、输出、二进制 SHA 见 `s03/linux_evidence/`。
- 实际真实探针编译/运行 argv 和结果见 `job_evidence/real_hbm_node*/`。训练以同域 `numactl --physcpubind=<获配38> --membind=<DDR节点>` 启动，由 CPU36 守卫在 Torch 导入前收窄。仅 HBM 侧的 Python 子进程加载私有 allocator，普通分配仍绑本域 DDR。性能阶段两个版本均用 CKPT0，观察 6–25 步。
- 严格 DDR/HBM 进程独立。DDR 把每步严格张量写入本轮私有临时快照并记录 SHA，HBM 校验快照身份后用原比较器逐项对照；原历史 loss、数据顺序、掩码与初权重仍逐轮检查。严格快照在进程清理后删除，保留张量摘要及完整比较原件，不复制权重到回传包。快照 I/O 不计入性能阶段。

每轮终态后执行 `djob -J -l <job> > djob_final.json` 并复验固定输入。用本目录 `collect_evidence.py` 作为 Python 标准输入封存原件，下载 ZIP 和收据，运行 `python -B analyze_hbm.py <本轮目录>` 复核 SHA、数值、配对、驻留和速度。源包、依赖 RPM、二进制及 ZIP 留在独立证据目录。

首轮预部署入口检查发现 shell 条件中的变量转义错误，提交前已修复。原未提交包、绑定和入口差异见 `HBM_R1_20261107T170010Z/predeploy_unsubmitted/` 和 `PREDEPLOY_REPAIR.diff`。实际候选 C 与原 S03 R2 候选逐字节一致。
