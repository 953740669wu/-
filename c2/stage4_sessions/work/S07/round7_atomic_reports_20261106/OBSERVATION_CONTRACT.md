# S07 R6：单次对齐取栈的执行边界

只对watchdog启用，不改变原初始化、注入点或四case接受规则。2041919仍保留整组FAIL；此次交付是观测实现，不是故障根因修复。

## Python栈与文件生命周期

- worker在验证原生CCS_JOB_ID、CPU36 receipt、继承CPU权限并显式绑到本rank selected36之后，保留原worker_ready首事件，再设置一次计时。时点为 `S07_CASE_DEADLINE_NS - 5e9`，默认即原case起点+25秒；延迟由目标减当前monotonic计算，不从导入/ready重新获得25秒。
- 只调用一次dump_traceback_later，repeat=False、exit=False；文件以独占二进制方式打开。设置前后均核全部可见TID的CPU掩码属于本rank selected36，新C watchdog线程也在快照范围。该API使用watchdog线程，文件必须保持到转储或取消。[Python3.9官方说明](https://docs.python.org/3.9/library/faulthandler.html#faulthandler.dump_traceback_later)
- 两次检查设定时点：打开文件前、打开后。若已经错过目标，记录MISSED并不设新timer；不补跑/不重置。开文件后才发现错过则关闭尚未交给faulthandler的空文件。
- 初始化结束事件记录返回后取消；worker的finally再次调用幂等取消/关闭。先cancel后close，保留首次取消原因和时刻。取消API出错时保留文件引用直到进程退出，标CANCEL_ERROR_FILE_RETAINED，不提前关闭/复用描述符。异常不绕过原父清理。
- `rankN.stack_status.json` 的ARMED只证明计时已设置，**不代表已取到栈**。进程被TERM时finally未必执行，必须同时核原始stack文件内容；文件为空/缺失不能写成成功取栈。C2调度/文件I/O误差尚未实测，不承诺纳秒精确触发。

## 辅助/proc：同一目标、共用2秒窗口

- 父只在watchdog启动一个本任务helper，不同步读取目标/proc，也不等待其采样返回。helper在目标之前启动、记录基准身份并等待同一绝对目标，采样窗口固定为[目标,目标+2秒]；准备/等待和所有观测开销仍计入原case总预算。
- 父向helper传真实Popen worker PID、拥有者父PID、run/job/token、两个CPU36 receipt。helper核原生job与实际父PID，并在目标前记录worker的PID/PPID/session/start_ticks；只允许同一父创建、各自独立session的两worker，拒绝自身或别的进程。采样前后再比起始标识/父/session及目标CPU掩码，变化则拒绝，不追踪新PID。
- helper启动继承父已授权selected集合并集；先缩到rank0 selected36完成身份准备，采样每个rank前缩到该rank selected36，并核自身所有可见TID。切换只在启动时捕获的授权集合内，不触碰每域预留2核，不使用主机全部可见核替代授权。没有Torch/模型计算或额外线程池。
- 目标主TID读取wchan/syscall/native stack；记录mountinfo与最多16个FD的链接/dev/inode线索。字段最多64KiB，EMPTY、ERROR/权限拒绝、TRUNCATED均保留。源码读取失败不安装新工具，不扩大到其它PID或全盘扫描。
- Linux helper的alarm和每段检查都使用同一个绝对采样截止；晚唤醒只剩原窗口余量，错过设定/完整窗口记MISSED/MISSED_WINDOW。TimeoutError单独向上终止，不能被当作可忽略权限错误继续读。两rank共用窗口，不各获得2秒。
- 父非阻塞poll，到采样截止kill自己Popen的helper；原worker的TERM先按原规则发出，再停止helper。helper回收只占原cleanup共享宽限，**没有helper wait/join或额外清理窗口**。若操作系统仍未使其退出，记录UNREAPED，交原S00外层拥有session的清理，不伪报已回收。OS不可中断I/O/调度的现场能力未验证，保留目标/实际时间与超期标志供核验。

## 安装源码身份

仅watchdog在backend_info返回后、ready之前，只读当前已加载distributed_c10d/rendezvous的两个小Python文件，每个最多1MiB，保存实际路径/bytes/mtime/SHA及目标函数必要调用的语法位置。前后stat变化或缺模块/无权限明确记INCOMPLETE。

这些是安装文件的静态来源记录，不证明某分支实际执行，也不等同C++调用栈。采样窗口不重做大Torch库哈希；原backend_info的大库身份记录保持。共享Torch不写入、不改造。

## 保持的接受层级

原pg5、原spawn前case30秒、consumer270/job300秒，Gloo/lo/file-store、CPU36/job/ready机制、注入点与run_checks.py全部保持。诊断完成度和通信判据分开：采样失败不等于数值失败，截止清理也不能代替watchdog到injected_hang；缺诊断不允许称观察任务完成。旧三过不能与后来补项拼成同一suite通过。
