"""Fixed two-rank objective; parameter gradients are already averaged by DDP."""
from fractions import Fraction


def backward_weights(counts, rank):
    if rank not in (0, 1) or len(counts) != 2 or any(
            len(row) != 2 or any(type(n) is not int or n < 0 for n in row) for row in counts):
        raise ValueError('two ranks of nonnegative integer element counts required')
    voltage, coarse = (sum(row[i] for row in counts) for i in range(2))
    if voltage <= 0 or coarse <= 0:
        raise ValueError('zero global loss denominator; no resampling or epsilon')
    return Fraction(2, voltage), Fraction(2, coarse)


def input_gradient_scale(world_size):
    if world_size != 2:
        raise ValueError('fixed world_size=2 required')
    return Fraction(1, world_size)


def validate_shards(indices, shards):
    if (len(indices) != 64 or len(set(indices)) != 64 or len(shards) != 2
            or list(shards[0]) != list(indices[:32]) or list(shards[1]) != list(indices[32:])):
        raise ValueError('require ordered, disjoint first32/last32 exact global64')
    return list(indices)
