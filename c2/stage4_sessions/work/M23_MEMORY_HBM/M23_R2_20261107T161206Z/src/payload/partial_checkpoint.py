def enable_checkpoint(enc):
    """Use the existing checkpoint wrapper on the first half of the Encoder."""
    from torch.utils.checkpoint import checkpoint
    if len(enc.tf.layers) != 12:
        raise ValueError('require the frozen 12-layer Encoder')
    for layer in enc.tf.layers[:6]:
        layer.forward = lambda *a, _f=layer.forward, **k: checkpoint(_f, *a, use_reentrant=False, **k)
