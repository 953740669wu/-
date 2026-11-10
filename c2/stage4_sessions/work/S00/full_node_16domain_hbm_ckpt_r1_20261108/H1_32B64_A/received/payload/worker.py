"""One original Encoder replica in one bound domain, with the R12 strict comparator."""
import argparse
import ctypes
from contextlib import nullcontext
import hashlib
import json
import os
from pathlib import Path
import random
import sys
import time
import traceback

import cpu36_guard
from data_gate import engineering_data as data
from diagnostic_common import configure_backend, finish_backend
import engineering_training as training
import memory_metrics
from m23_memory import SavedStorage
from checkpoint_layers import enable_checkpoint

ROOT = Path(__file__).resolve().parent
BASELINE = "e6c5c4411c453c8168939cd51d737a7e9d8232bdfff05da3967805a5e917ff26"


def tensors(model, optimizer, initial, captured, losses, values):
    packed = {"output." + name: value for name, value in captured.items()}
    packed.update(("loss." + name, value) for name, value in losses.items())
    packed.update((f"input_grad.{i}", values[i].grad.detach()) for i in (0, 1))
    params = dict(model.named_parameters())
    for name, p in params.items():
        packed["grad." + name] = p.grad.detach()
        packed["param." + name] = p.detach()
        packed["delta." + name] = p.detach() - initial[name]
        state = optimizer.state[p]
        if set(state) != {"step", "exp_avg", "exp_avg_sq"}:
            raise ValueError("optimizer state keys differ")
        for key, value in state.items():
            packed[f"state.{name}.{key}"] = value
    for name, value in model.state_dict().items():
        if name not in params:
            packed["buffer." + name] = value
    return packed


def strict_evidence(torch, accepted, args, result, step, model, opt, initial, captured, loss, values):
    got = tensors(model, opt, initial, captured, loss, values)
    path = args.reference / args.output.name / f"strict_step{step}.pt"
    if args.variant == "baseline":
        torch.save(got, path)
        result.setdefault("reference_snapshots", []).append(
            dict(step=step, bytes=path.stat().st_size, sha256=data.sha(path)))
        return
    receipt = json.loads((path.parent / "result.json").read_bytes())
    pinned = receipt["reference_snapshots"][step-1]
    if receipt["status"] != "PASS_STRICT_REFERENCE5" or receipt["completed_updates"] != 5 or (
            path.stat().st_size != pinned["bytes"] or data.sha(path) != pinned["sha256"]):
        raise ValueError("invalid pinned strict DDR snapshot")
    ref = torch.load(path, map_location="cpu", mmap=True, weights_only=True)
    if set(ref) != set(got):
        raise ValueError("strict tensor keys differ")
    for name, value in got.items():
        category = ("exact" if name.endswith(".step") else "state") if name.startswith("state.") else "tensor"
        accepted.compare(torch, f"{step}.{name}", ref[name], value, category, result["metrics"])


def write(path, value):
    temporary = path.with_suffix(".partial")
    temporary.write_text(json.dumps(value, indent=2) + "\n")
    temporary.replace(path)


def residency(out, label):
    for name in ("numa_maps", "status"):
        (out / f"{label}.{name}").write_bytes((Path("/proc/self") / name).read_bytes())


def barrier(args, step):
    rendezvous = args.phase_root / "barriers"
    node = args.output.name
    write(rendezvous / f"{step}.{node}.ready", dict(pid=os.getpid(), arrived=time.monotonic_ns()))
    release = rendezvous / f"{step}.release"
    while time.monotonic() < args.deadline:
        if release.is_file():
            at = json.loads(release.read_bytes())["release_at_ns"]
            time.sleep(max(0, (at - time.monotonic_ns()) / 1e9))
            return at
        time.sleep(.01)
    raise TimeoutError(f"barrier {step} deadline")


def runtime_check(runtime, hbm):
    expected = json.loads((ROOT / "RUNTIME_EXPECTED.json").read_bytes())
    if hbm:
        expected["env"]["LD_PRELOAD"] = hbm["path"] + ":" + expected["env"]["LD_PRELOAD"]
    if any(runtime.get(k) != v for k, v in expected.items()):
        raise ValueError("frozen R4 framework/KML/OpenMP/shim identity differs")
    if "libraries_after" in runtime and runtime["libraries_after"] != expected["libraries"]:
        raise ValueError("mapped library drift")


def run(args, result):
    strict = args.phase == "strict"
    planned = 5 if strict else 25
    batch = int(os.environ["S00_BATCH"])
    ckpt_layers = int(os.environ["S00_MATCHED_CKPT"])
    if batch not in (32,64) or ckpt_layers != 12:
        raise ValueError("expected a dependency-bound B32 or B64 with CKPT12")
    expected_cpu = json.loads(args.allocation.read_bytes())["receipt"]["selected"]
    guard = result["cpu36"] = {}
    after_numactl = sorted(os.sched_getaffinity(0))
    cpu36_guard.prepare(expected_cpu, args.allocation, guard)
    write(args.output / "before_torch_affinity.json", dict(pid=os.getpid(), job_id=result["job_id"],
          after_numactl=after_numactl, selected=sorted(os.sched_getaffinity(0)), node=guard["receipt"]["node"],
          reserved=guard["receipt"]["reserved"], guard_before_framework=guard["checkpoints"][0]))
    import numpy as np
    import torch
    cpu36_guard.checkpoint(guard, "after_framework", torch)
    runtime, expected = configure_backend(torch, "kml", expected_cpu)
    result["runtime"] = runtime
    paths = {line.split()[-1] for line in Path("/proc/self/maps").read_text().splitlines()
             if "libhbm_alloc" in line}
    hbm = None
    if args.variant in ("candidate","ckpt_hbm"):
        library = os.environ["M23_HBM_LIBRARY"]
        if paths != {library} or data.sha(library) != os.environ["M23_HBM_LIBRARY_SHA"]:
            raise ValueError("HBM allocator path/SHA mapping differs")
        hbm = dict(path=library, sha256=data.sha(library), node=int(os.environ["HBM_NODE"]),
                   cap_MiB=int(os.environ["HBM_MB"]))
    elif paths or os.environ.get("HBM_NODE"):
        raise ValueError("unexpected allocator in DDR worker")
    result["hbm_allocator"] = hbm
    runtime_check(runtime, hbm)
    module = sys.modules["kml_ops"]
    if data.sha(module.__file__) != BASELINE or module.LINEAR_DTYPE != torch.float32:
        raise ValueError("wrong original baseline or dtype")
    native = module._sgemm
    if not isinstance(native, ctypes._CFuncPtr):
        raise ValueError("actual native KML function required")
    shapes = {}

    def count_native(*values):
        if len(values) != 14:
            raise ValueError("unexpected direct SGEMM ABI")
        key = str(tuple(values[i] for i in (0,1,2,3,4,5,6,8,10,11,13)))
        shapes[key] = shapes.get(key, 0) + 1
        return native(*values)

    module._sgemm = count_native
    cpu36_guard.checkpoint(guard, "after_backend", torch)
    metadata = data.load_descriptor(args.descriptor, args.descriptor_sha)
    ledger = data.Exposure(args.output / "EXPOSURE_LEDGER.json", metadata["description"])
    loading = time.monotonic_ns()
    loaded = data.load_arrays(metadata, ledger)
    result["load_ns"] = [loading, time.monotonic_ns()]
    train = loaded["train"]
    normalization = dict(image_scale=loaded["image_scale"], scope=loaded["normalization_scope"],
                         fit_partition="train", train_units=[x["unit"] for x in metadata["units"]["train"]])
    if train["v"].shape != (800,928) or train["y0"].shape != (800,1,64,64):
        raise ValueError("frozen real 32E input dimensions differ")
    sys.path.insert(0, str(ROOT / "tests"))
    import check_equivalence as accepted
    definitions = accepted.model_definitions(torch)
    factory, angles = definitions["Encoder"], definitions["protocol_angles"](32, 5)
    roles = (args.variant,)
    models, opts = {}, {}
    for role in roles:
        torch.manual_seed(0)
        np.random.seed(0)
        random.seed(0)
        model = models[role] = factory()
        opts[role] = training.optimizer(torch, model)
        if sum(p.numel() for p in model.parameters()) != 37995777 or len(model.tf.layers) != 12:
            raise ValueError("original full Encoder dimensions differ")
    initial = {n: p.detach().clone() for n, p in models[args.variant].named_parameters()} if strict else None
    order = list(range(800))
    random.Random(0).shuffle(order)
    if batch == 64:
        order = order + order
        frozen = json.loads((args.descriptor.parent/"B64_SAMPLE_PLAN.json").read_bytes())
        if order != frozen["order"] or args.descriptor_sha != frozen["descriptor_sha256"] or (
                training.model_sha(models[args.variant]) != frozen["initial_weights_sha256"]):
            raise ValueError("independent B64 input or initial identity differs")
    masks = [torch.rand(batch, 928) < .5 for _ in range(25)]
    protocol = "S09_REAL32_ENGINEERING_B32_V1" if batch == 32 else "S00_REAL32_ENGINEERING_B64_V1"
    pairing = dict(protocol=protocol, descriptor_sha256=args.descriptor_sha,
                   batch_size=batch, electrodes=32, offset=5, tokens=928, dtype="fp32", checkpoint_layers=0,
                   width=512, layers=12, heads=8, feedforward=2048, seed=0, full_encoder_parameters=37995777,
                   initial_weights_sha256=training.model_sha(models[args.variant]),
                   angles_sha256=hashlib.sha256(angles.numpy().tobytes()).hexdigest(),
                   normalization=normalization, order=order,
                   mask_sha256=[hashlib.sha256(mask.numpy().tobytes()).hexdigest() for mask in masks],
                   mask_selected=[int(mask.sum()) for mask in masks])
    prior = args.descriptor.parent / "PRIOR_PAIRING.json"
    if batch == 32 and json.loads(prior.read_bytes()) != pairing:
        raise ValueError("external 32E reference differs")
    ref_dir = args.reference / args.output.name
    if strict and args.variant == "baseline":
        write(args.output / "PAIRING.json", pairing)
        reference_steps = []
    else:
        if json.loads((ref_dir / "PAIRING.json").read_bytes()) != pairing:
            raise ValueError("same-job 32E frame/mask/model pairing differs")
        reference_steps = [json.loads(line) for line in (ref_dir/"steps.jsonl").read_bytes().splitlines()]
        if len(reference_steps) != 5:
            raise ValueError("frozen DDR strict reference incomplete")
    result["pairing_sha256"] = hashlib.sha256(json.dumps(pairing,sort_keys=True).encode()).hexdigest()
    enable_checkpoint(models[args.variant])
    result["checkpoint_layers"] = ckpt_layers
    residency(args.output, "initialized")
    with (args.output / "steps.jsonl").open("x") as log:
        for step in range(1, planned + 1):
            if time.monotonic() >= args.deadline:
                raise TimeoutError("shared stop-new-update deadline")
            ids = order[(step-1)*batch:step*batch]
            mask = masks[step-1]
            frames = [train["frame_ids"][i] for i in ids]
            mask_sha = pairing["mask_sha256"][step-1]
            ledger.attempt(step, ids, frames)
            if not strict and step == 6:
                residency(args.output, "observe_start")
            captures, losses, values, rows = {}, {}, {}, []
            for role in roles:
                model = models[role]
                captured = captures[role] = {}
                handles = []
                if strict:
                    def capture(key):
                        def hook(_module, _args, output):
                            captured[key] = output.detach().clone()
                        return hook
                    for key, layer in (("h", model), ("v", model.head_v), ("coarse", model.head_coarse)):
                        handles.append(layer.register_forward_hook(capture(key)))
                values[role] = training.batch(torch, train, ids, angles)
                cpu36_guard.checkpoint(guard, f"before_{role}_{step}", torch)
                rss_before = memory_metrics.rss()
                shapes.clear()
                before = runtime["kml_gemm_calls"]
                release = barrier(args, step)
                if time.monotonic() >= args.deadline:
                    raise TimeoutError("deadline before update")
                reset = memory_metrics.reset_peak() if not strict else None
                start_memory = memory_metrics.rss() if reset else None
                if reset and (not reset["available"] or start_memory["peak_rss_bytes"] != start_memory["rss_bytes"]):
                    raise RuntimeError("could not reset/verify per-step RSS high-water mark")
                inventory = SavedStorage(model, values[role]) if (
                    strict and step == 1 and os.environ.get("S09_INVENTORY") == "1") else None
                hooks = torch.autograd.graph.saved_tensors_hooks(inventory.pack, inventory.unpack) if inventory else nullcontext()
                begin = time.monotonic_ns()
                try:
                    with hooks:
                        loss = losses[role] = training.train_step(torch, model, opts[role], values[role], mask)
                finally:
                    for handle in handles:
                        handle.remove()
                end = time.monotonic_ns()
                rss_after = memory_metrics.rss()
                training.validate_update(torch, model, opts[role], values[role], step)
                actual_huge = rss_after["hugetlb_bytes"]
                if (not hbm and actual_huge != 0) or (hbm and not 0 < actual_huge <= hbm["cap_MiB"]*2**20):
                    raise ValueError(f"unexpected training hugetlb bytes {actual_huge}")
                logical = runtime["kml_gemm_calls"] - before
                if inventory:
                    result["strict_step1_storage"] = inventory.summary(model, opts[role])
                if not logical or sum(shapes.values()) != logical:
                    raise ValueError("actual 32E direct KML evidence missing")
                if reference_steps:
                    pinned = reference_steps[(step-1) % 5]
                    trace_matches = logical == pinned["kml_calls"] and shapes == pinned["native_shapes"]
                    if not trace_matches:
                        result["bad_native"] = dict(step=step, role=role, shapes=dict(shapes), logical=logical)
                        raise ValueError("native trace differs from same-job 32E DDR")
                    if step <= 5:
                        for name, item in loss.items():
                            accepted.compare(torch, f"{role}.{step}.reference_loss.{name}",
                                             torch.tensor(pinned["losses"][name], dtype=torch.float32),
                                             item, "tensor", result["metrics"])
                if not all(torch.isfinite(item) for item in loss.values()):
                    raise ValueError("nonfinite epoch loss")
                cpu36_guard.checkpoint(guard, f"after_{role}_{step}", torch)
                rows.append(dict(role=role, step=step, batch_size=batch, frame_indices=ids, frame_ids=frames,
                                 mask_sha256=mask_sha, losses={k: v.item() for k,v in loss.items()},
                                 start_ns=begin, end_ns=end, release_ns=release, step_seconds=(end-begin)/1e9,
                                 rss_before=rss_before, training_start=start_memory, rss_after=rss_after,
                                 peak_reset=reset, kml_calls=logical, native_sgemm_calls=sum(shapes.values()),
                                 native_shapes=dict(shapes), sampled=not strict and step >= 6))
            for row in rows:
                log.write(json.dumps(row) + "\n")
            log.flush()
            if strict:
                strict_evidence(torch, accepted, args, result, step, models[args.variant], opts[args.variant],
                                initial, captures[args.variant], losses[args.variant], values[args.variant])
            ledger.confirm(step)
            result["completed_updates"] = step
    if not strict:
        barrier(args, 26)
        residency(args.output, "observe_end")
    data.load_descriptor(args.descriptor, args.descriptor_sha)
    result["final_model_sha256"] = {role: training.model_sha(model) for role, model in models.items()}
    finish_backend(runtime, expected)
    runtime_check(runtime, hbm)
    cpu36_guard.checkpoint(guard, "publish", torch)
    if strict:
        result["status"] = "PASS_STRICT_REFERENCE5" if args.variant == "baseline" else "PASS_STRICT_ENCODER5"
    else:
        result["status"] = "PASS_PERF25"


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", choices=("strict", "perf"), required=True)
    parser.add_argument("--variant", choices=("baseline", "candidate", "ckpt_ddr", "ckpt_hbm"), required=True)
    for flag in ("descriptor", "allocation", "phase-root", "output", "reference"):
        parser.add_argument("--" + flag, type=Path, required=True)
    parser.add_argument("--descriptor-sha", required=True)
    parser.add_argument("--deadline", required=True, type=float)
    args = parser.parse_args()
    args.output.mkdir(exist_ok=False)
    result = dict(status="STARTED", job_id=os.environ["CCS_JOB_ID"], host=os.uname().nodename,
                  phase=args.phase, variant=args.variant, pid=os.getpid(), started_ns=time.monotonic_ns(), metrics=[], completed_updates=0)
    try:
        run(args, result)
        code = 0
    except Exception as exc:
        result.update(status="FAIL_STOP", error=repr(exc), traceback=traceback.format_exc())
        code = 2
    result["finished_ns"] = time.monotonic_ns()
    write(args.output / "result.json", result)
    raise SystemExit(code)
