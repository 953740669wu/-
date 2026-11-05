"""CPU36 publication order for the strict and independent five-step entries."""
import cpu36_guard


def checkpoint_names(kind, steps):
    if kind not in ('strict', 'memory') or not 0 <= steps <= 5:
        raise ValueError('invalid fixed sequence contract')
    names = ['before_framework', 'after_framework', 'after_backend']
    if kind == 'memory':
        names += ['initialized']
    for step in range(1, steps + 1):
        names += ([f'before_reference_{step}', f'after_reference_{step}',
                   f'before_candidate_{step}', f'after_candidate_{step}'] if kind == 'strict'
                  else [f'before_training_{step}', f'after_training_{step}'])
    return names + ['publish']


def finish(state, torch, kind, steps):
    cpu36_guard.checkpoint(state, 'publish', torch)
    validate(state, kind, steps)


def validate(state, kind, steps):
    if state['errors'] or [x['name'] for x in state['checkpoints']] != checkpoint_names(kind, steps):
        raise ValueError('missing/out-of-order sequence CPU36 evidence')
    for record in state['checkpoints']:
        if record['pid'] != state['pid']:
            raise ValueError('CPU checkpoint PID changed')
        cpu36_guard.validate_checkpoint(record, state['receipt'])
