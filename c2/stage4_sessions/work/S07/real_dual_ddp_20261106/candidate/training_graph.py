"""Put the original encoder, both heads and squared-error sums inside DDP."""


def pretraining_model(torch, encoder):
    class Pretraining(torch.nn.Module):
        def __init__(self):
            super().__init__()
            self.encoder = encoder

        def forward(self, v, image, angles, belt, mask):
            h = self.encoder(v, angles, belt, mask)
            voltage = self.encoder.head_v(h)
            coarse = self.encoder.head_coarse(h.mean(1))
            target = torch.nn.functional.adaptive_avg_pool2d(image, 16).flatten(1)
            # Empty local indexing still yields a differentiable zero, without resampling.
            voltage_sum = (voltage[..., 0][mask] - v[mask]).square().sum()
            coarse_sum = (coarse - target).square().sum()
            return dict(outputs=dict(h=h, v=voltage, coarse=coarse),
                        voltage_sum=voltage_sum, coarse_sum=coarse_sum)

    return Pretraining()


def backward_loss(result, global_counts):
    masked, coarse = global_counts
    if masked <= 0 or coarse <= 0:
        raise ValueError('zero global loss denominator')
    return 2 * (result['voltage_sum'] / masked + result['coarse_sum'] / coarse)
