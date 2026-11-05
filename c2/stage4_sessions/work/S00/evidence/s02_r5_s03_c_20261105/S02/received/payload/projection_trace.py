"""Observe unchanged F.linear inputs/adjoints for the two worst projection parameters."""
import torch
import torch.nn.functional as F
from diagnostic_common import errors

NAMES = ['enc.tf.layers.1.self_attn.in_proj_weight', 'enc.tf.layers.10.self_attn.in_proj_weight']


def install(models, records):
    selected = {p.data_ptr():name for name,p in models.named_parameters() if name in NAMES}
    original = F.linear
    def observed(x, weight, bias=None):
        value = original(x,weight,bias)
        name = selected.get(weight.data_ptr())
        if name:
            # MHA packed projection is [sequence,batch,features] in the frozen model.
            if x.ndim != 3 or x.shape[0] != 208:
                raise RuntimeError('unexpected packed projection layout')
            record = dict(input=x.detach().transpose(0,1).clone(), adjoint=None)
            records.setdefault(name,[]).append(record)
            def backward(g):record['adjoint']=g.detach().transpose(0,1).clone()
            value.register_hook(backward)
        return value
    F.linear = observed
    return original


def summarize(ref, got, ref_snapshot, got_snapshot):
    result = {}
    for name in NAMES:
        xr=torch.cat([x['input'] for x in ref[name]])
        xg=torch.cat([x['input'] for x in got[name]])
        yr=torch.cat([x['adjoint'] for x in ref[name]])
        yg=torch.cat([x['adjoint'] for x in got[name]])
        item=dict(input=errors(xr,xg),output_adjoint=errors(yr,yg))
        # Fixed coordinates come from round2's worst weight and bias updates.
        if '.10.' in name:
            row,column=divmod(706127,512)
            item['round2_worst_coordinate']=dict(row=row,column=column,
                reference_dot_float64=(yr[...,row].double()*xr[...,column].double()).sum().item(),
                candidate_dot_float64=(yg[...,row].double()*xg[...,column].double()).sum().item(),
                reference_gradient=ref_snapshot['grad.'+name].flatten()[706127].item(),
                candidate_gradient=got_snapshot['grad.'+name].flatten()[706127].item())
        else:
            bias=name.replace('in_proj_weight','in_proj_bias')
            item['round2_worst_coordinate']=dict(index=576,
                reference_sum_float64=yr[...,576].double().sum().item(),
                candidate_sum_float64=yg[...,576].double().sum().item(),
                reference_gradient=ref_snapshot['grad.'+bias][576].item(),
                candidate_gradient=got_snapshot['grad.'+bias][576].item())
        result[name]=item
    return result
