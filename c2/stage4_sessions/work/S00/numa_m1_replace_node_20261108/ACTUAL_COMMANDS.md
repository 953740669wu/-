# M1 换节点续跑实际命令

通过既有 C2 登录端先核 2060643 的原生 ID、用户、执行路径、SHA 和等待状态。使用本站 `dkill --help` 所列的原生状态过滤，只对该 ID 的 PENDING 状态发出取消。调度原件记为 FAILED 和退出码 10003，显示用户终止前未开始、未分配。旧观察器均已退出。取消前后和用户终止回执在 `old-2060643`。

```bash
source /etc/profile.d/donaukit_scheduler.sh
djob -J -l 2060643
dkill -J -y -s PENDING 2060643
djob -J -l 2060643
dnode -J -q q_hpcai -s OK
dnode -J -l cn21341
dnode -J -l cn21761
djob -J -l 2061067
```

新根使用两个现场核实的空闲候选节点，排除旧忙节点。M23 四域作业 2061067 已成功终态、无残留。实际提交脚本重新核对队列及 M23 交叉，并校验至少一个候选仍空闲。新代码在计算节点以原生回执核对实际主机、CPU 集合、四域及实际 DDR 限额。

```bash
RUN=/home/share/dengqingtian/opt/stage4_sessions/S00/NUMA_M1_R1_REPLACE_20261108
PIN=cccb393be2be01e86dc402abe91db8bc0b06ef1151fb98991442ae18ca779b20
PACKAGE_SHA=1be8cab8371f38320fc6be2543d20989ea09ea506f38369918874aa2142437c9
cd "$RUN"
printf '%s  %s\n' "$PACKAGE_SHA" NUMA_M1.zip "$PIN" NUMA_RUN_BINDING.json | sha256sum --check --strict
unzip -n -q NUMA_M1.zip
/usr/bin/python3 -B prepare.py "$PIN"
timeout --signal=TERM --kill-after=5s 60s env -u LD_PRELOAD PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 /home/share/dengqingtian/opt/stage4_sessions/S00/ENV_20261104T130730Z_R4/venv/bin/python3 -B inspect_metadata.py --output LOGIN_METADATA_CHECK.json
timeout --signal=TERM --kill-after=5s 45s /usr/bin/python3 -B recheck_fixed_inputs.py > FIXED_INPUTS_BEFORE.json
nohup /usr/bin/python3 -B submit_once.py "$PIN" </dev/null >login_submit.log 2>&1 &
echo "$!" > login_submit_pid.txt
```

唯一原生提交命令由绑定生成。2061246 实际获配 cn21341，其他候选节点未运行本批训练。

```bash
dsub -J -q q_hpcai -x job -nl 'cn21341 cn21761' -R 'cpu=152,mem=98304MB' -RL 'mem=98304MB' -a 'numa[count=4,distribution=pack]' -T 1800 --env none --cwd "$RUN" -oo "$RUN/job.log" bash "$RUN/run_job.sh" "$PIN"
djob -J -l 2061246
timeout --signal=TERM --kill-after=5s 45s /usr/bin/python3 -B recheck_fixed_inputs.py > FIXED_INPUTS_AFTER.json
/usr/bin/python3 -B collect.py "$PIN"
```
