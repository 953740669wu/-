"""Scalar metadata only, reversible hooks around the unchanged fp32 KML path."""
from contextlib import contextmanager
import hashlib
import json
import math
from pathlib import Path
import threading
import time

PROTOCOL='ENGINEERING_REAL_CORPUS_GEMM5_V1'
EXPECTED_CALLS=149
MAX_RECORDS=256
FILE_BYTES=1024*1024


class ObservationError(RuntimeError):pass
class ObservationLimit(ObservationError):pass
class UnsupportedObservation(ObservationError):pass


def tensor_metadata(value):
    return dict(shape=list(value.shape),stride=list(value.stride()),dtype=str(value.dtype),contiguous=value.is_contiguous())


def storage(value):return value.untyped_storage().data_ptr()


def write_bounded(path,value):
    raw=(json.dumps(value,separators=(',',':'),allow_nan=False)+'\n').encode()
    if len(raw)>FILE_BYTES:raise ObservationLimit('GEMM detail file exceeds1MiB; no truncation/retry')
    with Path(path).open('xb') as stream:stream.write(raw)
    return dict(path=str(Path(path).resolve()),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())


class Observer:
    def __init__(self,module,output):
        if module._lib is None or not callable(getattr(module,'_sgemm',None)):
            raise UnsupportedObservation('actual fp32 _sgemm hook unavailable; no backend fallback')
        if str(module.LINEAR_DTYPE)!='torch.float32':raise UnsupportedObservation('fp32 only')
        self.module=module;self.output=Path(output);self.local=threading.local();self.lock=threading.Lock()
        self.active=False;self.samples=[]

    def stack(self):
        if not hasattr(self.local,'calls'):self.local.calls=[]
        return self.local.calls

    @contextmanager
    def linear_context(self,name):
        before=getattr(self.local,'linear',None);self.local.linear=name
        try:yield
        finally:self.local.linear=before

    def outer(self,a,b,*args,**kwargs):
        before=time.perf_counter_ns();bound=dict(ta=False,tb=False,out=None,beta=0.,acc32=False)
        names=list(bound)
        if len(args)>len(names) or set(kwargs)-set(names) or set(names[:len(args)]).intersection(kwargs):
            raise ObservationError('ambiguous GEMM argument binding')
        bound.update(zip(names,args));bound.update(kwargs)
        ta,tb,out,beta,acc32=[bound[k] for k in names]
        if type(ta) is not bool or type(tb) is not bool or type(acc32) is not bool or acc32 or type(beta) not in (int,float) or not math.isfinite(beta) or str(a.dtype)!='torch.float32' or a.dtype!=b.dtype:
            raise UnsupportedObservation('only original fp32 GEMM flags supported')
        if len(a.shape)!=2 or len(b.shape)!=2 or not a.is_contiguous() or not b.is_contiguous():
            raise ObservationError('original contiguous2D operands required')
        m,k=(a.shape[1],a.shape[0]) if ta else a.shape;n=b.shape[0] if tb else b.shape[1]
        if k!=(b.shape[1] if tb else b.shape[0]):raise ObservationError('GEMM inner dimensions differ')
        stack=self.stack();linear=getattr(self.local,'linear',None)
        role='forward' if linear=='forward' and not ta and tb else 'dX' if linear=='backward' and not ta and not tb else 'dW' if linear=='backward' and ta and not tb else 'UNKNOWN'
        with self.lock:
            self.sequence+=1
            if self.sequence>MAX_RECORDS:raise ObservationLimit('more than256 GEMM records; stop without extra call')
            index=self.sequence
        record=dict(step=self.step,call_index=index,thread_id=threading.get_native_id(),parent_call_index=stack[-1]['record']['call_index'] if stack else None,
            role=role,linear_context=linear,a=tensor_metadata(a),b=tensor_metadata(b),ta=ta,tb=tb,beta=float(beta),m=int(m),n=int(n),k=int(k),native_calls=0)
        context=dict(record=record,a=a,b=b,out=out);stack.append(context)
        record['observer_before_ns']=time.perf_counter_ns()-before
        record['gemm_start_ns']=time.perf_counter_ns()
        try:
            # Preserve exactly the original argument objects, positional/keyword form and order.
            result=self.original_gemm(a,b,*args,**kwargs)
            record['gemm_end_ns']=time.perf_counter_ns();after=record['gemm_end_ns']
            if record['native_calls']!=1:raise ObservationError('GEMM must match exactly one original _sgemm call')
            if list(result.shape)!=[m,n] or result.data_ptr()!=context['c_pointer']:raise ObservationError('native C/output mapping differs')
            record['output']=dict(**tensor_metadata(result),aliases_a_storage=storage(result)==storage(a),
                aliases_b_storage=storage(result)==storage(b),is_given_out=out is not None and result is out)
            record['gemm_wall_ns']=record['gemm_end_ns']-record['gemm_start_ns']
            record['outer_minus_ctypes_ns']=record['gemm_wall_ns']-record['ctypes_wall_ns']
            if not (record['gemm_start_ns']<=record['ctypes_start_ns']<=record['ctypes_end_ns']<=record['gemm_end_ns']):
                raise ObservationError('native/outer intervals do not nest')
            record['observer_after_ns']=time.perf_counter_ns()-after
            record['status']='COMPLETE'
            return result
        except BaseException as exc:
            record.setdefault('gemm_end_ns',time.perf_counter_ns());record['status']='FAILED';record['error']=repr(exc)
            raise
        finally:
            if stack.pop() is not context:raise ObservationError('thread context stack corrupted')
            with self.lock:self.records.append(record)

    def native(self,*args,**kwargs):
        entered=time.perf_counter_ns();stack=self.stack()
        if not stack:raise ObservationError('_sgemm without same-thread outer GEMM')
        context=stack[-1];record=context['record']
        if record['native_calls']!=0:raise ObservationError('multiple _sgemm calls for one GEMM')
        a,b=context['a'],context['b'];out=context['out'];m,n,k=record['m'],record['n'],record['k']
        expected=(101,112 if record['ta'] else 111,112 if record['tb'] else 111,m,n,k,1.,a.data_ptr(),a.shape[1],b.data_ptr(),b.shape[1],record['beta'] if out is not None else 0.)
        if kwargs or len(args)!=14 or tuple(args[:12])!=expected or args[13]!=n:
            raise ObservationError('actual _sgemm args differ from original fp32 contract')
        context['c_pointer']=args[12]
        if out is not None and args[12]!=out.data_ptr():raise ObservationError('given C pointer differs')
        record['sgemm']=dict(layout=args[0],transa=args[1],transb=args[2],m=args[3],n=args[4],k=args[5],
            alpha=args[6],lda=args[8],ldb=args[10],beta=args[11],ldc=args[13])
        record['ctypes_thread_id']=threading.get_native_id()
        record['native_calls']=1;record['ctypes_start_ns']=time.perf_counter_ns()
        try:return self.original_native(*args,**kwargs)
        finally:
            record['ctypes_end_ns']=time.perf_counter_ns();record['ctypes_wall_ns']=record['ctypes_end_ns']-record['ctypes_start_ns']
            record['observer_sgemm_bookkeeping_ns']=(record['ctypes_start_ns']-entered)+(time.perf_counter_ns()-record['ctypes_end_ns'])

    @contextmanager
    def sample(self,step):
        if self.active or step not in (3,4,5) or any(s['step']==step for s in self.samples):
            raise ObservationError('only one sample each at updates3..5')
        module=self.module;self.step=step;self.records=[];self.sequence=0
        self.original_gemm=module.gemm;self.original_native=module._sgemm
        cls=module._LinearFn;forward_descriptor=cls.__dict__['forward'];backward_descriptor=cls.__dict__['backward']
        forward,backward=cls.forward,cls.backward
        def marked_forward(*a,**kw):
            with self.linear_context('forward'):return forward(*a,**kw)
        def marked_backward(*a,**kw):
            with self.linear_context('backward'):return backward(*a,**kw)
        summary=dict(step=step,status='STARTED',records=0,native_calls=0);self.samples.append(summary)
        failed=None;self.active=True
        try:
            module.gemm=self.outer;module._sgemm=self.native
            cls.forward=staticmethod(marked_forward);cls.backward=staticmethod(marked_backward)
            yield summary
            if self.sequence!=EXPECTED_CALLS or len(self.records)!=EXPECTED_CALLS or any(r['native_calls']!=1 or r.get('status')!='COMPLETE' for r in self.records):
                raise ObservationError('missing/excess/unpaired GEMM records versus expected149')
            summary['status']='COMPLETE'
        except BaseException as exc:
            failed=exc;summary.update(status='FAILED',error=repr(exc));raise
        finally:
            module.gemm=self.original_gemm;module._sgemm=self.original_native
            cls.forward=forward_descriptor;cls.backward=backward_descriptor;self.active=False
            summary.update(records=len(self.records),native_calls=sum(r['native_calls'] for r in self.records))
            payload=dict(protocol=PROTOCOL,step=step,status=summary['status'],clock='time.perf_counter_ns monotonic',
                timing_scope='per-thread nested spans; ctypes includes Python conversion/native packing/scheduling/compute; outer-minus-ctypes includes prep/counter/alloc/observer. Not pure microkernel or program wall.',
                records=summary['records'],calls=sorted(self.records,key=lambda r:r['call_index']))
            try:summary.update(write_bounded(self.output/f'gemm_step_{step}.json',payload))
            except BaseException as exc:
                summary.update(status='FAILED',export_error=repr(exc))
                if failed is None:raise
