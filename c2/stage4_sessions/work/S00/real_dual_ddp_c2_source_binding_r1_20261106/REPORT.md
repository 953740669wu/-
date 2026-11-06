# S00 C2定向补源R1

状态：SOURCE_PACKET_COMPLETE_FOR_REVIEW，仅供审核。SOURCE_BINDING_PACKET.json SHA256=b0a0c1e11fb0ba26987f69cfc13b24eb15dc97820f141cfa835857af56edd93f。

先核01 BLOCKER_REVIEW、MISSING_BINDING_SPEC和原R4运行时/共享模块身份清单的冻结SHA，均吻合。S00离线文件及93个ZIP中央目录未找到六份确切目标原件；本地归档容器另做SHA核验，没有从Windows环境或上游补入替代源。

按新任务卡唯一一次只读SSH导出，采集主机login03，远端UTC=2026-11-06T15:45:58.863780+00:00。使用原R4 Python3.9.9/aarch64，-S禁site启动、-B禁缓存；仅标准库PathFinder查源码/扩展路径，不导入Torch。相同PYTHONPATH与已冻结R4环境关联。接收端与远端墙钟分别保存，预算依据远端单一monotonic起点及外层60秒timeout，不混用墙钟计算耗时。

六份原文共432651bytes（上限2097152），共同读取/哈希/导出0.364120212秒（上限60）。六份原字节base64回传后本地逐份bytes/SHA核验，文件名和顺序与01规格完全一致；version.py只做静态常量解析，版本2.7.1+cpu，git_version=e2d141dbde55c2a4370fac5165b0561b6af4798b。所有本地原文位于sources/torch，未换行重写或执行。

冻结__init__.py SHA9801e75447c7f585545f989f8a21940b60e0c4cc888effb2f08e739664b4b904、原R4解释器SHA41ed40932add50d0a953bbe92ba15a9e60a2ee476ce68cfd4798cf814647c383在采集首尾各核一次，路径/realpath/stat/字节身份均一致；14份唯一文件末次stat稳定核对完成。

只在已知包根与lib做两次非递归定向识别：实际_C.cpython-39-aarch64-linux-gnu.so，以及libc10、libtorch、libtorch_cpu、libtorch_global_deps、libtorch_python。六份核心文件均交路径/realpath/bytes/SHA、ELF64 little-endian AArch64与已有GNU build ID；只读取文件和ELF note，未加载/执行这些库，二进制下载0。核心库SHA为本次首次身份记录，不冒称旧job核心库字节身份曾被本轮回溯验证。

缺项/权限失败/身份漂移/超限/重试均0；SSH1、远端临时写0、SCP0，读取和输出结束后没有补取。Torch导入、模型、autograd、DDP、夹具、计算job和训练更新全部0；无进程/队列查询、安装提权、运行时/共享源码编辑或Git操作。旧规格、旧FAIL与前轮部署/结果全部按SHA确认未变。

缺源材料已齐，但B01方法/唯一消费边、目标hook API、attention布局与调用点是否足够仍由01独立静态审核；本包不作这些设计判定，不发布PREPARATION_READY，不恢复实现/部署/诊断/训练，也不声称解除全部准备阻断。精确ARCHIVE_FILES.json仅列本任务目录与S00短状态/六行摘要；本地SSH公钥记录不入归档，登录密码或私钥未写交付。
