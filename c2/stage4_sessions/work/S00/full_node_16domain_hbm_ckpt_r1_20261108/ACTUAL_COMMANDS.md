# 16 域全节点实际入口

依赖用 `python -E -s -B verify_dependency.py` 从冻结原件核验。实时查 `djob -J`、`djob -J -l 2063805`、各候选 `dnode -J -l`。09 与旧 S00 作业均为终态。首次全节点候选为 cn22035、cn22036、cn22044，排除 cn21341。

对每个版本使用冻结目录中的 `RUN_BINDING.json` 和包 SHA，使用本站已核 SSH 主机密钥上传。首次 A 版本登录端发现两处旧绑定文件名，`first_preflight.stderr` SHA256 为 `dea824545e2c6dad3403ad1be4eb24aab0535a0544a045dd36f4d30be27d0f77`；无提交 marker 或 job id。B 版本只修这两处并使用新远程目录。

```bash
source /etc/profile.d/donaukit_scheduler.sh
RUN=/home/share/dengqingtian/opt/stage4_sessions/S00/FULL16_R1_H1_32B32_B
PIN=4755126d673a01840ab76211c2a2d10c1c665a4e77857aed72f94602031afb53
PKG=904def960f2c08be24539f2bd978fce3f814bf78bc54e3cbaada3dd846b0fc28
cd "$RUN"
printf '%s  %s\n' "$PKG" FULL16_PAYLOAD.zip "$PIN" RUN_BINDING.json | sha256sum --check --strict
unzip -n -q FULL16_PAYLOAD.zip
/usr/bin/python3 -B prepare.py "$PIN"
timeout --signal=TERM --kill-after=5s 60s env -u LD_PRELOAD PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 /home/share/dengqingtian/opt/stage4_sessions/S00/ENV_20261104T130730Z_R4/venv/bin/python3 -B inspect_metadata.py --output LOGIN_METADATA_CHECK.json
timeout --signal=TERM --kill-after=5s 45s /usr/bin/python3 -B recheck_fixed_inputs.py > FIXED_INPUTS_BEFORE.json
nohup /usr/bin/python3 -B submit_once.py "$PIN" </dev/null >login_submit.log 2>&1 &
echo "$!" > login_submit_pid.txt
```

首轮实际 job 2064138，cn22035。原生完整 argv 随运行回收，并以每版 `RUN_BINDING.json` 绑定。本版为 608 核、393216 MB DDR 同限、16 NUMA pack、独占、7200 秒。未预提交任何后续版本。

2064138 成功终态，使用 `djob -J`、`getconf CLK_TCK`、固定输入复核、`/usr/bin/python3 -B collect.py "$PIN"` 及 `tar -czf JOB_2064138_TRANSFER.tgz JOB_2064138_evidence.zip bundle_receipt.json` 回收。传输 SHA256 为 `2dc302b3f35684799028897e046ba5b69f04a77e502e7fa6d4fae6fe2313bfa8`。所有计算进程已清理，16 域页池归还，第二轮因实测耗时和收尾预算延后。

下一配置为首主机 16 电极 B64/CKPT0，版本 `H1_16B64_A`，原生 2064626。包 SHA256 `abecb3de40f1edf0adecebe09671a2c8d980946dd41dd0f23587105b0a59e51e`，绑定 SHA256 `3c1ba3af6f43168a8996fb6aee7951900bce80d343f8853a2f5f8735d126428a`。同一登录入口和原生资源，首主机由 2064138 的实际获配确认为 cn22035。使用原 16 电极数值参考和最多三轮 HBM 25 步，本配置没有 DDR 25 步。

2064626 成功终态并已收集，传输 SHA256 `34c7eebb5386837fec6130fe677bc1c0f8b2001e55aca5e233494e67f0b44c4d`。第二主机候选 cn21762、cn22036、cn22289，排除 cn21341 和已执行的 cn22035。版本 `H2_32B32_A` 在独立目录逐字节复用已核的 B32 包和数据侧车，运行绑定 SHA256 `9d5530a6b6e04496812d95c28d50ec17c4aa585b5aae92ba2a813011da7165b4`。唯一提交 2064729，实际获配 cn21762。

2064729 成功终态并已收集，传输 SHA256 `dc854b9de1cfa31a1b2c408572bbbb1cfda12d9b9ddb2b2d49b6bb8be18681a2`。继续同一实际节点 cn21762 的独立 32 电极 B64，版本 `H2_32B64_A`，运行绑定 SHA256 `bc1ec8581162a21dc84a6c65e562811004fbcec31627fe82d7277b6928228538`，唯一提交 2065151。B64 样本顺序单独冻结为原 800 个真实索引的两次确定性遍历，初态绑定原模型 SHA，所有 16 个 DDR 进程实际生成的 25 份 B64 掩码 SHA 在第一步放行前比对并写出。HBM 对照读取同 B64 的 DDR 参考。

2065151 成功终态并已收集，传输 SHA256 `f9b9f770781a8faf894be8f6b18c733e2a6e0fcb55678e93d7172115827a9b0f`。继续同一实际节点 cn21762 的 16 电极 B64/CKPT0，版本 `H2_16B64_A`，唯一提交 2066108。逐字节复用 16 电极包 SHA256 `abecb3de40f1edf0adecebe09671a2c8d980946dd41dd0f23587105b0a59e51e`，运行绑定 SHA256 `d4a077f042883c16b2218c30ba72c3b68db5fa0d25af05e3055a58de295f0fee`。

2066108 成功终态并已收集，传输 SHA256 `a619424ac311515b34c51facc9bd308d371557a86e4345ff5da3272fc0aeb5ce`。首机剩余 B32 第 2、3 轮版本 `H1_32B32_R23`，唯一提交 2066185/cn22035，包 SHA256 `904def960f2c08be24539f2bd978fce3f814bf78bc54e3cbaada3dd846b0fc28`，绑定 SHA256 `a5ee9024aeb67bae29f34691965115cb37aa02865beee4f155990374826573ff`。每个新 allocation 重核 HBM 安全与严格五步，DDR 25 步仍以 2064138 的同 allocation 对照为准。

2066185 成功终态并已收集，传输 SHA256 `5fbc1108d2d99c368a296e4af3aa743db80bc4d3dcfd501cae3c46e97ee11eee`。用新两轮的实际阶段墙钟复核首机 B64 时限，见 `B64_WALL_PLANNING.json`。沿用同 B64 样本侧车、同包 SHA 与原数值门，在 cn22035 部署 `H1_32B64_A`，唯一提交 2066391，运行绑定 SHA256 `682661d4f408ae3b9fb869a7047b8d049c606bcb81187131583759388e2db018`。

2066391 成功终态并已收集，传输 SHA256 `045697dcbc94825d997cf7356829958e70df31ba4a45b0ebffce1b8e26ec5924`。配对同原生分配完成，额外轮次根据真实耗时延后。沿用 cn22035 和同包、同侧车，版本 `H1_32B64_R23` 唯一提交 2067131，绑定 SHA256 `5082eceda55d0815343aac01cff717808f07e797d09d34b1a5a39e9c6944dce1`，重核全域安全及严格五步，再补 HBM 第 2、3 轮。

2067131 成功终态并已收集，传输 SHA256 `bf29ebd255f5c44551d385b01d865105786afd0660d4aa0d50d515fe9aa1bb7a`。第 2、3 轮完整，已核原生 PID 空、实际自有进程回收和各阶段 HBM 页池归还。最终通过 `djob -J -l` 逐一复查全部 8 个原生 job，均 `SUCCEEDED`，`nodeResUsages.pids` 均为 `-`。
