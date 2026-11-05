# S02 R5：接受用于一次C2/KML严格数值对照

日期：2026-11-05。决定：**ACCEPTED_LOCAL_WRAPPER_FOR_ONE_BOUNDED_C2_KML_STRICT_COMPARISON**。

总协调已读取R5报告、最小diff、同PID守卫、实际入口与交接命令，独立核对42项交付索引、ZIP全部20成员及19项来源哈希，并在自己的临时副本复跑14项守卫测试，全部通过。原模型/loader/比较器等冻结来源相符，7个计算/比较函数AST与R3一致；固定case大小和SHA重新核验通过。原件及源码包未改。

- 根：work/S02/round5_cpu36_20261105T032617Z，work/相对c2/stage4_sessions。
- 代码包：package/S02_CPU36_R5_CODE.zip，50873字节，SHA256为64605deb9a08de087a42f9026272a18bfed1d1896acdd449852ed2837aa43003。
- case：work/S02/round3_20261104T134939Z/case/fixed_16_pre.pt，271979513字节，SHA256为4de1fb40eb1c4b43a8747586399f336bf9e37184592d66fdbf711abad8469846。ZIP不含case，远端如无同一已核验文件，S00需单独上传本次确切文件。
- 场景：一组16_adjacent/pre、backend=kml/mode=strict、B64对micro32×2、fp32/CKPT0/fresh/HBM0；首选分配38核、实际选36留2核，24576MB及同值限制、最多900秒。

接受的是本地运行包装，实际Linux语法、现场绑定/库调用和完整数值结果仍待新job。Windows194项严格失败和原容差保留，内存收益未接受。7个同PID checkpoint属于本包自己的证据，不冒称连续线程采样或复用R7旧监测。

## 提交命令的必要补充

R5交接命令在登录端source runtime.env后会把PATH重置为venv/bin:/usr/bin:/bin，随后直接调用dsub，漏了恢复Donau环境这一步。S00应在所有预提交校验通过后、调用dsub之前执行：

```bash
source /etc/profile.d/donaukit_scheduler.sh
command -v dsub
```

这是S00提交层补充，原R5 ZIP和source清单不需要修改。若仍找不到调度器则停在提交前，不重复模型环境测试。实际job入口run_s00_job.sh继续按原包加载冻结运行环境。

S00先核对已有队列避免重复，然后使用新目录/新job执行一次。退出0仅为固定合成case通过；退出1必须同时有FAIL_ORIGINAL_CRITERIA与全指标才作数值失败；退出2/超时/缺结果均为运行或证据问题。完整回传资源/终态、case/源码/后端身份、7项CPU证据、全部metrics/failures、原退出和日志；不改阈值或追加矩阵。

独立复核机读结果：S02_CPU36_R5_REVIEW.json；测试原始输出：S02_CPU36_R5_GUARD_TESTS.txt。
