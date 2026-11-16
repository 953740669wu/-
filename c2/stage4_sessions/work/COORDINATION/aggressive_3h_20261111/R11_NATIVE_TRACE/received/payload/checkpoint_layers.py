def enable_checkpoint(enc, mode="full"):
    """Keep attention activations and recompute only FFN in the candidate."""
    from torch.utils.checkpoint import checkpoint
    if mode not in ("full", "ffn"):
        raise ValueError("unknown checkpoint scope")
    attribute = "forward" if mode == "full" else "_ff_block"
    for layer in enc.tf.layers:
        original = getattr(layer, attribute)
        setattr(layer, attribute, lambda *a, _f=original, **k: checkpoint(_f, *a, use_reentrant=False, **k))
