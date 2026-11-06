"""Shared absolute consumer deadline, identity-checked owned descendants only."""
from pathlib import Path
import time
from owned_processes import run_phase,cleanup
from prepare import save

def run_step(root,owner,label,command,deadline,limit=None):
    stop=min(deadline,time.monotonic()+limit) if limit is not None else deadline
    record=None
    try:
        record=run_phase(root,owner,label,command,stop)
    finally:
        clean=cleanup(owner,min(time.monotonic()+15,deadline+15))
        save(Path(root)/'job_evidence'/(label+'_cleanup.json'),clean)
        if not clean['all_reaped']:raise RuntimeError('owned descendants remain after '+label)
    return record
