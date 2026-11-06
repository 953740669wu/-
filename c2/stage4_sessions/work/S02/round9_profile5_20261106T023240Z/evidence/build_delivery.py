"""Create immutable source/package identities after local verification only."""
from datetime import datetime,timezone
import difflib
import hashlib
import json
from pathlib import Path
import zipfile

ROOT=Path(__file__).resolve().parents[1]


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def asset(path):return dict(path=str(path.resolve()),bytes=path.stat().st_size,sha256=sha(path))


def save(path,value):path.write_text(json.dumps(value,indent=2)+'\n',encoding='utf-8')


if __name__=='__main__':
    assert not (ROOT/'PROFILE_READY.json').exists(),'do not hot-edit/republish a frozen delivery'
    validation=json.loads((ROOT/'evidence/local_validation.json').read_text())
    assert validation['status']=='PASS_LOCAL_PREPARED_NOT_C2_PROFILED'
    source=json.loads((ROOT/'SOURCE_SHA256.json').read_text());assert len(source)==24
    assert all(sha(ROOT/k)==v for k,v in source.items())
    patch=[]
    for before,after in [('train_engineering.py','train_profile5.py'),('run_engineering.sh','run_profile5.sh')]:
        patch.extend(difflib.unified_diff((ROOT/before).read_text().splitlines(True),(ROOT/after).read_text().splitlines(True),
                                        fromfile='frozen/'+before,tofile='profile5/'+after))
    for name in ['profile_probe.py','profile_contract.py','tests/test_profile5.py','PROFILE_CONTRACT.json']:
        patch.extend(difflib.unified_diff([],(ROOT/name).read_text().splitlines(True),fromfile='/dev/null',tofile='profile5/'+name))
    diff=ROOT/'diff/FROZEN_TO_PROFILE5.patch';diff.write_text(''.join(patch),encoding='utf-8')
    package=ROOT/'package/S02_R9_PROFILE5_CODE.zip';assert not package.exists()
    names=sorted([*source,'SOURCE_SHA256.json'])
    with zipfile.ZipFile(package,'x',zipfile.ZIP_DEFLATED) as z:
        for name in names:z.write(ROOT/name,name)
    with zipfile.ZipFile(package) as z:
        assert z.namelist()==names and all(hashlib.sha256(z.read(n)).hexdigest()==sha(ROOT/n) for n in names)
    save(ROOT/'package/PACKAGE_MANIFEST.json',dict(status='PASS_ZIP_FILE_SHA',package=asset(package),file_count=len(names),
                                               files={n:asset(ROOT/n) for n in names}))
    analysis=json.loads((ROOT/'evidence/BASELINE_TIMING.json').read_text());timing=analysis['timing']
    label={'training_step_seconds':'训练步骤合计','diagnostic_seconds':'可区分逐步诊断','checkpoint_and_recovery_seconds':'保存/恢复范围',
           'data_loading_seconds':'数据读取/归一化范围','batch_materialization_seconds':'批物化','unattributed_seconds':'未归属范围'}
    rows='\n'.join(f"| {label[k]} | {timing[k]:.6f} | {analysis['share_of_python_wall_percent'][k]:.2f}% |" for k in label)
    report=f'''# S02 R9：已有耗时分析与有限剖析包

2026-11-06（Asia/Shanghai）。仅完成AFTER_ENGINEERING_PILOT_20261106任务卡S02节；没有新集群提交、环境安装或生产默认变更。原activation checkpoint候选维持结案。

## 先看已有证据

只读核RUN_COMPLETE绑定的7份原件bytes/SHA、原25行steps及result、RUN_AUDIT和协调运行复核JSON；未SSH实查、未下载权重、未读取NPZ或重跑模型。唯一基线job2043445/cn21341：工程成功、25次连续AdamW/1600帧；程序计时86.690500秒，调度96节点秒另计，不相加。详细身份及重新求和见evidence/BASELINE_TIMING.json、local_validation.json。这里只继承已收原件所能证明的工程结果，不扩大科学/性能验收。

| 原记录范围 | 秒 | 程序wall占比 |
|---|---:|---:|
{rows}

训练中位2.329944秒，首两步2.830396/2.355097秒；这些只是已记录不同batch的时间，不推导稳态或退化。读取范围含train归一化和加载暴露写入；诊断含mask/更新前账本、CPU前后快照、参数/梯度/AdamW检查；保存恢复范围含其CPU/账本检查，均不称纯I/O或纯内核时间。未归属16.341825秒可能分布在原源码中的框架/库导入、源/数据哈希、模型初始化和权重哈希、其它CPU检查及日志/账本确认等段；这些子段没有独立计时，不能分摊到某一项。程序计时亦不包含末尾最终JSON写出、包装及调度全部开销。

目前attention、KML linear、其它反向和AdamW各占多少均未知；没有operator trace，不把历史233帧/s或其它不同范围数字拿来计算退化/加速。interop=608只是原getter观察值，原59次快照最多36个TID，不能推断实际启动608线程，也不据此调默认。

## 下一项优化应先看哪里

1. **训练路径优先**：67.46%是最大已测范围；先取得forward/loss、backward、optimizer及zero_grad相邻阶段壁钟，再看后3步CPU事件。attention和KML线性/布局/分配、其它反向、AdamW是同级待分辨候选，目前没有证据给它们内部排序。若native SDPA事件突出，再考虑attention路径；若KML包裹突出，再查linear布局/分配/调用边界；若optimizer阶段突出，再查AdamW算子。均须先有本包真实剖析，不先改算法。
2. **启动/未归属范围其次**：18.85%具有工程排查价值，但尚未细分，不能宣称某项导入/哈希慢。本轮不为凑比例删来源门禁。
3. **保留诊断的开销可审视**：7.89%已有边界，不能通过删检查制造提速；日志/账本与快照的后续优化仍需保持证据功能并另作对照。
4. **批物化和读取优先级较低**：本记录合计约1.08%；保存恢复范围4.72%另计。本轮不开展缓存/归一化算法/保存算法或activation checkpoint搜索。

## 本包的最小变化

16份复用文件与冻结工程包字节一致，包括完整Encoder/KML、loss/AdamW/保存恢复、配对/工程门禁、CPU36守卫、运行环境和原阈值比较器。原冻结入口及包没有改动。新train_profile5.py从该入口仅加入固定5步/身份/剖析控制，新profile_probe.py按原表达式及操作顺序给阶段计时/CPU事件；新profile_contract.py绑定原1600帧和前5步参考。最小diff为{diff.resolve()}。原数据/诊断/CPU/KML/保存恢复不删除，不改线程/interop默认。

B64、seed0、前5次连续更新，无重置AdamW、无样本补尾；1—2预热，3—5各采样1次。逐步核原frame顺序/ID哈希、mask/初始权重/归一化/实际KML计数，loss沿用原比较器阈值。读取仍为原1600工程帧，训练确认消费320帧，暴露记录区分加载用于统计和实际消费；旧descriptor/runtime ledger路径只读，新运行账本在新profile_JOB目录。checkpoint算法及工程标签不变，identity绑定新profile源码/配置，恢复额外更新0。

CPU profiler只使用已装Torch能力，缺失则UNSUPPORTED_PROFILER停止。每次最多50000事件（单次采集结束后查上限）；最多256个KML标记、3份<=8MiB trace、3份<=1MiB摘要，trace+摘要总上限27MiB，超限不截断/不重试。现有API无法逐事件硬取消采集，完整采集受单步及整体时限约束，此限制在PROFILE_CONTRACT.json明确记录。raw trace保留父事件/线程ID，摘要最多80个self CPU key；不相加嵌套total或把CPU事件合计当wall占比。

KML标记只说明Python/counter/分配/ctypes/native调用包裹，**不是精确原生内核时间**。profiler setup/start/stop/后处理导出单列，训练内部事件/标记扰动保留在step_seconds且无法凭此次采样精确扣除；全profiler调用wall另记，不能把采样速度当正式吞吐。CPU事件也不是操作系统进程CPU消耗或完整worker采样保证。

## 本地验证和交付身份

6项小型native Torch36夹具检查通过：连续5步对原函数loss/参数/AdamW逐项完全一致、RNG仅由同样mask推进、前2无采集后3各一份trace、五步checkpoint零额外更新恢复；另核能力缺失、CPU阶段事件缺失、乱序、固定身份漂移、KML标记委托/恢复及事件/文件上限拒绝。3种CLI拒绝（缺描述、正式协议混入、B32）在框架前生效；源码Python3.9 AST/LF、Git Bash -n、16文件冻结SHA、7份基线原件SHA及前5参考身份通过。测试没有完整Encoder或实际KML；数值精确一致仅限本地小夹具，不能扩展为C2完整模型已验证。

代码包：{package.resolve()}
bytes={package.stat().st_size}；files={len(names)}；SHA256={sha(package)}。
SOURCE_SHA256.json SHA256={sha(ROOT/'SOURCE_SHA256.json')}。
ZIP逐项内容核SHA通过，清单package/PACKAGE_MANIFEST.json；实际检查evidence/local_validation.json及日志。

## 未运行与下一步

本轮真实NPZ读取0、完整Encoder执行0、C2/KML剖析0、新job0；attention/linear/backward/optimizer热点仍未知，无性能或泛化结论。拟资源仅下一轮单NUMA38/实际36、24GiB请求同limit/exclusive、最多900秒，入口840+清理30+收尾30，720秒停止新更新、5更新完成即停。源/CPU/KML/数值/能力/采样限额/输出冲突/超时异常即停，不重试、不扩样/资源；无HBM/bf16/compile/decoder搜索，正式门禁不变。

命令、收集和停止条件见{(ROOT/'README.md').resolve()}及PROFILE_CONTRACT.json。先交协调复核，再另派S01绑定本包具体SHA审核和S00新部署/唯一marker；**旧900秒唯一作业授权已消耗，本包没有新执行授权**。S02无活动job，不查询或猜测其它远端任务。精确可Git归档清单ARCHIVE_FILES.json排除ZIP、真实数据、权重和环境；ZIP作为独立交付保留。没有操作共享Git暂存或提交推送。
'''
    (ROOT/'REPORT.md').write_text(report,encoding='utf-8')
    ready=dict(status='LOCAL_PREPARED_AWAITING_COORDINATOR_REVIEW',protocol='ENGINEERING_REAL_CORPUS_PROFILE5_V1',
        published_utc=datetime.now(timezone.utc).isoformat(),immutable_after_publish=True,engineering_only=True,
        package=asset(package),source_manifest=asset(ROOT/'SOURCE_SHA256.json'),file_count=len(names),
        contract=asset(ROOT/'PROFILE_CONTRACT.json'),reference=asset(ROOT/'REFERENCE_FIRST5.json'),
        checks=asset(ROOT/'evidence/local_validation.json'),report=asset(ROOT/'REPORT.md'),commands=asset(ROOT/'README.md'),
        diff=asset(diff),baseline_timing=asset(ROOT/'evidence/BASELINE_TIMING.json'),entrypoint='run_profile5.sh',
        resources=json.loads((ROOT/'PROFILE_CONTRACT.json').read_text())['resources'],new_jobs=0,
        C2_KML_profile_runs=0,operator_hotspots='UNKNOWN_NOT_PROFILED',execution_authorized=False,
        next_action='Coordinator review, then new S01 specific-SHA review and S00 new deployment/marker/authorization; do not reuse job2043445')
    temporary=ROOT/'PROFILE_READY.tmp';save(temporary,ready);temporary.replace(ROOT/'PROFILE_READY.json')
    print(json.dumps(ready,indent=2))
