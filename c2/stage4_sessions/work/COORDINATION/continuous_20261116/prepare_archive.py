"""Create an exact list for explicitly named closed experiment directories."""
import csv
from hashlib import sha256
import json
from pathlib import Path
import sys

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[4]


def main(label, *versions):
    chosen=set()
    for version in versions:
        r=HERE/version
        assert (r/'REVIEW.json').is_file()
        assert (r/'DECISION.json').is_file() or (r/'ADOPTION.json').is_file()
        for name in ('RUN_BINDING.json','SOURCE_SHA256.json','MINIMAL.diff','REVIEW.json','DECISION.json','ADOPTION.json','STRICT16_REVIEW.json','COORDINATION_SNAPSHOT.md','PLAN.md'):
            if (r/name).is_file():chosen.add(r/name)
        rec=r/'received'
        for name in ('COLLECTION_INDEX.json','djob_final.json','submission.command.json','submission.stdout',
                     'submission.result.json','scheduler_allocation.json','site_static.json','LOGIN_METADATA_CHECK.json',
                     'FIXED_INPUTS_BEFORE.json','FIXED_INPUTS_AFTER.json','QUEUE_AFTER.json','queue_before_submit.json','host_cn22036_before_submit.json',
                     'host_cn22035_before_submit.json','STOP_NATIVE_BEFORE.json','STOP_REQUEST.txt',
                     'ENGINEERING_DESCRIPTOR.json','PRIOR_PAIRING.json','DEPENDENCY_RECEIPT.json'):
            if (rec/name).is_file():chosen.add(rec/name)
        for name in ('launch.py','prepare.py','submit_once.py','run_worker.sh','native_trace.c','kml_control_guard.c','payload/worker.py','payload/checkpoint_layers.py',
                     'payload/ffn_relu_reuse.py','payload/engineering_training.py','payload/window_control.py',
                     'payload/checkpoint_tail.py',
                     'FROZEN_REFERENCE/PAIRING.json','FROZEN_REFERENCE/steps.jsonl',
                     'FROZEN_REFERENCE_NODE4/PROVENANCE.json','FROZEN_REFERENCE_NODE4/result.json',
                     'FROZEN_REFERENCE_NODE4/PAIRING.json','FROZEN_REFERENCE_NODE4/steps.jsonl'):
            if (rec/name).is_file():chosen.add(rec/name)
        if json.loads((r/'RUN_BINDING.json').read_bytes())['mode'] == 'fp32_attention_precise':
            chosen.update((rec/'payload/attn_dispatch.py',rec/'kml_attn.c'))
        ev=rec/'job_evidence'
        for pat in ('SUMMARY.json','cleanup.json','domain_map.json','native_memory_limit.json','hbm_capacity_before.json',
                    'allocator_identity_*.json','pool_return_*.json','strict_snapshot_cleanup.json','node*.allocation.json',
                    'scheduler_handoff.json','ACTIVE_CONTRACTS.json','PAIRING_FROZEN_BEFORE_UPDATE.json','update_budget_cleanup.json',
                    'ATTN_BUILD.json','cc_version.*','attn_compile.*','attn_link.*','NATIVE_TRACE_BUILD.json','native_trace_compile.*',
                    'CONTROL_GUARD_BUILD.json','control_guard_compile.*'):
            chosen.update(ev.glob(pat))
        if (ev/'domains').is_dir():
            chosen.add(ev/'DOMAIN_CHILDREN.json')
            for pat in ('DOMAIN_SUMMARY.json','cleanup.json','pool_return_*.json','node*.allocation.json',
                        'PAIRING_FROZEN_BEFORE_UPDATE.json','strict_snapshot_cleanup.json'):
                chosen.update((ev/'domains').glob('node*/'+pat))
        for phase in ev.rglob('*'):
            if not phase.is_dir() or not (phase.name.startswith(('strict_','perf_')) or phase.name in ('A','B')):continue
            for pat in ('phase_receipt.json','exit_codes.json','node*.hbm_residency.json','node*.command.json',
                        'node*.env.json','node*.log','WINDOW.json'):
                chosen.update(phase.glob(pat))
            chosen.update((phase/'barriers').glob('*.release'))
            if version in ('R8_TAIL_SKIP','R13_FOUR_DOMAIN_TAIL','R16_FULL16_STRICT'):
                chosen.add(phase/'cpu_samples.jsonl')
            for node in phase.glob('node[0-9]*'):
                if not node.is_dir():continue
                for name in ('result.json','steps.jsonl','PAIRING.json','EXPOSURE_LEDGER.json','native_first_step.jsonl',
                             'before_torch_affinity.json','strict_end.numa_maps','observe_end.numa_maps','publish.maps'):
                    if (node/name).is_file():chosen.add(node/name)
    if label == 'R16':
        chosen.update(HERE/n for n in ('build_r16.py','review_r16.py','prepare_archive.py'))
        chosen.add(HERE.parent/'GIT_AGGRESSIVE3H_1690_POST_PUSH_REVIEW_20261116.json')
    md=HERE/f'GIT_ARCHIVE_{label}.md'
    assert not md.exists(), 'issued archive is immutable'
    md.write_text(f'''# 连续优化闭合归档 {label}

仅归档已闭合目录 {', '.join(versions)} 的本TSV精确路径，加TSV自身。结论见各目录DECISION.json或ADOPTION.json。

本批基点为已独立核验的f365a772e06b5d596752f2be3f94f08b142d2694。旧1690路径批已提交推送，不重复。读取当前HEAD、index及实时远端后，按精确清单核路径/大小/SHA；若HEAD前进，先核相同blob并回传差集，任何漂移或无关暂存停止并回报。

包含源码差异、实际绑定、原生终态、完整数值与计时时序、HBM驻留和清理；完整传输包与未选取原件有COLLECTION_INDEX索引。未修改依赖按既有C1来源和源码SHA追溯。排除动态库、压缩包、原始数据、模型、环境文件与凭据、重复线程采样。活动作业、活动状态和未闭合候选继续暂缓，不整目录暂存。

仅唯一Git窗口按TSV普通提交推送main。核index及commit的每个blob，回传commit、父提交、对象/字节总数、遗漏/额外、实时origin/main和index状态。当前窗口独立复核后更新交接。
''',encoding='utf-8')
    chosen.add(md)
    rows=[]
    for f in sorted(chosen):
        raw=f.read_bytes();rows.append((f.relative_to(ROOT).as_posix(),len(raw),sha256(raw).hexdigest()))
    tsv=HERE/f'GIT_ARCHIVE_{label}.tsv'
    with tsv.open('x',encoding='utf-8',newline='') as out:
        w=csv.writer(out,delimiter='\t',lineterminator='\n');w.writerow(('path','bytes','sha256'));w.writerows(rows)
    raw=tsv.read_bytes()
    info=f'{len(rows)}行加TSV自身共{len(rows)+1}路径，{sum(r[1] for r in rows)+len(raw)}字节；TSV {len(raw)}字节，SHA256 {sha256(raw).hexdigest()}'
    prompt=f'''请在唯一Git窗口归档阶段四长任务{label}已闭合材料。工作区 E:\\eitfm_c2_stages2-4_2026-11-03。
旧1690路径批已完成，不重复；请读 c2/stage4_sessions/work/COORDINATION/continuous_20261116/GIT_ARCHIVE_{label}.md。
唯一批准清单为同目录GIT_ARCHIVE_{label}.tsv，{info}。
按说明核当前HEAD、前批commit blob、实时远端及本批路径/大小/SHA。只精确暂存本清单加TSV自身，普通提交推送main，保留其他文件与暂存。
回传commit/父提交、精确路径和字节总数、逐blob结果、遗漏/额外、实时origin/main、index状态。其他活动候选不入本批。
'''
    (HERE/f'GIT_PROMPT_{label}.txt').write_text(prompt,encoding='utf-8')
    print(info)


if __name__=='__main__':main(*sys.argv[1:])
