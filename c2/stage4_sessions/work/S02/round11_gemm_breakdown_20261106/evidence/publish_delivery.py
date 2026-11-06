"""Freeze the R11 observation package and publish the fixed S02 handoff."""
from datetime import datetime,timezone
import difflib
import hashlib
import json
from pathlib import Path
import zipfile

ROOT=Path(__file__).resolve().parents[1]


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def asset(p):return dict(path=str(p.resolve()),bytes=p.stat().st_size,sha256=sha(p))


def save(p,v):p.write_text(json.dumps(v,indent=2)+'\n',encoding='utf-8')


if __name__=='__main__':
    assert not (ROOT/'GEMM_READY.json').exists(),'published source/package must not be hot-edited'
    checks=json.loads((ROOT/'evidence/local_validation.json').read_text());assert checks['status']=='PASS_LOCAL_PREPARED_FAKE_CBLAS_ONLY'
    source=json.loads((ROOT/'SOURCE_SHA256.json').read_text());assert len(source)==26 and all(sha(ROOT/k)==v for k,v in source.items())
    assert sha(ROOT/'baseline/kml_ops.py')=='e6c5c4411c453c8168939cd51d737a7e9d8232bdfff05da3967805a5e917ff26'
    diff=[]
    for a,b in [('reference/train_profile5.py','train_gemm5.py'),('reference/run_profile5.sh','run_gemm5.sh')]:
        diff.extend(difflib.unified_diff((ROOT/a).read_text().splitlines(True),(ROOT/b).read_text().splitlines(True),fromfile='R9/'+a,tofile='R11/'+b))
    for name in ['gemm_observer.py','tests/test_gemm_observer.py']:
        diff.extend(difflib.unified_diff([],(ROOT/name).read_text().splitlines(True),fromfile='/dev/null',tofile='R11/'+name))
    patch=ROOT/'diff/R9_TO_R11_OBSERVATION.patch';patch.write_text(''.join(diff),encoding='utf-8')
    package=ROOT/'package/S02_R11_GEMM5_CODE.zip';names=sorted([*source,'SOURCE_SHA256.json'])
    with zipfile.ZipFile(package,'x',zipfile.ZIP_DEFLATED) as z:
        for name in names:z.write(ROOT/name,name)
    with zipfile.ZipFile(package) as z:
        assert z.namelist()==names and all(hashlib.sha256(z.read(n)).hexdigest()==sha(ROOT/n) for n in names)
    save(ROOT/'package/PACKAGE_MANIFEST.json',dict(status='PASS_ZIP_CONTENT_SHA',package=asset(package),file_count=len(names),files={n:asset(ROOT/n) for n in names}))
    report=f'''# S02 R11：原基线KML调用分解准备完成

2026-11-06（Asia/Shanghai）。S02仅准备接口、可撤销观测和冻结包；没有提交集群、读取真实NPZ或执行完整Encoder。按R11任务卡由S00新部署、S01精确SHA专项PASS后直接唯一执行，无需用户中转。S02不操作其它窗口目录或共享Git。

## R10处置

R10保留，CLOSED_NOT_SELECTED_LOW_BENEFIT；不是数值FAIL，不集成、不安排其20更新A/B。R10_READY及候选原件SHA未改，新处置记录R10_DISPOSITION.json。此包仅含未改原baseline，KML源码SHA=e6c5c4411c453c8168939cd51d737a7e9d8232bdfff05da3967805a5e917ff26，不包含R10候选实现。

只读核S08归因就绪文件及5个指定归因资产；用作本轮观测边界依据，不重跑解析/训练。R9复制归属不全在Linear，不能凭copy次数选优化；本轮只补实际GEMM元数据和调用边界证据，不作新性能收益结论。

## 接口先交与原数据门禁

INTERFACE_READY.json已先于代码发布，接口SHA={sha(ROOT/'INTERFACE.json')}，保持不变。新协议ENGINEERING_REAL_CORPUS_GEMM5_V1；原输入协议/descriptor SHA=b88ea9745147acf7fa70d51dc27c727f22f14e98af5dff1b80a9047e95648cd6、16单元/1600统计帧/seed0/原前320训练帧、初始化/scale/frame/mask及原15项loss门槛不变。

原engineering_data.py与其原INTERFACE.json字节一并存入data_gate/，入口显式从那里导入。原8b1b…接口继续约束旧descriptor；顶层1477…接口仅定义R11交接。这避免用新接口SHA替换旧描述或静默放宽数据门禁。本地已验证S00原descriptor元数据兼容；实际manifest/NPZ/sidecar与源前后核验仍由原门禁及S00执行。新账本在outputs/gemm_JOBID，旧运行清单/checkpoint不写。正式split/subject UNKNOWN，无val/test/科学接受。

## 最小观测及可解释范围

沿R9已跑通入口保留完整Encoder37995777/fp32/CKPT0/native SDPA/KML、原mean双loss/AdamW、实际CPU36/全部TID、源/库/有限性/暴露/保存及零更新恢复。共17份复用文件字节一致；R9/原工程源码及历史失败不改。新入口取消完整Torch profiler，只在训练第3—5更新用context manager临时包裹原counted gemm、_sgemm和Linear forward/backward两个调用点；前2更新不挂，保存/恢复/诊断不挂。

每个original GEMM与_sgemm函数恰调用一次、原对象/位置及关键字参数原样转发。raw14个SGEMM参数与原row-major/flags/m/n/k/alpha/beta/lda/ldb/ldc和A/B/C指针一致才允许调用。真实入口还要求_sgemm为ctypes._CFuncPtr，拒绝Python替身或错误模块来源。baseline和observer实际导入路径/SHA记入result，临时hook四处在finally恢复，成功/异常/限额/导出失败均覆盖。

记录每次A/B shape/stride/dtype/连续性、flags/beta、m/n/k、raw_sgemm标量参数、输出shape/storage alias布尔、线程/调用序号/父调用及monotonic ns起止。不复制或打印Tensor值，不改RNG。role仅由已核Linear上下文及flags确定forward/dX/dW，其余UNKNOWN。线程local栈和全步序号防串；嵌套保留parent，不相加父子inclusive或跨线程区间当程序wall。

gemm_wall包住原counted GEMM；ctypes_wall包住同次原_sgemm，含Python参数转换/库内部打包/调度/计算，**不是纯微内核时间**。outer_minus_ctypes含gemm内部准备/计数/分配及观测bookkeeping，metadata前后和_sgemm hook bookkeeping另记；仍不能精确扣除全部context/timer开销。A/B是已准备操作数，Linear前面的reshape/bias预填不在此边界内。观察只覆盖这149次直接kml_ops调用，不覆盖Torch内部所有BLAS。本轮不是A/B或正式吞吐验证。

最多3份详细文件gemm_step_3/4/5.json，各<=1MiB、每步<=256条且必须149条完整一一对应，不截断、不重试。失败也尽量写同一有界文件并标FAILED；超字节上限不写大文件，错误和计数留result。原first5 KML计数及15项loss门槛不改；缺配/多配/源/CPU/库/数值/能力/限额异常即停止。

## 实际本地检查

9项LOCAL_FAKE_CBLAS_ONLY检查通过：单次原调用/参数形式和对象/输出及输入权重bias梯度/RNG一致；连续5步AdamW最终参数与状态完全相同、仅3—5记录；异常恢复4处hook；双线程隔离、嵌套父关系；缺native/重复native/无外层native、计数和字节限额及能力拒绝。替身使用真实Tensor接口和原baseline Python GEMM函数，但没有实际KML或完整模型；不扩大成C2数值通过。

另3种CLI框架前拒绝（缺描述、正式协议混入、B32）、Python3.9 AST/LF/Git Bash -n、observer无Tensor值复制/转储代码、原data_gate兼容及来源/ZIP逐项SHA通过。旧5315/R10矩阵不重跑。证据evidence/local_validation.json及observer_final.log，原始检查/失败分支保留。

## 交付和停点

包：{package.resolve()}；{package.stat().st_size}bytes/{len(names)}文件；SHA256={sha(package)}。
源码清单SHA256={sha(ROOT/'SOURCE_SHA256.json')}；observer SHA256={sha(ROOT/'gemm_observer.py')}。
命令/资源/收集见{(ROOT/'C2_HANDOFF.md').resolve()}；契约GEMM_CONTRACT.json；差异{patch.resolve()}；package/PACKAGE_MANIFEST.json逐文件索引；GEMM_READY.json固定就绪。

本轮S02真实KML观测0、完整Encoder0、新job0；旧原件和门槛不动。尚存实质验证为S01代码/部署专项审核及S00唯一C2采集中的真实调用一一对应、原loss/CPU/库/保存恢复和终态清理。按当前任务卡新授权，S01 PASS绑定相同SHA后S00直接执行单域38/实际36、DDR24576MB同limit/exclusive、900秒作业；全入口840+清理30+收尾30，内部720秒停新更新，达到5即结束。失败停、不重试、不扩资源、不跑R10 A/B。

发布后源码/包不热改。精确Git候选ARCHIVE_FILES.json排除ZIP/数据/权重/环境；没有暂存/提交/推送。S02可在有限等待内只读接收S01具体审核意见，运行与终态由S00负责。
'''
    (ROOT/'REPORT.md').write_text(report,encoding='utf-8')
    ready=dict(status='GEMM_READY',preparation_status='LOCAL_PREPARED_FAKE_CBLAS_CHECKED_NOT_C2_RUN',protocol='ENGINEERING_REAL_CORPUS_GEMM5_V1',
        published_utc=datetime.now(timezone.utc).isoformat(),immutable_after_publish=True,
        package=asset(package),source_manifest=asset(ROOT/'SOURCE_SHA256.json'),source_manifest_name='SOURCE_SHA256.json',
        interface=asset(ROOT/'INTERFACE.json'),contract=asset(ROOT/'GEMM_CONTRACT.json'),reference=asset(ROOT/'REFERENCE_FIRST5.json'),
        checks=asset(ROOT/'evidence/local_validation.json'),report=asset(ROOT/'REPORT.md'),commands=asset(ROOT/'C2_HANDOFF.md'),
        baseline=asset(ROOT/'baseline/kml_ops.py'),observer=asset(ROOT/'gemm_observer.py'),diff=asset(patch),
        package_manifest=asset(ROOT/'package/PACKAGE_MANIFEST.json'),original_data_interface=asset(ROOT/'data_gate/INTERFACE.json'),
        R10_disposition=asset(ROOT/'R10_DISPOSITION.json'),entrypoint='run_gemm5.sh',file_count=len(names),new_jobs=0,
        actual_KML_observation='NOT_RUN_BY_S02',full_encoder_runs=0,engineering_only=True,formal_split_status='UNKNOWN',
        subject_mapping_status='UNKNOWN',validation_status='NOT_RUN_NO_FORMAL_SPLIT',
        resources=json.loads((ROOT/'GEMM_CONTRACT.json').read_text())['resources'],
        next_action='S00 new deployment; S01 SHA-bound PASS_FOR_ENGINEERING_GEMM5 then S00 single task-card-authorized run; no user forwarding needed')
    temporary=ROOT/'GEMM_READY.tmp';save(temporary,ready);temporary.replace(ROOT/'GEMM_READY.json')
    print(json.dumps(ready,indent=2))
