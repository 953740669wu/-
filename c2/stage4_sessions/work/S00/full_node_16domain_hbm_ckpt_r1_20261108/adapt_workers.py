"""Make only the synchronized 16-domain and batch-specific worker changes."""


def swap(source, before, after):
    if source.count(before) != 1:
        raise ValueError(f"expected one frozen source anchor: {before[:100]!r}")
    return source.replace(before, after)


def adapt_worker(raw, electrodes):
    code = raw.decode()
    code = swap(code, "release = barrier(args, step) if not strict else None", "release = barrier(args, step)")
    if electrodes == 16:
        return code.encode()
    code = swap(code, '    planned = 5 if strict else 25\n',
                '    planned = 5 if strict else 25\n'
                '    batch = int(os.environ["S00_BATCH"])\n'
                '    ckpt_layers = int(os.environ["S00_MATCHED_CKPT"])\n'
                '    if batch not in (32,64) or ckpt_layers != 12:\n'
                '        raise ValueError("expected a dependency-bound B32 or B64 with CKPT12")\n')
    code = swap(code, '    masks = [torch.rand(32, 928) < .5 for _ in range(25)]\n'
                     '    pairing = dict(protocol="S09_REAL32_ENGINEERING_B32_V1", descriptor_sha256=args.descriptor_sha,\n'
                     '                   batch_size=32, electrodes=32,',
                '    if batch == 64:\n'
                '        order = order + order\n'
                '        frozen = json.loads((args.descriptor.parent/"B64_SAMPLE_PLAN.json").read_bytes())\n'
                '        if order != frozen["order"] or args.descriptor_sha != frozen["descriptor_sha256"] or (\n'
                '                training.model_sha(models[args.variant]) != frozen["initial_weights_sha256"]):\n'
                '            raise ValueError("independent B64 input or initial identity differs")\n'
                '    masks = [torch.rand(batch, 928) < .5 for _ in range(25)]\n'
                '    protocol = "S09_REAL32_ENGINEERING_B32_V1" if batch == 32 else "S00_REAL32_ENGINEERING_B64_V1"\n'
                '    pairing = dict(protocol=protocol, descriptor_sha256=args.descriptor_sha,\n'
                '                   batch_size=batch, electrodes=32,')
    code = swap(code, '    if prior.is_file() and json.loads(prior.read_bytes()) != pairing:',
                '    if batch == 32 and json.loads(prior.read_bytes()) != pairing:')
    code = swap(code, '    checkpoint = args.variant in ("ckpt_ddr","ckpt_hbm")\n'
                     '    if checkpoint:\n'
                     '        enable_checkpoint(models[args.variant])\n'
                     '    result["checkpoint_layers"] = 12 if checkpoint else 0',
                '    enable_checkpoint(models[args.variant])\n'
                '    result["checkpoint_layers"] = ckpt_layers')
    code = swap(code, '            ids = order[(step-1)*32:step*32]', '            ids = order[(step-1)*batch:step*batch]')
    code = swap(code, 'step=step, batch_size=32, frame_indices=ids', 'step=step, batch_size=batch, frame_indices=ids')
    code = swap(code, '                    if checkpoint:\n'
                     '                        trace_matches = logical > pinned["kml_calls"] and all(\n'
                     '                            shapes.get(k,0) >= n for k,n in pinned["native_shapes"].items())\n'
                     '                    else:\n'
                     '                        trace_matches = logical == pinned["kml_calls"] and shapes == pinned["native_shapes"]',
                '                    trace_matches = logical == pinned["kml_calls"] and shapes == pinned["native_shapes"]')
    return code.encode()


def adapt_batch(raw):
    code = raw.decode()
    code = swap(code, '    if v.shape != (32, 928) or image.shape != (32, 1, 64, 64) or angles.shape != (928, 4):\n'
                     '        raise ValueError(\'real 32E B32 tensor contract\')\n'
                     '    return v,image,angles.expand(32,928,4),torch.ones(32,928,dtype=torch.float32)',
                '    b=len(indices)\n'
                '    if b not in (32,64) or v.shape != (b, 928) or image.shape != (b, 1, 64, 64) or angles.shape != (928, 4):\n'
                '        raise ValueError(\'real 32E B32/B64 tensor contract\')\n'
                '    return v,image,angles.expand(b,928,4),torch.ones(b,928,dtype=torch.float32)')
    return code.encode()
