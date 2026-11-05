"""Synthetic protocol records, never model/numerical evidence."""
import copy

ENV = dict(OMP_NUM_THREADS='36', MKL_NUM_THREADS='36', OPENBLAS_NUM_THREADS='1',
           OMP_PLACES='cores', OMP_PROC_BIND='close')
DIGEST = 'a' * 64


def augment(spec, results, statuses, runner):
    spec['cpu36_version'] = 'CPU36_MODEL_V1'
    spec['job_id'] = 'synthetic-job'
    spec['worker_environment'] = ENV.copy()
    spec['cpu_contracts'] = {}
    spec['cpus'] = {}
    spec['cpu_contexts'] = {}
    spec['runtime_reference'] = dict(
        modules=dict(torch=dict(version='synthetic-test', path='/synthetic/torch/__init__.py'),
                     numpy=dict(version='synthetic-numpy', path='/synthetic/numpy/__init__.py')),
        libraries={'/synthetic/libomp.so': dict(sha256=DIGEST, omp_get_max_threads=36),
                   '/synthetic/libkblas.so': dict(sha256=DIGEST, omp_get_max_threads=36)})
    for d in spec['domains']:
        base = 38 * d
        receipt = dict(allocated=list(range(base, base + 38)), domain_cpus=list(range(base, base + 38)),
                       selected=list(range(base, base + 36)), reserved=[base + 36, base + 37],
                       physical_siblings={str(cpu): [cpu] for cpu in range(base, base + 38)}, node=d)
        spec['cpu_contracts'][str(d)] = receipt
    for (r, d), data in results.items():
        receipt = spec['cpu_contracts'][str(d)]
        context = dict(version='CPU36_MODEL_V1', run_id=spec['run_id'], host=spec['host'],
                       job_id=spec['job_id'], round=r, rank=d, receipt=receipt)
        spec['cpu_contexts'].setdefault(str(r), {})[str(d)] = context
        spec['cpus'].setdefault(str(r), {})[str(d)] = receipt['selected']
        pid = data['run']['pid']
        stages = ['before_framework', 'after_framework']
        for belt in spec['belts']:
            stages += [f'{belt}_after_warmup'] + [f'{belt}_after_{part}' for part in spec['parts']]
        stages.append('publish')
        records = []
        for name in stages:
            records.append(dict(name=name, pid=pid, calling_tid=pid, calling_affinity=[receipt['selected'][0]],
                                time=data['run']['started'] + 0.001 * len(records),
                                snapshot=dict(complete=True, vanished=[], errors=[], threads=[
                                    dict(tid=pid + i, affinity=[cpu]) for i, cpu in enumerate(receipt['selected'])]),
                                torch_intraop=None if name == 'before_framework' else 36,
                                torch_interop=None if name == 'before_framework' else 608,
                                parallel_info=None if name == 'before_framework' else 'SYNTHETIC',
                                environment=ENV.copy(),
                                runtime=dict(modules=copy.deepcopy(spec['runtime_reference']['modules']),
                                             libraries={'/synthetic/libomp.so': dict(sha256=DIGEST, omp_get_max_threads=36),
                                                        '/synthetic/libkblas.so': dict(sha256=DIGEST, omp_get_max_threads=36)})))
        data['run'].update(affinity=[receipt['selected'][0]], omp_threads=36,
                           cpu36=dict(version='CPU36_MODEL_V1', context=context, checkpoints=records))
        if (r, d) in statuses:
            statuses[r, d]['thread_monitor'] = dict(pid=pid, snapshots=2, incomplete_samples=0, violations=[],
                                                    threads=[dict(tid=pid + i, masks=[[cpu]]) for i, cpu in enumerate(receipt['selected'])])

