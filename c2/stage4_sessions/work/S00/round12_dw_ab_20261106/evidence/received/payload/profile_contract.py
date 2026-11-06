"""Bind the same fixed1600 engineering frames and first five seed0 updates."""
import hashlib
import json

PROTOCOL='ENGINEERING_REAL_CORPUS_PROFILE5_V1'


def identity(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def check_data(description,reference):
    if description['corpus']!=reference['corpus'] or description['train']!=reference['units']:
        raise ValueError('profile data differs from job2043445 fixed unit/file identities')
    if len(description['train'])!=16 or sum(x['n_pairs'] for x in description['train'])!=1600:
        raise ValueError('same16 units/1600 frames required; no scope expansion/replacement')


def check_step_identity(step,indices,frame_sha,mask_sha,reference):
    if not 1<=step<=5:raise ValueError('profile update cap5')
    expected=reference['steps'][step-1]
    if expected['step']!=step or expected['frame_indices']!=indices or expected['frame_ids_sha256']!=frame_sha or expected['mask_sha256']!=mask_sha:
        raise ValueError('baseline first5 frame/order/mask drift; stop without resampling')
