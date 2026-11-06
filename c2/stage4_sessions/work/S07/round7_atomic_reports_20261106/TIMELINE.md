# 2050433 crash报告时序与受控复现

原件入口为S00/s07_r6_resume_20261106/RUN_COMPLETE.json的analysis_inputs；本轮24项必要输入的绝对路径、bytes、SHA、mtime及两次稳定读取见evidence/SOURCE_INPUTS_BEFORE.json。R6及原失败均只读。

## 现场事实

以下为同节点monotonic_ns，不把本地收集mtime用作现场事件时钟。全部事件原文见该analysis_inputs/crash/下rank0.events.jsonl、rank1.events.jsonl、supervisor.events.jsonl。

| 事件 | rank0 | rank1 |
|---|---:|---:|
| spawned（父日志） | 3968883544357878 | 3968883600861615 |
| worker_ready | 3968884249636148 | 3968884316642429 |
| Torch导入begin | 3968884274105141 | 3968884437229963 |
| Torch导入end | 3968899943997050 | 3968892193229621 |
| preparation_complete | 3968900965000189 | 3968892707311576 |
| both_ready | 3968900996646113 | 3968901009877111 |
| 初始化begin | 3968901006307036 | 3968901017939352 |
| 初始化end | 3968901770340251 | 3968901770270951 |
| 最后checkpoint_end | broadcast: 3968901811263338 | injected_crash: 3968901811273738 |
| worker_error | 3968901856907871（peer reset） | 无此事件 |

父监督起点3968883492839668；cleanup_begin=3968901863234009，reason=child_failed，exit_codes=[null,17]；TERM rank0=3968901865811403；回收rank0=3968901917849245/-15，rank1=3968901919945498/17；supervisor_end=3968901921841630。worker_error到cleanup相差6.326138ms，到TERM相差8.903532ms。summary为FAIL/all_reaped=true，原rank0.json为0 bytes，SHA为e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855；原checks.json仅normal已通过，随后JSON读取异常停止。后两case及取栈NOT_RUN，整组仍FAIL。

## 源码支持的机制与证据缺口

R6的write_json先json.dumps，再Path.write_text；后者以w打开目标会先截断。checkpoint、正常结束、异常处理三处均用它重写rank报告。broadcast checkpoint_end意味着此前一次报告发布调用已返回，后来worker_error触发同目标的另一次覆盖写。最终空文件与后续重写被TERM打断一致，但现场未记录系统调用/栈，不能指定精确被中断的write/syscall。

peer reset发生在故意rank1崩溃之后，不说明normal有同样通信故障。此次双方初始化已结束；不能据此解释历史watchdog的初始化阻塞。

## 受控复现（本轮本地）

先加入17项检查并运行红灯，再实现修复；红灯原件atomic_red.log显示旧模式空/残报告两例已复现，新函数尚不存在。旧模式使用逐字节保留的write_json，子进程在目标流打开后、写零字节或半份内容并flush时等待；父只终止自己创建的短进程。结果旧报告分别变成0 bytes及30 bytes残JSON。

原子模式在相同写入故障点把损坏局限在独占临时文件，原133-byte报告逐字节保留；另在完整写入/fsync/关闭、replace前终止，旧目标仍完整。首次发布尚未提交时，正式文件仍缺失，原reader照常拒绝。evidence/controlled_reproduction.json绑定六组输出，包括临时残件；不从事件或父内存补造正式报告。Windows terminate不等于Linux SIGTERM现场验证，本轮没有Torch/Gloo或新job。
