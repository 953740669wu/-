# S00简短状态

- 更新/轮次：2026-11-05；S07_R4_DIAGNOSTIC_20261105T104153Z；由S00维护。
- 本轮完成：唯一2041165/cn21338 FAILED/jobExitCode1；28 Linux检查/环境通过，normal初始化失败，已收齐原始事件及终态，无重试/补跑。
- 活动job：本轮相关S00 job全部终态，无活动S00 job；两直接worker回收、外层remaining_live=[]、调度PID清空。SSH/SCP正常退出，其他任务不动。
- 去重/来源：从login05实际核队列和全部R4目录/提交记录无已有本轮任务后单次提交；原包prepare/清单、登录14+25检查通过；原submit_once/publisher一次成功，无临时改包。
- 包/预算：外包62715bytes SHA=b20e248be761db6c645fdbcebbbfc61d083642bb0e1d959eb1a0fcfa9b304284；内包31262bytes SHA=af2725e24d0bd8b2183f1d7bc8b6aae79f801b7b83b640b41645e822e0c23f45；两域76分配/各选36留2，总DDR24576MB同limit/exclusive/HBM0；job300/consumer270/pg5/case30秒均未改。
- 验证增量：本job6诊断+6身份+16原检查=28 Linux全过、无跳过，环境通过；原生job/nonce/raw/ready/新鲜度/主机/资源/逐核拓扑通过。normal rank1实际Torch36；rank0未到该测量和导入后TID检查点，不宣称双方完整Torch36实测。
- 事件观测：rank0/1/父监督各15/25/10行，全部原字节保存；rank1相对9.401416s入初始化、15.924755s报Wait timeout；rank0相对16.383994s才记录Torch导入结束，16.420449s进入libtorch_cpu SHA，16.569892s被父监督TERM。
- 清理/边界：父监督16.567950s因child_failed开始清理，exit[-15,1]、all_reaped=true，16.676003s结束，未触发30秒case deadline；normal未到all_gather/broadcast/all_reduce，后三case均NOT_RUN。不把rank0的-15或缺SHA end当其自行失败/哈希永久卡住。
- 诊断完整性：原清单DIAGNOSTIC_EVIDENCE_INCOMPLETE；rank0 metadata/CPU库SHA、rank1 init区间未闭合。未检出TRACE_WRITE_ERROR/非法行/截断尾行；不据缺end定根因，不重跑补证。本次准备阶段错开已有事件，旧2040233是否同因仍待S07分析。
- 完整证据：evidence/s07_r4_diagnostic_20261105T104153Z/JOB_2041165_full_evidence.zip，197610bytes/82文件，SHA=f8213b5946d756675e2b890597dd930644346c1c77f3cba2efbedb982038248c；81项远端mtime/bytes/SHA与全部ZIP原件核验通过，源改动=[]。
- 汇总：S07_R4_DIAGNOSTIC_REPORT.md；本轮REVIEW.json/TIMELINE.md/received/及ARTIFACT_SHA256.txt；candidate/audit_s07_r4_diagnostic.py只核档案和原事件清单，不重跑检查/通信。
- 连接记录：认证前网络失败和主机密钥变化已记录；用户明确授权10.44.9.4入口各指纹信任，另存pool并保留旧文件，本轮实际仍StrictHostKeyChecking=yes，未改其它主机设置，凭据未落盘。
- 成本/保护：19:04:00—19:05:21中国时间，81节点秒/usage81，已知累计21job/1045秒；旧R4包/候选/旧失败及2040363保护SHA未变，共用暂存区及其它任务目录未操作；02/06/训练未运行。
- 下一步：只交总协调/S07原会话分析本次双方准备阶段与监督终止时间线，不宣称通信或旧根因修复，不自动追加实测。
