# S02 内存分解与 S03 交接

日期：2026-11-04。**STATIC_ONLY / RESIDENCY_NOT_MEASURED**。以下为冻结源码默认结构的逻辑张量字节；不是 DDR/HBM 测量，也不是工作集上界。算式及所有 B/M 原值见 `prepare_evidence.py`、`evidence/static_memory.json`。待 torch 可用，数值脚本首先核对真实模型 numel 与此解析计数；本次这项动态核对未运行。

## 参数、梯度、AdamW

编码器 37,995,777 参数，解码器 29,416,449，合计 67,412,226。没有更改 12 层/512/8、U-Net 通道、归一化或注意力。

| 对象 | fp32 字节 | MiB（2^20 字节） | 生命周期/限制 |
|---|---:|---:|---|
| enc+dec 权重 | 269,648,904 | 257.157 | 两阶段均常驻 |
| 所有参数的两个 AdamW moments | 539,297,808 | 514.314 | 原入口两阶段预热后逐步建立，随后常驻；每参数另有 step 标量和容器开销 |
| pre 参数梯度 | 151,983,108 | 144.942 | 仅 enc；清梯度后重新生成，跨微批累加 |
| dec 参数梯度 | 269,119,492 | 256.652 | enc 除 mask_tok/两个预训练 head，另加全部 dec |
| fresh optimizer 仅 pre 的 moments | 303,966,216 | 289.885 | 首步 lazy 初始化；不可当作预热后真实入口 |
| fresh optimizer 仅 dec 的 moments | 538,238,984 | 513.305 | 同上；不含预训练专用参数的历史 state |

全参数 moments 建立后，权重+moments+当前阶段梯度的逻辑小计为 pre 916.414 MiB、dec 1028.124 MiB。**还没有计入任何激活、输入、临时张量、allocator/后端 workspace、Python 容器、库或页碎片，不代表峰值。** fp32 master 参数已经计入权重，不再重复加一份。AdamW 中无梯度参数不应做 weight decay、不应增加 step，也不能删除其已有历史 moments。

参数计数推导：Linear=i*o+o；Conv2d=i*o*k*k+o；GroupNorm=2*c；encoder 每层含 QKV/out、两层 FF 和两个 LayerNorm；U-Net MHA 分别计算 q/k/v 与 out 投影（ctx=512），不把不同维度错误当成4*c*c。逐模型 numel 断言在真实检查脚本中。

## 随 microbatch 改变的对象

32 电极 M=928 下单个张量的逻辑尺寸：

| 张量（fp32） | B64 MiB | B32 MiB | B16 MiB |
|---|---:|---:|---:|
| encoder h / 每层宽度512输出 [B,928,512] | 116 | 58 | 29 |
| 单个 FF 隐层 [B,928,2048] | 464 | 232 | 116 |
| 单个 [B,8,928,928] score，**仅当实现物化时** | 1682 | 841 | 420.5 |
| U-Net 首层 [B,128,64,64] | 128 | 64 | 32 |

这些对象有别名/重用及不同存活区间，**不能把各行或层数简单相加当峰值**。原生 CPU SDPA 可能使用不同后端，不应先假定一定存在 N² score；KML ctypes / oneDNN workspace 也不一定由 tensor 统计完整覆盖。16 电极及精确字节见 JSON。

固定 B64 的 v+y0+e+t+mask 为 M208 2,164,224 字节、M928 2,394,624 字节，未计 angles/belt/整个 demo 常驻数组；这部分不随 microbatch 减小。原入口 D 读取所有 NPZ 键，包含当前不用的 J_img；又保存 imgs/x 等中间数组，实际尺寸依赖真实帧数与输入 dtype。本地没有真实 NPZ，不能据此估算其总驻留或直接改成“选择性读取”，更不能默默换输入。

现有 CKPT 仅包裹 encoder 每一层，不覆盖 U-Net；它保留 checkpoint 输入并在 backward 重算，不能消除权重、moments、当前 h、U-Net 激活或后端临时缓冲。B16×4 能减少一部分单次图的激活，同时增加循环及重算代价；哪项先触及 4GB、哪项最快均待实测。

## 给 S03 的测量约定（当前全部未运行）

在接受的 S01 运行器和 S00 现场确认的代码/库/输入上，先做32电极，随后补16电极；pre/dec 分列。候选顺序为 B64×1 CKPT0、B32×2 CKPT0、B16×4 CKPT0、同三组 CKPT1，共六组；每组有效批64、fp32不变。不要把历史B32无累积和新B32×2拼成配对结果。

同一次有效批的采样点：模型/输入建立后、两阶段预热后、清梯度后、每个微批 forward 末、backward 末、step 前后。记录时间戳和 phase/microbatch；峰值需连续事件或足够采样覆盖，边界快照只是下界。使用独立运行做 profiler，避免把 profiler 或等价检查快照的额外驻留计入性能结果。

交接表需同时有：

- tensor 实际 storage 的去重字节与大小类（<256KiB、256KiB–2MiB、2–16MiB、16–128MiB、>=128MiB），区分参数/梯度/moments/saved activations/临时数据；保留分配和释放时序，防止将累计量写成同时存活。
- 进程 DDR RSS/PSS、映射和 NUMA 分布；hugetlb/HBM 映射、页实际占用/触达及高水位单列，注明共享页/独占节点条件。普通 RSS 不含全部 hugetlb。
- allocator 申请累计字节、arena bump high-water、实际存活/实际驻留分别命名；分配字节不能证明访问热度。给 S03 的放置优先级须结合重复访问/流量证据，不能仅凭张量名字或尺寸改 allowlist。
- 全有效批耗时（全部微批及一次step），包含 CKPT 重算；不使用单微批耗时推算整批收益。不在本次数值脚本内计性能，它保留大量参考快照。

停止/扩展：数值失败、NaN/Inf、输入身份缺口未解决、OOM/SIGBUS、任何缺域/超时使该轮无效；先单域有限小试，四域通过后再整节点，三有效轮与第二主机按协调排期。此处没有申请/使用节点小时，也没有推荐正式 batch、LR 或 schedule。

当前可给 S03：解析存储清单、张量尺寸、生命周期测点和候选接口。当前不能给 S03：实际同时占用 trace、热度排序、实际最小工作集、实际性能最优配置；这些缺口须保留。
