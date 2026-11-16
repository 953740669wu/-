"""Unify the frozen closed-round lists plus an explicit session-support whitelist."""
import csv
import hashlib
import json
from pathlib import Path
import subprocess

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[4]
LABELS=('R1','R2','R3','R4','R5','R8','R8_F1','R8_F2','R8_F3','R9','R10','R11','R12','R13','R14','R15')


def main():
    ledger=json.loads((HERE/'BUDGET_LEDGER.json').read_bytes())
    assert ledger['status']=='CLOSED' and all(r['state'] in ('SUCCEEDED','FAILED','CANCELLED') and r['cleanup_passed'] for r in ledger['submissions'])
    head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    index=subprocess.check_output(['git','diff','--cached','--name-only'],cwd=ROOT,text=True).splitlines()
    assert not index, 'shared index is not empty; do not disturb it'
    tracked={}
    for row in subprocess.check_output(['git','ls-tree','-r','-z','HEAD'],cwd=ROOT).split(b'\0'):
        if row:
            meta,path=row.split(b'\t',1);tracked[path.decode()]=meta.split()[2].decode()
    chosen=set();batches=[]
    for label in LABELS:
        tsv=HERE/f'GIT_ARCHIVE_{label}.tsv'
        rows=list(csv.DictReader(tsv.open(encoding='utf-8'),delimiter='\t'))
        for r in rows:
            p=ROOT/r['path'];raw=p.read_bytes()
            assert len(raw)==int(r['bytes']) and hashlib.sha256(raw).hexdigest()==r['sha256'],r['path']
            assert p not in chosen, 'overlapping round lists'
            chosen.add(p)
        chosen.add(tsv)
        batches.append(dict(label=label,paths=len(rows)+1,manifest_bytes=tsv.stat().st_size,manifest_sha256=hashlib.sha256(tsv.read_bytes()).hexdigest()))
        chosen.add(HERE/f'GIT_PROMPT_{label}.txt')
    support=('ACTIVE_VERSION.json','BUDGET_LEDGER.json','PREPARED_NOT_SUBMITTED.json','SESSION_STATUS.md',
             'SPEED_COMPARISON.md','RUN_CLOSEOUT.md','MONITOR_CLOCK_NOTE.md','R1_PLAN.md','R5_PLAN.md','R8_PLAN.md',
             'build_r1.py','build_r1_fix1.py','build_r2_stack.py','build_r3_threeway.py','build_hbm_policy.py','build_full16.py',
             'build_tail_skip.py','build_tail_retry.py','build_tail_diagnostic.py','build_tail_wait_policy.py','build_ffn_tail.py',
             'build_sdpa_serial.py','build_native_trace.py','build_control_guard.py','build_tail_four_domains.py',
             'build_domain1_tail.py','build_independent_domains.py','checkpoint_layers.py','checkpoint_tail.py',
             'native_trace.c','kml_control_guard.c','review_job.py','review_threeway.py','review_full16.py',
             'review_independent_domains.py','prepare_archive.py','prepare_session_archive.py','test_checkpoint_scope.py')
    chosen.update(HERE/n for n in support)
    chosen.update(HERE.parent/n for n in ('COORDINATOR3_HANDOFF_20261111.md','SESSION_STATUS.md','ROUND_DELTA.md','STATUS.md'))
    skipped=[];new=set()
    for p in chosen:
        raw=p.read_bytes();rel=p.relative_to(ROOT).as_posix()
        oid=hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()
        if tracked.get(rel)==oid:skipped.append(rel)
        else:new.add(p)
    audit=HERE/'ARCHIVE_AUDIT.json'
    audit.write_text(json.dumps(dict(base_head=head,shared_index_empty=True,prior_frozen_batches=batches,
        prior_manifest_drift=[],duplicate_paths=[],already_identical_in_head=sorted(skipped),
        excluded_unsubmitted=['R2/','R6_FOREACH/','R7_ATTN_PRECISE/','build_r2.py','build_foreach.py','build_attention_precise.py','R7_PLAN.md'],
        remote_rechecked=False,reason='No Git-window receipt yet; live remote verification follows its commit/push return.'),ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    new.add(audit)
    md=HERE/'GIT_ARCHIVE_ALL_CLOSED.md'
    md.write_text('''# 三小时长任务统一闭合归档

本卡取代本轮尚未执行的各GIT_PROMPT_R*提交安排；不重复执行两套提示词。旧分轮清单保留追溯，已核各自路径/大小/SHA且互不重叠。最终唯一批准范围为GIT_ARCHIVE_ALL_CLOSED.tsv逐行路径，加TSV自身；一批普通提交推送main即可。只包含已闭合的成功、拒绝、失败、诊断、实际修改代码及必要协调材料。R2草案、R6/R7未提交代码、动态库、模型/数据和ZIP不在清单；暂缓说明单列。

先核ARCHIVE_AUDIT.json的基点、当前HEAD、共享index和实时远端。若HEAD已前进，不重复已提交且blob相同的路径；须先回传核验后的精确差集和数量，不能扩大清单。发现文件漂移、无关暂存或远端分叉应停止并说明。不得git add整个目录、改写历史、强推或夹带其他材料。

逐路径核大小/SHA，精确暂存并核index blob；提交后核commit blob、遗漏/额外、父提交、路径/字节总数，再普通推送main，实时核origin/main。回传全部核验结果给总协调窗口。总协调独立核提交对象与远端后更新任务表/交接；本卡就绪不等于已经提交或推送。
''',encoding='utf-8');new.add(md)
    tsv=HERE/'GIT_ARCHIVE_ALL_CLOSED.tsv';assert not tsv.exists(),'issued master manifest is immutable'
    rows=[]
    for p in sorted(new):
        raw=p.read_bytes();rows.append((p.relative_to(ROOT).as_posix(),len(raw),hashlib.sha256(raw).hexdigest()))
    with tsv.open('x',encoding='utf-8',newline='') as f:
        w=csv.writer(f,delimiter='\t',lineterminator='\n');w.writerow(('path','bytes','sha256'));w.writerows(rows)
    raw=tsv.read_bytes();info=dict(paths=len(rows)+1,total_bytes=sum(r[1] for r in rows)+len(raw),manifest_bytes=len(raw),manifest_sha256=hashlib.sha256(raw).hexdigest(),base_head=head)
    assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()==head
    (HERE/'GIT_PROMPT_ALL_CLOSED.txt').write_text(f'''请在唯一Git窗口归档阶段四三小时长任务，工作区 E:\\eitfm_c2_stages2-4_2026-11-03。
本统一卡取代尚未执行的本轮R1至R15分轮提示，不要重复旧批。先读 c2/stage4_sessions/work/COORDINATION/aggressive_3h_20261111/GIT_ARCHIVE_ALL_CLOSED.md 和 ARCHIVE_AUDIT.json。
唯一清单为同目录 GIT_ARCHIVE_ALL_CLOSED.tsv 加TSV自身：共{info['paths']}路径、{info['total_bytes']}字节；TSV {info['manifest_bytes']}字节，SHA256 {info['manifest_sha256']}。基点HEAD {head}。
核当前HEAD、index、实时远端及所有路径/大小/SHA；只精确暂存清单，核index/commit每个blob，普通提交并推送main。未提交R2/R6/R7等继续暂缓，不整目录加入Git。
回传commit、父提交、精确路径/字节总数、逐blob核验、遗漏/额外、实时origin/main和index状态。若HEAD已前进或有漂移/无关暂存，先按说明核差集回报，不重复提交、不扩大范围。总协调收到后独立核验并更新交接。
''',encoding='utf-8')
    print(json.dumps(info))


if __name__=='__main__':main()
