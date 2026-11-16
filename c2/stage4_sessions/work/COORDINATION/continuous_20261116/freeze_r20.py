"""Freeze the completed mixed-profile comparison and its exact validation gate."""
import freeze_closed_round as archive

archive.ROUNDS['R20'] = ('R20_MIXED_TAIL_WINDOW', 'R19', (
    'build_r20.py', 'review_r20.py', 'freeze_r20.py',
    'R20_MIXED_TAIL_WINDOW/PROFILE_GATE.json',
    'R20_MIXED_TAIL_WINDOW/received/PROFILE_GATE.json',
    'R20_MIXED_TAIL_WINDOW/received/STRICT16_REVIEW.json',
    'R20_MIXED_TAIL_WINDOW/received/ONLINE_A.json',
    'R20_MIXED_TAIL_WINDOW/POST_COLLECTION_QUEUE.json',
    'R20_MIXED_TAIL_WINDOW/PRIOR_AFFINITY_AUDIT.json'))
archive.main('R20')
