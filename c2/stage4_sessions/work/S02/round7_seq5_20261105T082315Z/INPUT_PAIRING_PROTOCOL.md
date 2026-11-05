# S02_PAIRED_BELT_V1：电压、目标和帧身份

日期：2026-11-04。范围：本地候选与合成等价检查。**不是正式训练数据/归一化协议的最终批准，也没有生成真实数据输出。**

## 依据与两条账目

读取COORDINATION/S00_REMOTE_REVIEW.md，接受的是保存的证据交接。只读核对S00的remote_context.json：placement0/1的demo images payload SHA均等于32电极源，且不同于16电极源；形状同为[2,64,64]不能证明目标属于同一帧。生成器s6_corpus.py在同一循环将images[b*nt+i]与v_cur[b*nt+i]写入单元，base_of_pair确定相应v_ref行；随机种子含L，不能假定不同belt生成了相同目标。

- `LEGACY_SHARED_IMAGES_TIMING`：保留原demo与历史记录，只解释旧入口的计时；不据此接受16电极科学训练正确性。
- `S02_PAIRED_BELT_V1`：每个belt的电压与目标从同一冻结源单元的同一行读取；新协议与旧输入有语义差异。今后基线和内存候选都必须使用同一套新协议输入，不能把输入修正带来的差异归给微批优化。

本地没有真实NPZ/sidecar。本次仅在S02/evidence内创建并清理合成文件；未读取远程、改旧demo或冻结corpus。真实源的整文件与sidecar哈希、训练划分和元数据仍须S00/协调确认。

## 输入身份与顺序

候选API：`candidate/paired_inputs.py::load_belt_inputs(sources, belt)`，每个source必须显式提供`path`（NPZ绝对路径）、`npz_sha256`、`sidecar_sha256`。哈希须来自可信冻结快照，不能在发现不符后自动接受新哈希。侧车为同名JSON。函数只读原文件，在内存返回新张量，不写NPZ、不修改模型。

读取同一次NPZ/JSON字节快照并核对哈希后检查：

1. JSON的unit等于文件stem，belt/L等于本次协议；case、placement、contact、unit共同标识源单元。code_hash/config_hash随输入身份返回；函数不把任意哈希值自动认定为已接受的生产版本。
2. 16_adjacent驱动偏移1、M208；32_skip4偏移5、M928。drives和meas的**有序**内容必须匹配当前模型，不能只检查token数。baseline索引为整数、范围有效，states行数和各行baseline必须与base_of_pair吻合。
3. cur[n]、images[n]和states[n]保持源单元的同一row；ref= v_ref[base_of_pair[n]]。图像目标绝不跨belt复用。source列表顺序由调用者冻结，单元内顺序为row0..N-1；不自动排序或重排。
4. 每帧ID为`(NPZ_SHA, sidecar_SHA, case, placement, belt, contact, unit, pair_index, baseline_index)`。同源重复输入拒绝；后续batch idx有放回抽样可合法重复该帧ID，idx也需冻结。

哈希防止已冻结输入被替换，并不独立证明生成器的科学语义。若有人把错误目标与电压重新打包并同时提供新哈希，单靠shape/元数据无法判断；这需要可信来源和源生成证据。真实适配前须核对这条前提。当前只证明合成夹具和已保存S00证据的对应关系。

## 归一化约定及未决定事项

本次合成检查明确采用`per_belt_frozen_cohort_absmax`：

- source电压float32，image为float16/32；在完整、有序的本belt源集合上先转float32。
- `v=((v_cur-v_ref[base_of_pair])/mean(abs(v_ref[base_of_pair]),axis=1))*100`，逐帧参考分母；无epsilon、裁剪或重采样。非有限值/分母<=0在训练前拒绝。
- `scale=max(abs(concat(this_belt_images)))`，完整本belt集合求一次，正且finite；`y0=(images/scale)[:,None]`。scale在整批与所有微批间保持不变，不在微批内重算。
- 这沿用旧入口的计算公式，但把目标集合限制为本belt的配对源；旧共享images scale不再沿用。正式训练采用每belt scale、统一scale还是其它冻结训练集统计，仍由协调决定；本任务不据此改变正式实验。未来若更改scale，需另立输入版本，不静默替换本检查。

接口返回v、y0、scale、frame_ids、source身份、protocol和normalization；不传J_img，因此仅覆盖pre/dec（GN=SAMPLING=0）。物理采样/GN的J_scale恢复及物理量单位不在本次修复范围。

## 已执行与待执行

`tests/paired_fixture.py`对每belt生成两个placement，每单元2个baseline×2帧，共8帧。图像随belt/placement/row改变，电压扰动由同一图像的空间均值构造。这仅是可检验的合成配对关系，不是CEM物理模拟或真实病例。

10项NumPy检查验证上述关系、参考展开和拒绝行为；既有4项代数/源码检查继续保留。完整模型数值脚本使用这个夹具，经同一个loader得到v/y0，再一次性抽取B64 idx及mask/t/noise；比较同初值B64与B32×2/B16×4及CKPT。参考仍用原始mean损失，损失与更新容差完全沿用VALIDATION_PLAN，**未放宽**。

完整模型脚本还准备记录v/y0/idx/mask/t/noise及初始权重SHA256、选中帧ID；临时夹具文件读取后清理。NPZ容器哈希可能含封装差异，跨运行固定输入的比较以dtype/shape和张量payload哈希为准。依赖缺torch/numpy时退出2/NOT_RUN；没有这些哈希的真实模型结果不能称完成此验收。本次无torch，因此这48组及张量/权重运行时哈希均未产生。

真实配对NPZ尚未在本地适配或运行；不能以合成NumPy通过宣称真实输入或模型等价通过。后续C2仍由S00处理，使用S01接受运行器，且只在当前账号自有候选目录落盘。
