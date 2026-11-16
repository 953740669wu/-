"""Include the later empty-queue receipt without altering issued archive code."""
import freeze_closed_round as archive

version, previous, support = archive.ROUNDS['R19']
archive.ROUNDS['R19'] = (version, previous, support + (
    'R19_FTZ_REFERENCE/POST_COLLECTION_QUEUE.json', 'freeze_r19.py'))
archive.main('R19')
