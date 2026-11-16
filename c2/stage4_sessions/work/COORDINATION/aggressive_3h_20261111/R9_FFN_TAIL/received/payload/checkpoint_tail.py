"""Restore the final Linear's saved inputs without computing an unused replay output."""
from contextlib import contextmanager, nullcontext


def enable_checkpoint_tail(enc):
    import torch
    from torch.utils.checkpoint import checkpoint

    counts = dict(skipped=0, escaped=0)

    class SavedInputsOnly(torch.autograd.Function):
        @staticmethod
        def forward(ctx, x, weight):
            ctx.save_for_backward(x.reshape(-1, x.shape[-1]).float().contiguous(),
                                  weight.float().contiguous())
            return x.new_empty(0)

        @staticmethod
        def backward(ctx, grad):
            raise RuntimeError("replay-only saver must never participate in backward")

    def install(layer):
        if not layer.norm_first or any(m.p != 0 for m in (layer.dropout, layer.dropout1, layer.dropout2)):
            raise ValueError("tail replay requires the frozen norm-first, dropout-zero block")
        if tuple(layer.linear2.weight.shape) != (512, 2048) or layer.linear2.weight.dtype != torch.float32:
            raise ValueError("tail replay requires the frozen FP32 FFN projection")
        replay = [False]
        original_linear = layer.linear2.forward
        original_layer = layer._ff_block

        @contextmanager
        def recompute():
            if replay[0]:
                raise RuntimeError("nested replay is unsupported")
            replay[0] = True
            try:
                yield
            finally:
                replay[0] = False

        def linear(x):
            if not replay[0]:
                return original_linear(x)
            counts['skipped'] += 1
            SavedInputsOnly.apply(x, layer.linear2.weight)
            # The framework must raise its early-stop exception while saving the
            # final input/weight. No dummy output may reach any model operation.
            counts['escaped'] += 1
            raise RuntimeError("checkpoint did not stop at the final FFN saved inputs")

        layer.linear2.forward = linear
        layer._ff_block = lambda *a, **k: checkpoint(original_layer, *a, use_reentrant=False,
                                                   context_fn=lambda: (nullcontext(), recompute()), **k)

    if len(enc.tf.layers) != 12:
        raise ValueError("exactly twelve frozen encoder blocks required")
    for layer in enc.tf.layers:
        install(layer)
    return counts
