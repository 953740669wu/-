"""LOCAL_FIXTURE metadata helpers only. No model, observer or process executor."""
import argparse
import json
import os
from pathlib import Path

SPEC_SHA = 'd1da482f2971281996ac70e9133606933277bb31bfead1a48ed64fbbddaf67c2'
RETAIN_MAX, RAW_MAX, TEXT_MAX = 2**30, 2**29, 2**26
NS = 10**9


class ContractError(ValueError):
    pass


def require(value, message):
    if not value: raise ContractError(message)


def partition(global_ids, shards):
    require(len(global_ids) == 64 and len(set(global_ids)) == 64, 'original64 unique IDs required')
    require(shards == [global_ids[:32], global_ids[32:]], 'ordered first32/last32 partition required')


def rows(ids, wanted, order, tokens, shape, provenance_sha):
    """Map declared logical samples to physical flattened rows, never tensor values."""
    require(len(ids) in (32,64) and len(set(ids)) == len(ids), 'unique logical sample IDs required')
    require(wanted in (ids,ids[:len(ids)//2],ids[len(ids)//2:]), 'logical subset order/coverage differs')
    require(isinstance(provenance_sha,str) and len(provenance_sha) == 64 and
            all(x in '0123456789abcdef' for x in provenance_sha), 'explicit layout provenance required')
    require(type(tokens) is int and 1 <= tokens <= 208 and len(shape) in (2,3) and
            all(type(x) is int and x > 0 for x in shape), 'bounded logical shape required')
    b, f = len(ids), shape[-1]
    if order == 'sample_token': expected = [b,tokens,f]
    elif order == 'token_sample': expected = [tokens,b,f]
    elif order == 'sample' and tokens == 1: expected = [b,f]
    else: raise ContractError('unproven logical sample axis')
    require(shape == expected or shape == [b*tokens,f], 'shape/provenance mismatch')
    return [(ids.index(sample)*tokens+t if order != 'token_sample' else t*b+ids.index(sample))
            for sample in wanted for t in range(tokens)]


def scaling(mask_counts, coarse_counts, factors):
    require(len(mask_counts) == 2 and all(type(x) is int and 0 <= x <= 32*208 for x in mask_counts), 'actual local mask counts required')
    require(0 < sum(mask_counts) <= 64*208, 'zero/invalid global mask denominator')
    require(coarse_counts == [8192,8192] and factors == [1,1,1], 'sequential global denominators and 1/1/1 only')
    return [sum(mask_counts),16384]


class Paths:
    def __init__(self, start_ns):
        self.start = start_ns
        self.active = None; self.path_start = None
        self.completed = []; self.counts = {}; self.stopped = False
        self.last = start_ns

    def _time(self, now):
        require(type(now) is int and self.last <= now < self.start+240*NS, 'shared execution deadline/clock failed')
        if self.active: require(now < self.path_start+90*NS, 'path90 cannot reset common240')
        self.last = now

    def begin(self, path, now):
        require(not self.stopped and self.active is None, 'no new path after stop or active path')
        expected = ['A_FULL_B64','B_SEQUENTIAL_32_PLUS_32']
        require(len(self.completed) < 2 and path == expected[len(self.completed)], 'one A then one B only')
        self._time(now); self.active = path; self.path_start = now
        self.counts[path] = dict(forward=0,backward=0)

    def record(self, event, now):
        require(not self.stopped and self.active and event in ('forward','backward'), 'forbidden computation/update or stopped')
        self._time(now)
        limit = 1 if self.active == 'A_FULL_B64' else 2
        count = self.counts[self.active]
        require(count[event] < limit, 'forward/backward count exceeded')
        if event == 'forward': require(count['forward'] == count['backward'], 'finish prior backward first')
        else: require(count['forward'] == count['backward']+1, 'one backward per actual forward')
        count[event] += 1

    def finish(self, now):
        require(not self.stopped and self.active, 'no completed path after stop')
        self._time(now); n = 1 if self.active == 'A_FULL_B64' else 2
        require(self.counts[self.active] == dict(forward=n,backward=n), 'incomplete path')
        self.completed.append(self.active); self.active = None

    def numeric_failure(self):
        self.stopped = True


class Budget:
    def __init__(self):
        self.allocations = {}; self.totals = dict(retained=0,raw=0,text=0)

    def reserve(self, kind, name, nbytes):
        require(kind in self.totals and (kind,name) not in self.allocations, 'duplicate/unknown budget entry')
        require(type(nbytes) is int and nbytes >= 0, 'nonnegative byte count required')
        cap = dict(retained=RETAIN_MAX,raw=RAW_MAX,text=TEXT_MAX)[kind]
        require(self.totals[kind]+nbytes <= cap, 'retention/raw/text byte cap exceeded')
        self.allocations[kind,name] = nbytes; self.totals[kind] += nbytes


def retention_proof():
    p = 37995777*4
    values = (64*208*512 + 64*208 + 64*256 + 64*208 + 64*64*64 + 3)*4
    categories = dict(initial_snapshot=p,reference_gradients=p,sequential_gradients=p,
                      reference_values=values,sequential_values=values,
                      compare_workspace=256*2**20,hash_workspace=32*2**20,
                      retained_inputs=64*2**20,text_and_indices=TEXT_MAX,buffers=4*2**20)
    return dict(scope='CONDITIONAL_STATIC_BYTE_ENVELOPE_NOT_MEASURED',categories=categories,
                parameter_fp32_bytes=p,retained_bytes_bound=sum(categories.values()),
                extra_limit=RETAIN_MAX,raw_reference_value_bytes=p+values,raw_limit=RAW_MAX,
                image_shape_bound=[64,1,64,64],largest_compare_tensor_elements=64*208*512,
                double_compare_four_copies_bytes=4*8*64*208*512,
                conditions=['one initial snapshot, one reference set, one sequential transient set',
                            'compare serially; no all-layer X/G snapshots; bounded streaming hash',
                            'reject image/buffer/temporary growth or unaccounted copies',
                            'base model/autograd/library workspace and actual24GiB peak unmeasured'])


def parse_stat(text):
    try:
        left, right = text.index('('), text.rindex(')')
        fields = text[right+1:].split()
        value = dict(pid=int(text[:left]),ppid=int(fields[1]),pgid=int(fields[2]),
                     session=int(fields[3]),start_ticks=int(fields[19]))
        require(all(x > 0 for x in value.values()), 'invalid process identity')
        return value
    except (ValueError,IndexError) as exc:
        raise ContractError('malformed proc stat creation identity') from exc


def compute_identity(actual, expected, direct_pid, supervisor_pid):
    keys = ('pid','ppid','pgid','session','start_ticks','parent_start_ticks','boot_id','job','run','exe_sha256')
    require(all(k in expected and actual.get(k) == expected[k] for k in keys), 'compute start/job/run identity differs')
    require(actual['pid'] == direct_pid and actual['ppid'] == supervisor_pid and
            actual['pgid'] == actual['session'] == direct_pid, 'actual compute/launcher/session mismatch')
    require(all(type(actual[k]) is int and actual[k] > 0 for k in keys[:6]), 'positive native process identity required')


def exit_evidence(owned, events, start_ns, descendants_complete):
    require(descendants_complete is True and owned, 'complete identity-bound owned descendants required')
    found = {pid:set() for pid in owned}
    term_times = []; last = start_ns
    for e in events:
        require(isinstance(e,dict) and {'pid','start_ticks','at_ns','event'} <= set(e), 'incomplete lifecycle event')
        require(e.get('pid') in owned and e.get('start_ticks') == owned[e['pid']], 'unowned or reused PID')
        when = e.get('at_ns')
        require(type(when) is int and last <= when <= start_ns+270*NS, 'common cleanup deadline/order missing')
        last = when
        require(e['event'] in ('TERM_REQUEST','KILL_REQUEST','ACTUAL_EXIT','REAP'), 'Popen-only/late-absence is not actual exit')
        if e['event'] == 'TERM_REQUEST': term_times.append(when)
        if e['event'] == 'REAP': require('ACTUAL_EXIT' in found[e['pid']], 'reap lacks actual compute exit evidence')
        found[e['pid']].add(e['event'])
    require(all({'ACTUAL_EXIT','REAP'} <= x for x in found.values()), 'actual exit/reap evidence incomplete')
    require(not term_times or last-min(term_times) <= 30*NS, 'cleanup30 exceeded')


def require_observer_coverage(roles):
    needed = {'c2_node_hook_grad_inputs','c2_native_linear_vjp_slot_binding','c2_attention_logical_layout'}
    require(needed <= set(roles), 'B01_UNBOUND_INSTALLED_NATIVE_VJP: pinned per-operation VJP/layout sources missing')


def validate_report(value):
    require(value.get('scope') == 'LOCAL_FIXTURE' and value.get('spec_sha256') == SPEC_SHA,
            'fixture scope or frozen spec identity differs')
    require(value.get('complete') is True and value.get('status') == 'LOCAL_FIXTURE_VALID', 'missing/partial fixture report')
    require(all(value.get(k) is False for k in ('actual_autograd','actual_KML','actual_Linux_exit')),
            'fixture cannot claim actual runtime verification')


def _unique(pairs):
    value = {}
    for k,v in pairs:
        require(k not in value, 'duplicate JSON key'); value[k] = v
    return value


def read_report(path):
    path = Path(path)
    require(path.suffix == '.json' and 0 < path.stat().st_size <= TEXT_MAX, 'empty/temporary/oversize report')
    try: value = json.loads(path.read_text(encoding='utf-8-sig'),object_pairs_hook=_unique)
    except (ValueError,UnicodeError) as exc: raise ContractError('corrupt/partial JSON') from exc
    require(isinstance(value,dict), 'JSON object required')
    validate_report(value)
    return value


def write_report(path, value):
    path = Path(path); temporary = path.with_suffix('.tmp')
    validate_report(value)
    require(not path.exists() and not temporary.exists(), 'refuse old report/temp; no retry')
    raw = (json.dumps(value,indent=2)+'\n').encode()
    require(len(raw) <= TEXT_MAX, 'text cap exceeded')
    with temporary.open('xb') as stream:
        stream.write(raw); stream.flush(); os.fsync(stream.fileno())
    temporary.replace(path)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--fixture',type=Path,required=True)
    parser.add_argument('--report',type=Path,required=True)
    args = parser.parse_args()
    try:
        value = read_report(args.fixture); write_report(args.report,value)
        print(json.dumps(dict(status='LOCAL_FIXTURE_VALID',actual_runtime=False)))
    except (OSError,ValueError) as exc:
        print(json.dumps(dict(status='LOCAL_FIXTURE_REJECTED',error=str(exc)))); raise SystemExit(2)
