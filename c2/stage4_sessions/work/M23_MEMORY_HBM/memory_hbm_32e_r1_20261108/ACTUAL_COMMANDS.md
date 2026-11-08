# 09 真实 32 电极执行记录

## 固定输入与模型

原始语料 `/home/share/songzhenlong/eitfm/corpus_shape_20261102`。登录端在 09 私有根执行 `/usr/bin/python3 -B freeze_data.py`，核实原 manifest 与 119 工程候选 cases 文件 SHA，从 7,150 个真实 32_skip4 单元按 seed 2026 固定 2 个 case、各 4 个单元，每单元 100 帧。独立 descriptor SHA256 为 `2d9ef2f224a7b2f2fb2848c4ec39274fe9466ab2f2aaef4757bc35608e1ebe4a`。原始 NPZ 不复制，八个 NPZ 与 sidecar 的 bytes/SHA、array headers 及来源在每轮回传的 `ENGINEERING_DESCRIPTOR.json`。登录端逐项核验 int16 drives/meas 的实际顺序和形状。目标端原加载流程核实 `base_of_pair`、sidecar states、有限性、ref 分母、voltage dtype、images 后做归一化。

原 Encoder 入口源码保持字节相同，12 层、width 512、8 头、FFN 2048，模型输入是 32 电极偏移 5、928 tokens，32 电极 belt 标志为 1。B32 整批，fp32，原 masked mean voltage MSE、coarse image MSE 及 AdamW。真实模型 init/mask seed 0，首轮 DDR strict worker 从实际 32E 生成 `PAIRING.json`，包含初态 SHA、协议角、归一化、800 帧顺序及 25 个掩码 SHA。后续轮绑定这个原件。比较器 SHA256 为 `e9b53136146c062b0817fd0bf63632ad6c8cde6daa8d862cf78ba10431024a3e`。没有使用 16E loss 或固定 16E KML 形状。32E DDR 的真实 SGEMM 签名逐步采集，并在同轮对照中检查。

## 提交与实测

通过原固定主机密钥池 SSH/SCP。每轮 `M23_RUN_BINDING.json` 和 `received/submission.command.json` 保留实际远端路径、队列、节点选择、资源、绝对截止及预算。首轮上传冻结包与绑定，复用轮在私有目录从首轮逐字节复制包和独立 32E 配对，上传独立绑定。登录端依次校验上传 SHA、`unzip -n -q M23_PAYLOAD.zip`、`python3 -B prepare.py "$PIN"`、`inspect_metadata.py --output LOGIN_METADATA_CHECK.json`、`recheck_fixed_inputs.py > FIXED_INPUTS_BEFORE.json`、`nohup /usr/bin/python3 -B submit_once.py "$PIN" </dev/null >login_submit.log 2>&1 &`。每轮提交前查原 00 活动节点，排除 cn21341 及当时活动目标。

- 原生独占 q_hpcai。单域 38 CPU 分配、DDR request=limit 24576 MB。四域 152 CPU 分配、DDR request=limit 98304 MB，实际同 die 4 个完整域。Torch 导入前每域绑定 36 核，保留 2 核。
- 重用 M23 已过 C50/UBSan 的正常构建，SHA256 `89f295754a199dcb6206f8e6217e6cf57651bceed2d364b1a6e4cc83eea6095d`。每轮只在私有目录复制，校验原件与复制件，检查 ldd 和训练实际映射。每轮复用真实 C 安全探针，现场核实本域池、触页、并发、策略恢复、精确复用、DDR 回退和页池归还。候选 C 初始 SHA256 `d1f5dbbfb6aa4a973dcc4d12607f62a8b2be5166690897dfd5ea35e067c7d7a2`。
- 每轮在独立 DDR strict 进程生成 5 个实际输出、梯度、参数更新与 AdamW snapshot。其它版本读严格 pin 的 snapshot，用原比较器逐项比较。快照在严格结束后从私有路径清理，保留其 SHA 和比较原件。每个性能进程完成 25 步，前 5 步预热。四域同一步对齐起跑，速度用最早开始到最晚结束的跨度。每步记录重置后的普通 RSS 高水位、步末 hugetlb、以及前后 NUMA 采样。
- 调度终态后重新核实真实输入文件 SHA，用 `collect_evidence.py` 在远端封存原件并生成回执，SCP 回传后用 `analyze_32e.py` 校验 ZIP、逐文件 SHA、门槛和实测对照。每轮保留分配原件、进程清理和页池归还证据。

## 实际调度终态

| 轮次 | 作业 | 域数 | 主机 | 终态 | 排队秒 | 分配秒 | 本轮完成更新 |
|---|---:|---:|---|---|---:|---:|---:|
| R1 | 2063215 | 1 | cn21379 | SUCCEEDED | 3 | 618 | 60 |
| R2 | 2063282 | 4 | cn21379 | SUCCEEDED | 2 | 1594 | 240 |
| R3 | 2063364 | 1 | cn21379 | SUCCEEDED | 2 | 1355 | 120 |
| R4 | 2063431 | 4 | cn21379 | SUCCEEDED | 4 | 2779 | 360 |
| R5 | 2063538 | 4 | cn21379 | SUCCEEDED | 2 | 2072 | 360 |
| R6 | 2063639 | 4 | cn21379 | SUCCEEDED | 2 | 2062 | 360 |
| R7 | 2063805 | 4 | cn21379 | SUCCEEDED | 4 | 2055 | 360 |

R1 冻结 32E 工程入口与独立 DDR 参考。R2 复用 CKPT0 包。R3 冻结 CKPT12 包，在单域比较四种配置。R4 四域比较 DDR/CKPT12 与两组 CKPT0。R5–R7 在同一节点按同一顺序比较 DDR/CKPT0、HBM/CKPT0 和 HBM/CKPT12。

逐步的输入帧与掩码、原数值指标、KML 调用和 NUMA/RSS 快照在各轮回传的 job_evidence 中。每轮原始 ZIP 及 bundle_receipt.json 保留逐文件身份。归档建议只选定新目录内的审阅材料，原始 ZIP 在实验目录留存。
