# S06 R2：线程观测与父进程退出清理

日期：2026-11-05；READY_FOR_REVIEW（修订包） / LOCAL_ONLY / CLUSTER_NOT_RUN。

本轮仅修订线程口径、进程退出清理和检查搬移性。没有安装、连接集群、提交作业、调用真实Torch或重跑旧卷积搜索。R1原始代码、报告、证据均保留；更新短状态前已按其旧清单核验27项并逐文件保存完整r1_snapshot（含当时的两份可变状态和原清单）。R1原始模型/KML与新包内副本不变。

## 修订和来源

先读自己的状态/增量、AFTER_S06_S07_NEXT的S06节、本次审核S06节及总表，再核对现有三份候选与旧7项检查、源码/mtime/SHA。SOURCE_IDENTITY.json保存本轮读到的来源身份，MINIMAL.diff列全部必要代码差异；新增冻结合同与新检查的完整内容也在包内，无共享核心改动。

1. run_linux.sh仅将OpenBLAS36改为1；OMP36/MKL36/cores/close不变。
2. probe.py移除set_num_threads；after_framework读取实际Torch intra-op/interop/parallel_info，实际intra-op非36即拒绝。before_framework/after_framework/before_exit保存并校验全部可见TID；完整性失败、任一掩码越出S00所选36核或环境冲突均失败。检查失败原始快照保留；退出时失败不能留下PASS。新增记录与检查开销不作性能结论。
3. 复用S00已冻结、与S01 R7同SHA的CPU36_MODEL_V1合同；仅调用ENVIRONMENT、cpu_list、snapshot_threads和validate_snapshot，冻结文件原样复制SHA=3990bb6ba40e7d4e47037aef245c6bc971191e7ae2c4be8701dd329c408a179d。没有改合同、绑回36或强制修改框架线程数。
4. run_probe.py用finally覆盖正常、超时、TERM、SIGINT/KeyboardInterrupt和wait异常；只清理自己创建的新session组。TERM后0.5秒有界wait，再KILL该组（含leader已退出的情况），最终1秒有界wait回收直接子进程。清理中不再接受重复中断，随后恢复旧handler；Popen句柄赋值前的信号延迟处理，避免丢失新子进程或让子进程继承被阻塞的TERM/INT。异常/清理回执落execution.json；CLEANUP_FAILED非零。
5. 旧源检查改为包内SHA及可选S06_PROJECT_ROOT显式原项目路径，删除固定祖先定位；测试自己创建evidence目录，纯文件搬移/解包无需保留旧目录层级。

## 新增验证及边界

- 最终Windows Python3.11标准库26项：23通过、3 Linux实测跳过；其中旧7项通过，新增19项为16通过/3跳过。证据evidence/tests_after.txt。
- 线程正负控均使用模拟Torch/快照：实际36通过且模拟对象没有setter；环境36/实际35拒绝、OpenBLAS36拒绝、越界TID/不完整快照/重复selected拒绝；单TID正常绑定选中单核通过，失败快照保留。不能据此宣称真实Torch36。
- 退出检查覆盖超时、KeyboardInterrupt、TERM、wait异常、创建句柄期间收到TERM、清理失败非PASS及只向本任务组发信号。Windows实际执行了旧检查中的直接子进程失败/超时；POSIX分支为模拟调用，不能视作Linux组清理通过。
- Linux真实继承信号掩码、TERM清后代/SIGINT清后代三项已准备，当前全部NOT_RUN。Windows无SIGKILL的POSIX模拟夹具错误已修正；初版失败输出保留为tests_after_first.txt。
- 将最终新包纯文件搬到任意flat_relocated_payload目录，默认不设置S06_PROJECT_ROOT再复跑同套26项；不依赖原项目祖先结构。证据tests_relocated.txt/local_verification.json。
- Python3.9语法解析和Windows Git Bash的bash -n为语法检查，不是Python3.9/Linux运行、线程数值或C2执行证据。本机依旧无Torch，未声称真实探针通过。

before_framework/after_framework/before_exit只是当时全部可见TID快照，不是连续观测、物理活跃36核或全部编译后代的线程监测。REAPED仅指直接子进程已回收且限定组的清理调用未报错；不证明所有后代可由本父进程wait回收。父进程被SIGKILL、系统失效或不可中断内核等待不在Python finally保证范围。未改变原模型数值门槛、loss、精度、批量或性能验收。

## 交付与下一步

- payload/README_R2.md：修订命令、环境口径、资源/失败界限和回传项；替代旧R1执行说明，旧说明只保留历史。
- payload/：可独立搬移的修订包；payload/ARTIFACT_SHA256.txt校验包内文件。
- S06_R2_PAYLOAD.zip：只包含新payload；其SHA及本轮总文件清单见ARTIFACT_SHA256.txt。
- r1_snapshot/：完整R1归档，原manifest可在该目录逐项核验；根S06当前状态更新后，旧根manifest不再用于校验当前状态。
- SOURCE_IDENTITY.json / MINIMAL.diff / evidence/final_verification.json：来源、精确差异、R1保留/最终包与源码身份。

下一步先由总协调复核修订包，再由S00在明确安排的资源内执行Linux针对性检查和实际probe；当前没有新job，没有活动的本任务子进程。C2依赖/权限/编译器、实际Torch36/TID边界、Linux组清理及所有compile/数值/性能结论继续未测，不建议集成模型改动。
