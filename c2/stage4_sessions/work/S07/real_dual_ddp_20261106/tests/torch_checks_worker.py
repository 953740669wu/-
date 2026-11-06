"""Small real-autograd/DDP fixtures; no corpus or full-model update."""
import argparse
import copy
from datetime import timedelta
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'candidate'))
import cpu36_contract as cpu36
from runtime_guard import load_allocation
from training_graph import backward_loss, pretraining_model
from training_support import gather_tensor, load_reference, validate_ddp_api


def main(args):
    # Linux compute-side checks must inherit the current job's explicit two-domain allocation.
    if sys.platform == 'linux':
        allocation = load_allocation(Path(os.environ['S07_TEST_ALLOCATION']))
        receipt = allocation['ranks'][args.rank]
        os.sched_setaffinity(0, receipt['selected'])
    import torch
    import torch.distributed as dist
    config = json.loads((ROOT / 'training_config.json').read_text())['ddp']
    if sys.platform == 'linux':
        validate_ddp_api(torch, config)

    class TinyEncoder(torch.nn.Module):
        def __init__(self):
            super().__init__()
            self.val = torch.nn.Linear(1, 4)
            self.pos = torch.nn.Linear(4, 4)
            self.tf = torch.nn.Linear(4, 4)
            self.mask_tok = torch.nn.Parameter(torch.zeros(4))
            self.head_v = torch.nn.Linear(4, 1)
            self.head_coarse = torch.nn.Linear(4, 256)

        def forward(self, v, angles, belt, mask):
            h = self.val(v[..., None]) + self.pos(angles)
            return self.tf(torch.where(mask[..., None], self.mask_tok.expand_as(h), h))

    torch.manual_seed(7)
    encoder = TinyEncoder()
    graph = pretraining_model(torch, encoder)
    v = torch.ones(32, 208, requires_grad=True)
    image = torch.zeros(32, 1, 16, 16, requires_grad=True)
    values = (v, image, torch.ones(32, 208, 4), torch.zeros(32, 208))
    mask = torch.zeros(32, 208, dtype=torch.bool)
    mask.reshape(-1)[:1 if args.rank == 0 else 3] = True
    if args.mode == 'math':
        output = graph(*values, mask)
        backward_loss(output, (4, 16384)).backward()
        assert set(dict(graph.named_parameters())) == {'encoder.'+n for n, _ in encoder.named_parameters()}
        assert all(p.grad is not None and torch.isfinite(p.grad).all() for p in encoder.parameters())
        assert v.grad is not None and image.grad is not None
        encoder.zero_grad(set_to_none=True)
        empty = graph(*values, torch.zeros_like(mask))
        backward_loss(empty, (4, 16384)).backward()
        assert empty['voltage_sum'].item() == 0
        assert all(p.grad is not None and torch.isfinite(p.grad).all() for p in encoder.parameters())
        # Real input autograd is twice the corresponding global-objective shard; DDP only averages parameters.
        full = torch.tensor([2., 3.], requires_grad=True)
        full.square().sum().div(2).backward()
        local = torch.tensor([2.], requires_grad=True)
        (2 * local.square().sum() / 2).backward()
        assert torch.equal(local.grad / 2, full.grad[:1])
        post_tiny = torch.get_rng_state().clone()
        isolated = torch.Generator().set_state(post_tiny)
        expected_tiny = torch.rand(5)
        torch.rand(17)
        assert torch.equal(expected_tiny, torch.rand(5, generator=isolated))
        # Mask generator copies the post-initialization state; unrelated global draws cannot affect it.
        if sys.platform == 'linux' and os.environ.get('S07_REFERENCE_ROOT'):
            ref, _ = load_reference(os.environ['S07_REFERENCE_ROOT'], os.environ['S07_REFERENCE_READY'])
            torch.manual_seed(0)
            # Consume exactly the original Encoder initialization, not a seed0 mask shortcut.
            definitions = ref.accepted.model_definitions(torch)
            original = definitions['Encoder']()
            post = torch.get_rng_state().clone()
            del original
            stream = ref.new_mask_stream(torch, post)
            expected = torch.rand(64, 208) < .5
            torch.rand(17)
            actual = stream.next(1)
            assert torch.equal(expected, actual)
            checkpoint = stream.state_dict()
            restored = ref.new_mask_stream(torch, post)
            restored.load_state_dict(checkpoint)
            assert torch.equal(stream.next(2), restored.next(2))
        elif sys.platform == 'linux':
            raise ValueError('Linux checks require frozen S02 reference paths for RNG check')
    else:
        from torch.nn.parallel import DistributedDataParallel
        reference = pretraining_model(torch, copy.deepcopy(encoder)) if args.rank == 0 else None
        print('TINY before_pg', args.rank, flush=True)
        dist.init_process_group('gloo', init_method=args.init_method,
                                rank=args.rank, world_size=2, timeout=timedelta(seconds=10))
        print('TINY after_pg', args.rank, flush=True)
        ddp = DistributedDataParallel(graph, **config)
        print('TINY after_ddp', args.rank, flush=True)
        output = ddp(*values, mask)
        counts = torch.tensor([int(mask.sum()), 8192], dtype=torch.int64)
        dist.all_reduce(counts)
        backward_loss(output, counts.tolist()).backward()
        print('TINY after_backward', args.rank, flush=True)
        assert all(p.grad is not None for p in encoder.parameters())
        for parameter in encoder.parameters():
            pair = [torch.empty_like(parameter.grad), torch.empty_like(parameter.grad)]
            dist.all_gather(pair, parameter.grad)
            assert torch.equal(pair[0], pair[1])
        input_grads = [gather_tensor(torch, dist, value.grad, args.rank) for value in values[:2]]
        if args.rank == 0:
            full_v = torch.ones(64, 208, requires_grad=True)
            full_image = torch.zeros(64, 1, 16, 16, requires_grad=True)
            full_mask = torch.zeros(64, 208, dtype=torch.bool)
            full_mask.reshape(-1)[[0, 32*208, 32*208+1, 32*208+2]] = True
            full = reference(full_v, full_image, torch.ones(64, 208, 4), torch.zeros(64, 208), full_mask)
            (full['voltage_sum']/4 + full['coarse_sum']/16384).backward()

            metrics = []

            def strict(name, left, right):
                delta = left.double()-right.double()
                norm = left.double().norm().item()
                absolute = delta.abs().max().item()
                relative = delta.norm().item()/max(norm, 1e-12)
                metrics.append(dict(name=name, max_abs=absolute, l2_relative=relative,
                                    reference_norm=norm,
                                    passed=absolute <= 2e-5 and (norm <= 1e-8 or relative <= 2e-6)))

            for name, parameter in encoder.named_parameters():
                strict(name, dict(reference.encoder.named_parameters())[name].grad, parameter.grad)
            strict('input_v', full_v.grad, input_grads[0]/2)
            strict('input_image', full_image.grad, input_grads[1]/2)
            (args.output / 'strict_pair_metrics.json').write_text(json.dumps(metrics, indent=2))
            assert all(row['passed'] for row in metrics), [row for row in metrics if not row['passed']]
        dist.destroy_process_group()
    if sys.platform == 'linux':
        cpu36.validate_snapshot(receipt['selected'], cpu36.snapshot_threads(os.getpid()))
    return 0


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--rank', type=int, choices=(0, 1), required=True)
    parser.add_argument('--mode', choices=('math', 'ddp'), required=True)
    parser.add_argument('--init-method')
    sys.exit(main(parser.parse_args()))
