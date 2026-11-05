任务/轮次：COORDINATION / GIT_READY_R5_FP32_R3_REVIEW
状态变化：00 R5本地准备/04 R3本地fp32控制核验，累积交付转唯一Git窗口归档；实际远端为GitHub。
本轮改动：新归档指令/TSV、定向核验MD/JSON、10+2项复跑日志、总表/自身状态；作者源码不动。
验证增量：核00索引15/86及16文件包、04索引29及30文件包/保存83零误差；新增10收集+2结构复跑全过，旧全量检查不重复。
证据：GIT_READY_R5_FP32_R3_REVIEW.md/.json、S00_R5_GIT_TARGETED_TESTS.txt、S04_R3_GIT_TARGETED_TESTS.txt、新提交TSV。
阻塞与下一步：Git按精确SHA分批commit并普通push现有origin，核远端/回报；bf16仍FAIL、P1未实施、就绪协议未现场测，root不代提交。
