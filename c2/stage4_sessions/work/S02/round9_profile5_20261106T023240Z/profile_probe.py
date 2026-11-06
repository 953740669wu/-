"""Five updates only: CPU events on3..5, explicit wall phases, bounded output."""
from contextlib import contextmanager,nullcontext
import hashlib
import json
import os
from pathlib import Path
import sys
import time

from engineering_training import losses

MAX_EVENTS=50000
MAX_KML_MARKERS=256
TRACE_BYTES=8*1024*1024
SUMMARY_BYTES=1024*1024
PHASES=('zero_grad_before','forward_loss','zero_grad_after','backward','optimizer')


class UnsupportedProfiler(RuntimeError):pass
class ProfileLimit(RuntimeError):pass


def check_event_count(count):
    if count>MAX_EVENTS:raise ProfileLimit('CPU event count exceeds50000; stop without retry')


def write_bounded(path,value,limit):
    raw=(json.dumps(value,separators=(',',':'),allow_nan=False)+'\n').encode()
    if len(raw)>limit:raise ProfileLimit('profile artifact exceeds byte limit: '+str(path))
    with Path(path).open('xb') as stream:stream.write(raw)
    return dict(path=str(Path(path).resolve()),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())


@contextmanager
def mark_kml(torch,module):
    original=module.gemm;state=dict(calls=0)
    def marked(*args,**kwargs):
        state['calls']+=1
        if state['calls']>MAX_KML_MARKERS:raise ProfileLimit('KML marker cap256 per sampled update')
        # This includes Python/counter/allocation/ctypes work, NOT exact native kernel time.
        with torch.profiler.record_function('S02/KML_python_gemm_envelope'):
            return original(*args,**kwargs)
    module.gemm=marked
    try:yield state
    finally:module.gemm=original


class Probe:
    def __init__(self,torch,output,kml_module=None):
        p=getattr(torch,'profiler',None)
        if p is None or not all(hasattr(p,k) for k in ('profile','ProfilerActivity','record_function','supported_activities')):
            raise UnsupportedProfiler('required existing torch CPU profiler API unavailable; no fallback/install')
        if p.ProfilerActivity.CPU not in p.supported_activities():
            raise UnsupportedProfiler('torch CPU profiler unsupported; no backend fallback')
        self.torch=torch;self.output=Path(output);self.kml=kml_module;self.records=[]

    @contextmanager
    def phase(self,record,name):
        tick=time.perf_counter()
        context=self.torch.profiler.record_function('S02/'+name) if record['sampled'] else nullcontext()
        with context:
            try:yield
            finally:record['phase_seconds'][name]=time.perf_counter()-tick

    def train_step(self,model,opt,values,mask,record):
        # Original operation order and expressions; only timing/record_function scopes added.
        torch=self.torch;v,image,angles,belt=values
        v.requires_grad_();image.requires_grad_()
        with self.phase(record,'zero_grad_before'):opt.zero_grad(set_to_none=True)
        with self.phase(record,'forward_loss'):
            total,voltage,coarse=losses(torch,model,v,image,angles,belt,mask)
        with self.phase(record,'zero_grad_after'):opt.zero_grad()
        with self.phase(record,'backward'):total.backward()
        with self.phase(record,'optimizer'):opt.step()
        return dict(total=total.detach(),voltage=voltage.detach(),coarse=coarse.detach())

    def run(self,step,model,opt,values,mask):
        if step!=len(self.records)+1 or not 1<=step<=5:raise ProfileLimit('exactly sequential updates1..5 required')
        record=dict(step=step,sampled=step>=3,phase_seconds={},status='STARTED',
                    profiler_setup_start_seconds=0.,profiler_stop_seconds=0.,profiler_postprocess_export_seconds=0.,
                    in_step_profiler_overhead_seconds=None,
                    overhead_note='in-step event/marker overhead is included and inseparable without a matched unprofiled run; no net throughput claim')
        self.records.append(record);torch=self.torch;prof=None
        if record['sampled']:
            tick=time.perf_counter()
            try:
                prof=torch.profiler.profile(activities=[torch.profiler.ProfilerActivity.CPU],
                    record_shapes=False,profile_memory=False,with_stack=False,with_flops=False)
                prof.__enter__()
            except Exception as exc:
                record['status']='UNSUPPORTED_PROFILER';raise UnsupportedProfiler(str(exc)) from exc
            finally:record['profiler_setup_start_seconds']=time.perf_counter()-tick
        tick=time.perf_counter()
        try:
            with mark_kml(torch,self.kml) if prof is not None and self.kml is not None else nullcontext() as marker:
                result=self.train_step(model,opt,values,mask,record)
                record['kml_markers']=marker['calls'] if marker else 0
        except BaseException:
            record['status']='FAILED_OR_INTERRUPTED';raise
        finally:
            record['instrumented_step_seconds']=time.perf_counter()-tick
            if prof is not None:
                tick=time.perf_counter();prof.__exit__(*sys.exc_info())
                record['profiler_stop_seconds']=time.perf_counter()-tick
        if prof is not None:
            tick=time.perf_counter();events=prof.events();record['events']=len(events);check_event_count(len(events))
            names=[e.name for e in events]
            if not all('S02/'+name in names for name in PHASES):
                raise UnsupportedProfiler('CPU capture missing required phase events; no fallback')
            if self.kml is not None and names.count('S02/KML_python_gemm_envelope')!=record['kml_markers']:
                raise UnsupportedProfiler('CPU capture missing KML envelope events')
            trace=[dict(name=e.name,ph='X',ts=e.time_range.start,dur=e.time_range.elapsed_us(),pid=os.getpid(),tid=e.thread,
                        args=dict(event_id=e.id,parent_id=e.cpu_parent.id if e.cpu_parent else None)) for e in events]
            record['trace']=write_bounded(self.output/f'trace_step_{step}.json',dict(traceEvents=trace,
                displayTimeUnit='ms',scope='CPU FunctionEvent spans; nested totals overlap; no exact KML native-kernel attribution'),TRACE_BYTES)
            averages=sorted(prof.key_averages(),key=lambda e:e.self_cpu_time_total,reverse=True)
            summary=dict(step=step,events=len(events),distinct_keys=len(averages),top_limit=80,
                units='microseconds',aggregation='sorted self CPU time; total CPU is nested, never add self+total or nested totals; CPU time across threads is not wall time',
                kml_scope='S02/KML_python_gemm_envelope includes Python/counter/allocation/ctypes/native; exact native kernel share UNKNOWN',
                top_self_cpu=[dict(key=e.key,calls=e.count,self_cpu_us=e.self_cpu_time_total,total_cpu_us=e.cpu_time_total) for e in averages[:80]])
            record['summary']=write_bounded(self.output/f'events_step_{step}.json',summary,SUMMARY_BYTES)
            record['profiler_postprocess_export_seconds']=time.perf_counter()-tick
        record['profiler_outside_step_seconds']=sum(record[k] for k in ('profiler_setup_start_seconds','profiler_stop_seconds','profiler_postprocess_export_seconds'))
        record['status']='CAPTURED' if record['sampled'] else 'WARMUP_NO_CPU_CAPTURE'
        return result,record
