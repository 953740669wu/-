# S00 R6 诊断结果复核与 S01 修订指令

日期：2026-11-04。依据 S00/CPU36_R6_DIAGNOSTIC_REPORT.md、CPU36_READINESS.md 及 evidence/cpu36_r6_2026725 完整原始回传。本聊天未连接集群或提交作业。

## 接受结论

**ACCEPTED_DIAGNOSTIC_EVIDENCE / CPU36_MODEL_REVISION_REQUIRED**。

五组有限诊断已完成，足以指导环境及绑定检查的最小修订；尚未形成或验收新的36核完整模型入口，不能直接解锁S02或训练内存测试。

## 独立复核

- 完整ZIP SHA256 af5b01f9a7890d0bcaeb8c989e30a12ad64f65a6c40c5e7663d8d2f05d5b22b1，包内54文件与received副本逐字节一致。
- job2026725/cn21338，五组worker均exit0、无停止原因，SUMMARY为DIAGNOSTIC_DATA_COMPLETE。
- CPU receipt实际选0–35，预留36/37；全部2737行采样、30个阶段快照逐项检查，所记录线程非空掩码均为selected36子集。
- 39项内层COLLECTION的SHA/bytes核对一致，原始mtime_ns存在。未修改解包文件时间。
- 各组末阶段Torch intra-op：A=1；B/C/D/E=36。close组主线程掩码[0]；D绑定false时为0–35。以上与保存的原始worker和SUMMARY一致。

采样不能证明全部线程生命周期瞬间或精确in-region team成员；没有模型前后向或性能/内存验收。

## 可据此采用的修订方向

### 环境候选

下一版36核模型小试采用已实测的C组作为明确环境候选：OMP_NUM_THREADS=36、MKL_NUM_THREADS=36、OPENBLAS_NUM_THREADS=1、OMP_PLACES=cores、OMP_PROC_BIND=close，显式使用选中的36核/同域内存绑定。不要继续继承MKL=1。

该选择固定下一次模型验证的环境，不是正式生产默认或性能最优结论。B组unset也能令Torch为36；本轮选择显式36便于复现和核验，不额外搜索。E设置OPENBLAS=36时NumPy库API仍为1，没有证明其收益，因此不将E作为额外并行方案。实际Torch/KML/OMP路径和线程API仍需在模型进程内记录。

A/B/C对照支持在本次C2二进制/启动环境中，MKL=1是Torch默认intra-op为1的原因之一；不能推广为所有运行时行为的唯一根因。

### 绑定合同

以框架初始化前记录的调度授权集合和selected36为边界；模型运行中的相关TID必须非空且位于selected36，实际Torch intra-op须36。允许OpenMP将不同TID分别固定在单核；不能继续要求调用线程掩码始终等于整个36核集合。

保留CPU越界、核心不足/跨域/预留核占用、缺失线程证据、实际线程数1、模型配置/输入/库身份不符的拒绝检查。不把总TID数、掩码并集或某个runtime的omp_max单独作为36核接受依据；Torch inter-op报告608也不等于实际使用608个计算线程，继续记录实际TID而不凭元数据臆断。

## 现在交 S01 实施

1. 对实际五组原始结果作独立分析，确认上述候选配置与解释范围。
2. 在S01新修订目录修改运行器的线程/绑定记录与验收合同，保持R2、R6、历史失败及全部原证据不变。当前R6合同原型需接入真实发布/汇总路径，而不是只在独立测试里通过。
3. 补正负回归：每个TID单核且在selected36内可通过；任何TID触及预留/未授权核心失败；torch intra-op=1或缺记录失败；缺域/旧结果/退出失败/超时等既有保护继续有效；模型计算AST与已冻结版保持一致。
4. 给S00交付新候选SHA、包与环境契约、最小diff、模型提交前检查和回传字段。S00据此同时更新S01/S02包装器，不能继续用旧38/4核包。
5. S02同PID守卫也要区分框架初始化前36核授权与导入后各TID子集；不能为采用close而继续错误要求主线程导入后等于整个selected36。S02数值阈值/输入/模型不变。

S01修订审核后才安排下一次36核完整模型小试，资源不超过原24GiB/900秒、HBM0、16电极pre/dec、B32、三轮REPS1；当前不提交。小试通过后再恢复一组S02 C2等价检查，严格数值未过前训练内存仍NOT_READY。

## 可发给 S01

```text
S00已完成job2026725的R6诊断，总协调已核对完整54文件和全部样本。
请读取 work/S00/CPU36_R6_DIAGNOSTIC_REPORT.md
以及 work/COORDINATION/CPU36_DIAGNOSTIC_RESULT_REVIEW.md（work/相对c2/stage4_sessions）。
请形成新的36核模型运行器修订：以C组OMP36/MKL36/OpenBLAS1/close为下一次验证环境；实际torch intra-op必须36。
将调用线程掩码等于全集的旧检查，改为选中36核授权边界、全部相关TID子集与实际线程数的组合验收；保留越界/缺证据/线程数错的拒绝检查。
接入真实发布和汇总路径，补正负回归，保持模型计算与历史文件不变。
交付新候选SHA、最小diff及S00/S02包装器接口供总协调审核，暂不自行重跑完整模型。
```
