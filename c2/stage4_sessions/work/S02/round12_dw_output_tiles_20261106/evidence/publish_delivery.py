"""Freeze the one fixed R12 candidate after its local fail-fast screen."""
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
    assert not (ROOT/'R12_READY.json').exists(),'no hot edits after ready publication'
    validation=json.loads((ROOT/'evidence/local_validation.json').read_text());assert validation['status']=='PASS_LOCAL_SCREEN_FIXED_CANDIDATE_ONLY'
    sources=json.loads((ROOT/'SOURCE_SHA256.json').read_text());assert len(sources)==26 and all(sha(ROOT/k)==v for k,v in sources.items())
    diff=ROOT/'diff/CANDIDATE_ONLY.patch'
    diff.write_text(''.join(difflib.unified_diff((ROOT/'baseline/kml_ops.py').read_text().splitlines(True),
        (ROOT/'candidate/kml_ops.py').read_text().splitlines(True),fromfile='frozen/baseline/kml_ops.py',tofile='candidate/kml_ops.py')),encoding='utf-8')
    package=ROOT/'package/S02_R12_DW_TWO_COLUMN_TILES.zip';names=sorted([*sources,'SOURCE_SHA256.json'])
    with zipfile.ZipFile(package,'x',zipfile.ZIP_DEFLATED) as z:
        for n in names:z.write(ROOT/n,n)
    with zipfile.ZipFile(package) as z:assert z.namelist()==names and all(hashlib.sha256(z.read(n)).hexdigest()==sha(ROOT/n) for n in names)
    save(ROOT/'package/PACKAGE_MANIFEST.json',dict(status='PASS_ZIP_CONTENT_SHA',package=asset(package),files={n:asset(ROOT/n) for n in names},file_count=len(names)))
    report=f'''# S02 R12：固定dW输出列两块候选

2026-11-06（Asia/Shanghai）；仅一个固定方案、本轮本地准备，不提交集群、不默认集成。状态LOCAL_SCREEN_PASS_PENDING_ACTUAL_KML。原数值门槛、模型/损失/AdamW/数据/精度/CPU36/KML不变。

## 实际目标与实现选择

只读核R11 job2049454/cn21338的8份绑定原件（result/steps/audit/review/reference及3份GEMM记录）和协调复核；未SSH/读NPZ/权重或重跑模型。三采样各12次dW目标(m,n,k)=(512,2048,13312)、ta=True/tb=False/beta0，实际A[13312,512]、B[13312,2048]，lda512/ldb2048/ldc2048。该组ctypes区间合计374.199378/377.310428/378.006874ms，仍非纯内核、不作本轮性能对照。原记录与例子见evidence/TARGET_FROM_R11.json。

编码前方案和固定fixture见DECISION_BEFORE_CODE.md。唯一改动在gemm原fp32路径：精确形状/CPU/contiguous/ta=True/tb=False/beta0/out=None/acc32False才走两块。一次最终contiguous C[512,2048]分配；列0和1024分别调用原_sgemm，n=1024、k完整13312，A不动，B/C起点各偏移0/4096bytes，lda512/ldb2048/ldc2048、alpha1/beta0和转置语义不变。两个输出列区间不重叠，没有拆batch/K、没有部分梯度累加、没有子view contiguous后忘回写、没有大操作数复制或权重缓存。

原输入/输出stride及float32 itemsize/4byte对齐、C不alias A/B、A/B/C末访问索引和列范围均断言。最大索引A=6815743、B=27262975、C=1048575，恰为各自numel-1。所有其它shape/flags/out/精度保留原路径；forward/dX/bias/gb和所有其它函数AST与原baseline一致。最小diff：{diff.resolve()}。原baseline SHA={validation['baseline_sha256']}；唯一candidate SHA={validation['candidate_sha256']}。不加载R10视图候选，R9/R11/R10与历史失败均保留不改。

## 数值及alias风险

完整K仅保持数学归约范围，不保证KML因N变化仍用相同内部累加/打包/舍入路径；也可能重复打包、多一次调用更慢。原tensor/state/exact比较器不变；任何首次ABI或本地/实际KML数值FAIL即保留并关闭这一固定候选，不换tile、fixture尺度、精度或阈值。

实际输入不变、输出不alias，完整最终C直到两次调用完成才返回；不复用autograd持有输出。库内部是否打包或多复制仍未知，不能用Python侧无复制证明库内成本下降。

## 已完成本地筛选

5项fail-fast候选检查通过：①真实目标尺寸的ABI/pointer偏移/lda-ldb-ldc/完整K和输出canary、输入不变；②其它输入fallback、alias和misalignment拒绝；③完整目标输出；④目标线性forward、输入梯度、dW和bias梯度；⑤连续5次原AdamW参数/梯度/delta/step/一二矩。原比较器30项最大绝差与相对误差均0，step exact另核。数学实现是本地假CBLAS接口内的native Torch matmul，不是实际KML；直接dW注入的五步AdamW不是完整Encoder五步训练，真实语料完整gate仍待C2。

另4项轻量运行契约检查通过：原生计数不隐藏为149、失败/旧receipt/source/node/job/CPU拒绝、与原逻辑shape日志一致、strict5→perf25和前5/后20不可缩步。2种CLI路径拒绝为预期负例，不是候选数值失败。Python3.9 AST/LF/bash-n、14份冻结复用文件/26份R11源、原件SHA、输入/输出导入身份和ZIP逐项SHA通过。没有重跑旧5315或无关模型矩阵。

本地实际导入路径与gemm代码来源匹配，IMPORT_IDENTITY.json明确_lib未加载、不是KML；核验为screen后的只读import身份确认，未重跑数值。evidence/native_screen_first.log/native_screen.json保留首次筛选；evidence/local_validation.json及runtime_contract_final.log列本轮实际检查。

## 计数及有限同节点提案

逻辑GEMM149/步和目标逻辑12/步保持；实际直接_sgemm baseline149、candidate161，目标full12→0、目标native tiles0→24，候选dispatch12。runtime_counts与训练入口同时核所有计数，实际导入/模块/原生签名频数均记录，不能藏第二次native让149假过。原R11一对一observer不用于这个候选。恢复小batch K416不匹配，不触发tile；不把直接_sgemm计数叫Torch内部全部BLAS。

具体命令及停止条件见{(ROOT/'AB_PROPOSAL.md').resolve()}，附screen_target.py/train_dw_ab.py/run_ab_proposal.sh。先新授权实际KML完整目标shape/ABI/canary筛选，再完整Encoder严格5步配对（输出/loss/输入梯度/所有参数梯度/参数/delta/AdamW状态）；均过后，同节点同job同CPU/库的独立baseline/candidate进程各原1600帧单epoch25更新，前5预热后20观察、无profiler、两侧诊断/CPU/KML/暴露/保存恢复一致并分项计时。原25步frame/mask身份取自job2043445绑定steps，源/库/framework/env和receipt跨阶段核对。

最多完整模型60更新（严格5x2+性能25x2），只1对，整体900秒：840共享全入口+清理30+收尾30；单域38分配/实际36、24GiB同limit/exclusive/HBM0。预算不足INCOMPLETE，不缩到短采样/扩资源/续跑或重提。S00须另备原生资源/新唯一marker/所属进程清理，旧job授权不用。只按同节点后20步总训练调用耗时/波动判断价值，孤立GEMM变快不替代训练收益，RSS/HWM只作独立进程相同采样范围。无收益关闭、不搜索替代块宽。

## 冻结交付和待验证

包：{package.resolve()}；{package.stat().st_size}bytes/{len(names)}文件；SHA256={sha(package)}。
SOURCE_SHA256.json SHA256={sha(ROOT/'SOURCE_SHA256.json')}。
R12_READY.json绑定候选/基线/包/源码/契约/diff/检查/提案/实际导入身份；package/PACKAGE_MANIFEST.json逐文件核SHA。

本轮真实KML目标筛选0、完整Encoder0、同节点A/B0、新job0；原正式subject/split UNKNOWN，无val/test或科学/生产/稳态加速接受。无已知本地数值失败；实际KML、完整5步严格门槛及25步同机收益仍未知。交协调核定后另派01审核/00执行，本轮不提交、不集成。精确Git候选ARCHIVE_FILES.json排除ZIP/真实数据/权重/环境，未操作共享暂存/提交/推送。
'''
    (ROOT/'REPORT.md').write_text(report,encoding='utf-8')
    ready=dict(status='LOCAL_SCREEN_PASS_PENDING_ACTUAL_KML',candidate='R12_FIXED_DW_N2048_TWO_N1024_FULL_K13312',published_utc=datetime.now(timezone.utc).isoformat(),immutable_after_publish=True,
        package=asset(package),source_manifest=asset(ROOT/'SOURCE_SHA256.json'),baseline=asset(ROOT/'baseline/kml_ops.py'),candidate_source=asset(ROOT/'candidate/kml_ops.py'),
        contract=asset(ROOT/'R12_CONTRACT.json'),diff=asset(diff),checks=asset(ROOT/'evidence/local_validation.json'),local_numeric=asset(ROOT/'evidence/native_screen.json'),
        import_identity=asset(ROOT/'evidence/IMPORT_IDENTITY.json'),target_evidence=asset(ROOT/'evidence/TARGET_FROM_R11.json'),report=asset(ROOT/'REPORT.md'),proposal=asset(ROOT/'AB_PROPOSAL.md'),
        package_manifest=asset(ROOT/'package/PACKAGE_MANIFEST.json'),entrypoint='run_ab_proposal.sh',file_count=len(names),
        actual_KML_target='NOT_RUN',full_encoder_strict='NOT_RUN',same_node_AB='NOT_RUN',new_jobs=0,default_integrated=False,execution_authorized=False,
        next='Coordinator decision, new S01 SHA-bound review, then new S00 execution authorization; first numerical FAIL closes this fixed candidate')
    temp=ROOT/'R12_READY.tmp';save(temp,ready);temp.replace(ROOT/'R12_READY.json');print(json.dumps(ready,indent=2))
