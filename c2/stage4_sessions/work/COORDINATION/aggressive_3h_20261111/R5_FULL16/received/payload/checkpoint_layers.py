def enable_checkpoint(enc):
    """Same per-layer non-reentrant checkpoint wrapper as the frozen source."""
    from torch.utils.checkpoint import checkpoint
    for layer in enc.tf.layers:
        layer.forward = lambda *a, _f=layer.forward, **k: checkpoint(_f, *a, use_reentrant=False, **k)
