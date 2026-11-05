"""Transcribe published local history; never present this as raw cluster data."""
import csv
import json
from pathlib import Path
import statistics

work = Path(__file__).resolve().parent
belts = ['16_adjacent/pre', '16_adjacent/dec', '32_skip4/pre', '32_skip4/dec']
records = [
    ('DDR_B64_PREFERRED', 64, [[243, 233, 237], [76, 49, 49], [31.0, 31.1, 32.7], [20.5, 20.4, 21.3]],
     'opt_s4_A1_node16_sync.log', 'round 2 has a documented missing 32-belt decoder domain; others unverified'),
    ('DDR_B32_MEMBIND', 32, [[150, 151, 151], [43, 46, 46], [21.9, 20.9, 20.9], [17.0, 16.5, 16.8]],
     'opt_s4_A1_node16_b32.log', 'document says no failure; raw files and statuses unavailable'),
    ('HBM_B32_MEMBIND', 32, [[290, 318], [75, 72], [21.9, 21.4], [18.0, 18.3]],
     'opt_s4_A1_node16_b32_hbm.log', 'two rounds only, stragglers; raw files and statuses unavailable'),
    ('DDR_B64_CKPT', 64, [[121, 118], [56, 42], [16.6, 16.8], [14.3, 14.0]],
     'opt_s4_A1_node16_b64ckpt.log', 'S01 context only; two rounds, raw files unavailable'),
]
rows, spreads = [], []
for config, batch, workloads, log, caveat in records:
    for workload, values in zip(belts, workloads):
        for round_id, value in enumerate(values, 1):
            rows.append(dict(status='HISTORICAL_DOCUMENT_ONLY', config=config, workload=workload,
                round=round_id, batch_per_process=batch, amp='fp32', expected_domains=16,
                verified_result_count='', total_step_s='', node_sum_frames_per_s=value,
                min_domain='', median_domain='', conservative_rate='', ddr_peak='', hbm_peak='',
                verified_exit_status='', source='c2/C2_OPTIMIZATION_REPORT.md',
                remote_log='/home/share/songzhenlong/eitfm/logs/' + log, caveat=caveat))
        spreads.append(dict(config=config, workload=workload, rounded_document_values=values,
            spread_from_rounded_values=(max(values) - min(values)) / statistics.mean(values),
            acceptance='NOT_ACCEPTED_RAW_EVIDENCE_MISSING',
            note='Rounded transcription only. Do not replace the original raw-value spread with this value.'))
with (work / 'evidence/historical_measurements.csv').open('w', encoding='utf-8', newline='') as stream:
    writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
    writer.writeheader()
    writer.writerows(rows)
(work / 'evidence/historical_spreads.json').write_text(json.dumps(spreads, indent=2) + '\n', encoding='utf-8')
print(len(rows), 'historical rows; no current cluster measurements')
