"""Freeze the rejected math SDPA result, including incomplete-domain evidence."""
import freeze_closed_round as archive

version = 'R21_MATH_SDPA_REFERENCE'
support = ['build_r21.py', 'review_r21.py', 'freeze_r21.py',
           version+'/EXTERNAL_REFERENCE.json', version+'/received/EXTERNAL_REFERENCE.json',
           version+'/POST_COLLECTION_QUEUE.json']
support.extend(p.relative_to(archive.HERE).as_posix() for p in
    (archive.HERE/version/'received/job_evidence/domains').glob('node*/strict_candidate/cpu_samples.jsonl'))
archive.ROUNDS['R21'] = (version, 'R20', tuple(support))
archive.main('R21')
