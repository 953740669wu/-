"""Add the executed round's support files without changing an already issued list."""
import csv
from hashlib import sha256
from pathlib import Path
import sys
import prepare_archive

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[4]
ROUNDS={
    'R18':('R18_FOREACH_FULL_CKPT','R16',('build_r18.py','review_r18.py','freeze_closed_round.py')),
    'R19':('R19_FTZ_REFERENCE','R18',('build_r19.py','review_r19.py')),
}


def main(label):
    version,previous,support=ROUNDS[label]
    tsv=HERE/f'GIT_ARCHIVE_{label}.tsv'
    assert not tsv.exists(), 'issued manifest is immutable'
    prepare_archive.main(label,version)
    paths={ROOT/r['path'] for r in csv.DictReader(tsv.open(encoding='utf-8'),delimiter='\t')}
    paths.update(HERE/n for n in support)
    if label=='R18':paths.add(HERE/version/'PRELIMINARY_ONLINE.json')
    if label=='R19':
        paths.update(HERE/version/n for n in ('EXTERNAL_REFERENCE.json','received/EXTERNAL_REFERENCE.json'))
        paths.update((HERE/version/'received/job_evidence/domains').glob('node*/strict_candidate/cpu_samples.jsonl'))
    md=HERE/f'GIT_ARCHIVE_{label}.md'
    md.write_text(f'''# 连续优化 {label} 闭合归档

本批只含{version}已闭合材料及实际执行的支持代码。先完成已发{previous}清单，再按本清单逐路径核大小/SHA；不重复旧1690路径批或前一批，不扩大至其他工作目录。基点为已核f365a772的正常后代；核实时HEAD/index/远端，漂移、无关暂存或分叉须停止说明。

唯一范围为同名TSV逐行路径加TSV自身。正常提交推送main，不改历史、不强推。回传commit、父提交、逐blob核验、遗漏/额外、实时远端和index。总协调收到回执后独立复核。模型、数据、动态库、传输ZIP、凭据和活动候选不入本批；活动状态以冻结COORDINATION_SNAPSHOT追溯。
''',encoding='utf-8')
    prior=HERE/f'GIT_ARCHIVE_{previous}.tsv'
    prior_paths={ROOT/r['path'] for r in csv.DictReader(prior.open(encoding='utf-8'),delimiter='\t')}
    assert not paths & prior_paths, 'duplicate paths from prior issued batch'
    rows=[]
    for p in sorted(paths):
        raw=p.read_bytes();rows.append((p.relative_to(ROOT).as_posix(),len(raw),sha256(raw).hexdigest()))
    with tsv.open('w',encoding='utf-8',newline='') as stream:
        writer=csv.writer(stream,delimiter='\t',lineterminator='\n');writer.writerow(('path','bytes','sha256'));writer.writerows(rows)
    raw=tsv.read_bytes();count=len(rows)+1;total=sum(r[1] for r in rows)+len(raw);digest=sha256(raw).hexdigest()
    (HERE/f'GIT_PROMPT_{label}.txt').write_text(f'''请在唯一Git窗口提交推送阶段四连续优化{label}闭合材料。
工作区 E:\\eitfm_c2_stages2-4_2026-11-03。先完成已发{previous}批，再读 c2/stage4_sessions/work/COORDINATION/continuous_20261116/GIT_ARCHIVE_{label}.md。
唯一清单为同目录GIT_ARCHIVE_{label}.tsv加自身：{count}路径、{total}字节；TSV {len(raw)}字节，SHA256 {digest}。
先核当前HEAD、index、实时远端和逐路径大小/SHA；仅精确暂存本清单，核index及commit每个blob后普通提交推送main。旧1690路径批和前批不要重复；活动候选、模型数据、动态库等不加入。
回传commit、父提交、路径/字节数、逐blob核验、遗漏/额外、实时origin/main和index。漂移或无关暂存/分叉先停止说明，不扩大范围。
''',encoding='utf-8')
    print(dict(paths=count,total_bytes=total,manifest_bytes=len(raw),manifest_sha256=digest))


if __name__=='__main__':main(sys.argv[1])
