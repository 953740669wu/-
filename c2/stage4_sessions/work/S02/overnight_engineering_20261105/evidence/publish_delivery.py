"""Freeze the verified S02 code/package before atomic CODE_READY publication."""
from datetime import datetime,timezone
import difflib
import json
from pathlib import Path
import zipfile
import hashlib

ROOT=Path(__file__).resolve().parents[1]


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def asset(p):return dict(path=str(p.resolve()),bytes=p.stat().st_size,sha256=sha(p))


def save(p,value):p.write_text(json.dumps(value,indent=2)+'\n',encoding='utf-8')


if __name__=='__main__':
    assert not (ROOT/'CODE_READY.json').exists(),'frozen delivery cannot be republished/hot-edited'
    checks=json.loads((ROOT/'evidence/local_validation.json').read_text());assert checks['status']=='PASS_LOCAL_PREPARED'
    source=json.loads((ROOT/'SOURCE_SHA256.json').read_text());assert all(sha(ROOT/k)==v for k,v in source.items())
    patch=[]
    for before,after in [('train_real.py','train_engineering.py'),('pilot_training.py','engineering_training.py'),('run_real_pilot.sh','run_engineering.sh')]:
        patch.extend(difflib.unified_diff((ROOT/before).read_text().splitlines(True),(ROOT/after).read_text().splitlines(True),
                                       fromfile='R8/'+before,tofile='engineering/'+after))
    for name in ['engineering_data.py','inspect_engineering.py','tests/test_engineering.py','tests/test_engineering_native.py']:
        patch.extend(difflib.unified_diff([],(ROOT/name).read_text().splitlines(True),fromfile='/dev/null',tofile='engineering/'+name))
    (ROOT/'diff/R8_TO_ENGINEERING.patch').write_text(''.join(patch),encoding='utf-8')
    package=ROOT/'package/S02_OVERNIGHT_ENGINEERING_CODE.zip';assert not package.exists()
    names=sorted([*source,'SOURCE_SHA256.json'])
    with zipfile.ZipFile(package,'x',zipfile.ZIP_DEFLATED) as archive:
        for name in names:archive.write(ROOT/name,name)
    with zipfile.ZipFile(package) as archive:
        assert archive.namelist()==names
        assert all(hashlib.sha256(archive.read(k)).hexdigest()==sha(ROOT/k) for k in names)
    manifest=dict(package=asset(package),files={k:asset(ROOT/k) for k in names},status='ZIP_CONTENT_SHA_MATCH',file_count=len(names))
    save(ROOT/'package/PACKAGE_MANIFEST.json',manifest)
    report=f'''# S02夜间工程入口（本地已准备）

依据OVERNIGHT_ENGINEERING_20261105，仅完成S02节。接口先于代码发布；代码/包就绪后冻结，不热改。S00_DATA_READY已收到且完成元数据兼容核验，无须等待正式split推进本次工程入口。原R8正式门禁和历史数值/内存证据不变，checkpoint优化任务保持结案。

## 交付与范围

完整Encoder37995777参数、fp32/CKPT0、原native SDPA/KML linear、原mean voltage/coarse双loss与AdamW。13个关键R8文件逐字节不变；engineering_training.py仅把checkpoint协议标签两处改为独立工程协议，模型/训练/恢复算法完全不变。新engineering_data.py明确隔离正式模式；train_engineering.py复用R8训练流程，移除正式val调用、加入暴露和计时。限时包装仅替换入口与工程环境变量。最小差异见diff/R8_TO_ENGINEERING.patch。

接口SHA：{sha(ROOT/'INTERFACE.json')}。
源码清单SHA：{sha(ROOT/'SOURCE_SHA256.json')}。
代码包：{package.resolve()}，{package.stat().st_size}bytes/{len(names)}文件，SHA256={sha(package)}。
精确文件及解包SHA见package/PACKAGE_MANIFEST.json；命令和资源边界见C2_HANDOFF.md。

## 数据与暴露

固定源为任务卡14300单元/1430000对/143case/3399057bytes manifest SHA=bdd146040bddf2ddd47fb9d571d5d2f40e5fa20fbd30d0c0d11239893e647032，工程源锚并非正式冻结。固定S00描述SHA=b88ea9745147acf7fa70d51dc27c727f22f14e98af5dff1b80a9047e95648cd6：s0285/s0593、16单元、1600帧。仅元数据和S00交接SHA已在S02本地核验；真实NPZ/manifest Linux路径没有在S02读取，实际来源/选样重算/文件SHA门禁必须由S00登录侧检查并由唯一作业再次执行。S00选样检查是119候选均具备至少8个合规单元的记录，入口按已发布接口重算选择，若不一致停止、不换样。

同unit/belt/pair配对、base_of_pair与states/电极顺序核验、原参考均值*100，工程train absmax只拟合一次，无val/test。所有工程标记显式UNKNOWN/NOT_RUN_NO_FORMAL_SPLIT；case不当subject。运行暴露清单先于模型工作创建，每次读取/更新前后原子持久化，区分selected、loaded、possibly-used interrupted update及confirmed frames，恢复探针另记0额外更新。失败/timeout保留清单；未来按真实subject映射排除工程暴露对象的最终测试，当前无无泄漏保证。

## 本地检查（非真实训练）

14项夹具/小型native Torch36检查通过：工程数据/隔离/来源锚/范围/顺序/暴露8项，小型连续多batch、原mean/AdamW表达式、独立工程checkpoint零更新恢复3项，复用配对/状态顺序/电极顺序、零参考与cross-belt/SHA异常3项。实际2种CLI在框架前拒绝缺失描述或工程输入送正式入口；全部Python3.9 AST、LF、Git Bash -n、R8关键文件SHA、源码清单与ZIP逐项SHA核验通过。证据evidence/local_validation.json和各日志。

计时拆分Python入口内读取、batch物化、训练、诊断、checkpoint/恢复、未归属开销；诊断计时范围显式记录，外层部署/调度壁钟由S00收集。RSS/HWM为process_lifetime，不作逐步独占峰值或稳态性能结论。

## 未运行与停点

S02本轮真实NPZ读取0、完整模型训练0、C2/KML验证0、集群提交0；正式val/test不运行。Linux实际Torch36/全部TID/KML映射/GEMM、真实数值有限训练、checkpoint和恢复仍须唯一工程作业验证。当前无已知S02代码阻塞；S00部署及S01绑定精确SHA的专项审核是后续执行前提。S02不代交任务、不声明其它窗口活动job终态。失败/资源超限/SOURCE_CHANGED保留证据停止，无自动重试。

## 精确待归档范围

本目录INTERFACE.json、INTERFACE_READY.json、CODE_READY.json、SOURCE_SHA256.json、C2_HANDOFF.md、REPORT.md、diff/R8_TO_ENGINEERING.patch、package/PACKAGE_MANIFEST.json、package/S02_OVERNIGHT_ENGINEERING_CODE.zip、源码清单所列28文件，以及evidence/R8_INPUT_SHA256.json、S00_COMPATIBILITY.json、local_validation.json、验证日志和准备/发布脚本；另自身SESSION_STATUS.md与ROUND_DELTA.md。最终精确路径/SHA由ARCHIVE_FILES.json列举。仅元数据/代码/证据，无真实数据、权重或环境。没有暂存/提交/推送。
'''
    (ROOT/'REPORT.md').write_text(report,encoding='utf-8')
    ready=dict(status='CODE_READY',protocol='ENGINEERING_REAL_CORPUS_PILOT_V1',engineering_only=True,
               formal_split_status='UNKNOWN',validation_status='NOT_RUN_NO_FORMAL_SPLIT',subject_mapping_status='UNKNOWN',
               preparation_status='LOCAL_PREPARED',published_utc=datetime.now(timezone.utc).isoformat(),immutable_after_publish=True,
               interface=asset(ROOT/'INTERFACE.json'),interface_sha256=sha(ROOT/'INTERFACE.json'),package=asset(package),
               source_manifest=asset(ROOT/'SOURCE_SHA256.json'),source_manifest_name='SOURCE_SHA256.json',
               checks=dict(**asset(ROOT/'evidence/local_validation.json'),status=checks['status'],test_count=14),
               report=asset(ROOT/'REPORT.md'),diff=asset(ROOT/'diff/R8_TO_ENGINEERING.patch'),
               compatibility=asset(ROOT/'evidence/S00_COMPATIBILITY.json'),entrypoint='run_engineering.sh',
               entry_environment=['S02_ENGINEERING_DESCRIPTOR','S02_ENGINEERING_DESCRIPTOR_SHA256'],
               resources=json.loads((ROOT/'INTERFACE.json').read_text())['resources'],new_jobs=0,
               actual_full_encoder_training='NOT_RUN_BY_S02',required_next='S00 deploy/hash gate and S01 SHA-bound review before unique authorized job')
    temp=ROOT/'CODE_READY.tmp';save(temp,ready);temp.replace(ROOT/'CODE_READY.json')
    print(json.dumps(ready,indent=2))
