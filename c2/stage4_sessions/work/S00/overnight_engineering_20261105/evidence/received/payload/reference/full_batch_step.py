"""One full-batch original mean step; only the existing checkpoint may differ."""
import torch.nn.functional as F
from training_step import enable_checkpoint


def training_step(enc, dec, opt, v, angles, belt, y0, mask):
    h = enc(v, angles, belt, mask)
    loss = F.mse_loss(enc.head_v(h)[...,0][mask],v[mask]) + F.mse_loss(
        enc.head_coarse(h.mean(1)),F.adaptive_avg_pool2d(y0,16).flatten(1))
    opt.zero_grad()
    loss.backward()
    opt.step()
    return loss.detach()
