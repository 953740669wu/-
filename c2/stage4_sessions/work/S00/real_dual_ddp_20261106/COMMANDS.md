# REAL_DUAL_DDP 唯一条件执行

本目录外包给01审核；07本地原阈值小B64配对FAIL，三项失败证据已固定，不声称本地数值通过。S01未最终同SHA明确PASS前，以下提交步骤禁止执行。Linux19+02参考7检查全部零skip后才允许实际完整模型更新，所有阶段共享840秒，清理30/收尾30。

新远端根目录（本轮已创建，仅包装检查，无job）：

```text
/home/share/dengqingtian/opt/stage4_sessions/S00/REAL_DUAL_DDP_20261106T085703Z
```

从本地上传S00_REAL_DUAL_DDP_DEPLOYMENT.zip到上述根目录。严格主机记录在本轮evidence/known_hosts_dual_ddp_confirmed_pool；不在命令或文件中记录密码。外包SHA见S00_DEPLOYMENT_READY.json及evidence/OUTER_BUILD_RECEIPT.json；内包原样为S02=df7275b06d8ee59cd88c0d17c04b0b64f63605ffa1c4410d3d02307ce848eec5、S07=d032d67cd76eddbc372ab6f9dd51c8355c4bb1ef3e7469254c2549a3481623a9。

登录节点核外包SHA后只在新根解包，执行：

```bash
ROOT=/home/share/dengqingtian/opt/stage4_sessions/S00/REAL_DUAL_DDP_20261106T085703Z
/usr/bin/python3 -B "$ROOT/prepare.py"
/usr/bin/python3 -B "$ROOT/tests/test_deployment.py"
/usr/bin/python3 -B "$ROOT/payload/training/candidate/train_ddp.py" run --help
```

以上仅源/AST39/LF/bash-n/包装夹具/真实CLI解析，不导入Torch，不执行07数学或模型。准备证据保存后发布S00_DEPLOYMENT_READY。S00实际本地调用validate_release.py会核上游源、冻结包、全部资产与READY一致性。

仅当S01/real_dual_ddp_review_20261106/S01_REVIEW.json为PASS_FOR_REAL_DUAL_DDP、review_complete=true，且required_review_bindings/resources/workload全部一致：复制原字节审核到本目录S01_REVIEW.json，执行本地：

```powershell
python -B E:/eitfm_c2_stages2-4_2026-11-03/c2/stage4_sessions/work/S00/real_dual_ddp_20261106/validate_release.py --review
```

再上传该审核原件到远端同名路径。登录端唯一提交入口：

```bash
source /etc/profile.d/donaukit_scheduler.sh
ROOT=/home/share/dengqingtian/opt/stage4_sessions/S00/REAL_DUAL_DDP_20261106T085703Z
/usr/bin/python3 -B "$ROOT/submit_once.py" "$ROOT"
```

入口先核具体审核和源，再查询完整实时队列/当前每项job详情、系列marker；创建排他submit_once.marker后只调用一次：

```text
dsub -J -q q_hpcai -x job -R cpu=76,mem=24576MB -RL mem=24576MB -a numa[count=2,distribution=pack] -T 900 --env none --cwd ROOT -oo ROOT/job.log bash ROOT/run_job.sh VERIFIED_S01_REVIEW_SHA256
```

末行是submit_once.py产生的精确argv结构，ROOT及审核SHA自动填入submission.command.json，不手填未经核验值。提交失败或歧义也保留marker，不重试。RUNNING后登录端只发布一次原生nonce/raw/ready调度交接；计算端不source登录profile。

现场按当前授权两域各38分配/36实际/留2、DDR总24576MB同limit、HBM0核验；两个CPU-bearing DDR节点numactl绑定。S07检查父保留76继承授权，两个Torch检查child及实际worker各在Torch前绑本域36。02原七项文件顶部导入Torch，启动解释器前绑定rank0 selected36/DDR；其原小模型测试内部2线程只属独立夹具，不改实际训练36线程。Linux检查全部26项（19+7）零skip才进入完整Encoder；失败立即所属清理，不继续训练。真实模型最多前5原B64逐步门槛，再同状态到25；最多50rank+5参考=55完整更新。

跟踪同一job到终态，collect_evidence.py在登录端收取原始文本/日志/空坏报告/隐藏残件；所有.pt/.pt.tmp/.pth/.npz权重只留远端并索引，不下载。终态后：

```bash
source /etc/profile.d/donaukit_scheduler.sh
ROOT=/home/share/dengqingtian/opt/stage4_sessions/S00/REAL_DUAL_DDP_20261106T085703Z
/usr/bin/python3 -B "$ROOT/collect_evidence.py" "$ROOT"
```

取bundle_receipt.json及其唯一ZIP，核bytes/SHA/CRC/逐文件索引后发布RUN_COMPLETE.analysis_inputs。01不通过则无job，保留明确冻结/失败停点；不为求PASS重跑本地失败检查或替换参考/阈值。
