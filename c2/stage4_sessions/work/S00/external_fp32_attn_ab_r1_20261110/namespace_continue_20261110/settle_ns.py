"""Reuse the established terminal/strict/A-B checks and verify namespace receipts."""
import sys

from freeze_ns import HERE, PREVIOUS, read

sys.path.insert(0,str(PREVIOUS))
import settle_attn as original


def verify_unpack(*args):
    raw, receipt = unpack(*args)
    root=raw/'job_evidence'
    for p in sorted(root.glob('*candidate*/node*/result.json')):
        r=read(p)
        attn=r.get('attention',{})
        identity=attn.get('locking_namespace')
        if not identity:
            assert not any(attn.get('counts',{}).values()) and r['status']=='FAIL_STOP'
            continue
        locking=attn['build']['locking_kml']
        assert all(identity[k]==locking[k] for k in ('path','sha256'))
        assert all(type(identity[k]) is int and identity[k]>0 for k in ('namespace_id','handle','gemm_address'))
        reached=[]
        for check in r['cpu36']['checkpoints']:
            if check['name'] in ('before_framework','after_framework'):
                continue
            reached.append(check['name'])
            libs=check['runtime']['libraries']
            actual=libs[locking['path']]
            assert all(actual[k]==v for k,v in identity.items())
            assert check['torch_intraop']==36 and actual.get('omp_get_max_threads',36)==36
            assert any(k!=locking['path'] and v.get('omp_get_max_threads')==36 for k,v in libs.items())
            assert check['snapshot']['complete'] and all(t['affinity'] and set(t['affinity'])<=set(r['cpu36']['receipt']['selected'])
                                                       for t in check['snapshot']['threads'])
        if any(attn['counts'].values()):
            assert reached and reached[0]=='after_backend'
        if r['status'].startswith('PASS'):
            assert reached[-1]=='publish'
    return raw,receipt


unpack=original.unpack
original.unpack=verify_unpack
original.HERE=HERE

if __name__=='__main__':
    original.settle(*sys.argv[1:])
