"""One original Encoder replica in one bound domain, with the R12 strict comparator."""
import argparse
import ctypes
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
import profile_contract

ROOT = Path(__file__).resolve().parent
BASELINE = "e6c5c4411c453c8168939cd51d737a7e9d8232bdfff05da3967805a5e917ff26"


def compare_models(torch,accepted,left,right,opts,initial,metrics,prefix):
    a=dict(left.named_parameters());b=dict(right.named_parameters())
    if set(a)!=set(b):raise ValueError('model parameter keys differ')
    for name,p in a.items():
        q=b[name]
        for key,x,y in [('grad',p.grad,q.grad),('param',p.detach(),q.detach()),
                        ('delta',p.detach()-initial[name],q.detach()-initial[name])]:
            accepted.compare(torch,prefix+key+'.'+name,x,y,'tensor',metrics)
        sa,sb=opts[0].state[p],opts[1].state[q]
        if set(sa)!=set(sb) or set(sa)!={'step','exp_avg','exp_avg_sq'}:raise ValueError('optimizer keys differ')
        for key,value in sa.items():accepted.compare(torch,prefix+'state.'+name+'.'+key,value,sb[key],
                                                   'exact' if key=='step' else 'state',metrics)
    aa,bb=left.state_dict(),right.state_dict()
    if set(aa)!=set(bb):raise ValueError('model state keys differ')
    for name in set(aa)-set(a):accepted.compare(torch,prefix+'buffer.'+name,aa[name],bb[name],'tensor',metrics)


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


def runtime_check(runtime):
    expected = json.loads((ROOT / "RUNTIME_EXPECTED.json").read_bytes())
    if any(runtime.get(k) != v for k, v in expected.items()):
        raise ValueError("frozen R4 framework/KML/OpenMP/shim identity differs")
    if "libraries_after" in runtime and runtime["libraries_after"] != expected["libraries"]:
        raise ValueError("mapped library drift")


def run(args, result):
    strict = args.phase == "strict"
    planned = 5 if strict else 25
    ref = json.loads((ROOT / "REFERENCE_FIRST5.json").read_bytes())
    epoch = json.loads((ROOT / "REFERENCE_EPOCH25.json").read_bytes())
    if args.descriptor_sha != ref["descriptor_sha256"]:
        raise ValueError("frozen descriptor differs")
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
    runtime_check(runtime)
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
    profile_contract.check_data(metadata["description"], ref)
    ledger = data.Exposure(args.output / "EXPOSURE_LEDGER.json", metadata["description"])
    loading = time.monotonic_ns()
    loaded = data.load_arrays(metadata, ledger)
    result["load_ns"] = [loading, time.monotonic_ns()]
    train = loaded["train"]
    normalization = dict(image_scale=loaded["image_scale"], scope=loaded["normalization_scope"],
                         fit_partition="train", train_units=[x["unit"] for x in metadata["units"]["train"]])
    if len(train["v"]) != 1600 or normalization != ref["normalization"]:
        raise ValueError("original data or normalization differs")
    sys.path.insert(0, str(ROOT / "tests"))
    import check_equivalence as accepted
    definitions = accepted.model_definitions(torch)
    factory, angles = definitions["Encoder"], definitions["protocol_angles"](16, 1)
    roles = ("baseline", "control") if strict else ("baseline",)
    models, opts = {}, {}
    for role in roles:
        torch.manual_seed(0)
        np.random.seed(0)
        random.seed(0)
        model = models[role] = factory()
        opts[role] = training.optimizer(torch, model)
        if sum(p.numel() for p in model.parameters()) != 37995777 or training.model_sha(model) != ref["initialization"]["initial_weights_sha256"]:
            raise ValueError("original full Encoder/initial state differs")
    initial = {n: p.detach().clone() for n, p in models["baseline"].named_parameters()} if strict else None
    order = list(range(1600))
    random.Random(0).shuffle(order)
    known_shapes = json.loads((ROOT / "NATIVE_BASELINE_SHAPES.json").read_bytes())
    residency(args.output, "initialized")
    with (args.output / "steps.jsonl").open("x") as log:
        for step in range(1, planned + 1):
            if time.monotonic() >= args.deadline:
                raise TimeoutError("shared stop-new-update deadline")
            ids = order[(step-1)*64:step*64]
            mask = torch.rand(64, 208) < .5
            frames = [train["frame_ids"][i] for i in ids]
            mask_sha = hashlib.sha256(mask.numpy().tobytes()).hexdigest()
            if step <= 5:
                profile_contract.check_step_identity(step, ids, profile_contract.identity(frames), mask_sha, ref)
            pinned = epoch["steps"][step-1]
            if (ids != pinned["frame_indices"] or profile_contract.identity(frames) != pinned["frame_ids_sha256"]
                    or mask_sha != pinned["mask_sha256"]):
                raise ValueError("fixed frame/mask order changed")
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
                release = barrier(args, step) if not strict else None
                if time.monotonic() >= args.deadline:
                    raise TimeoutError("deadline before update")
                begin = time.monotonic_ns()
                try:
                    loss = losses[role] = training.train_step(torch, model, opts[role], values[role], mask)
                finally:
                    for handle in handles:
                        handle.remove()
                end = time.monotonic_ns()
                rss_after = memory_metrics.rss()
                training.validate_update(torch, model, opts[role], values[role], step)
                if runtime["kml_gemm_calls"] - before != 149 or shapes != known_shapes:
                    result["bad_native"] = dict(step=step, role=role, shapes=dict(shapes), logical=runtime["kml_gemm_calls"]-before)
                    raise ValueError("original native SGEMM trace differs")
                for name, item in loss.items():
                    if step <= 5:
                        accepted.compare(torch, f"{role}.{step}.baseline_loss.{name}",
                                         torch.tensor(ref["steps"][step-1]["losses"][name], dtype=torch.float32),
                                         item, "tensor", result["metrics"])
                    elif not torch.isfinite(item):
                        raise ValueError("nonfinite epoch loss")
                cpu36_guard.checkpoint(guard, f"after_{role}_{step}", torch)
                rows.append(dict(role=role, step=step, batch_size=64, frame_indices=ids, frame_ids=frames,
                                 mask_sha256=mask_sha, losses={k: v.item() for k,v in loss.items()},
                                 start_ns=begin, end_ns=end, release_ns=release, step_seconds=(end-begin)/1e9,
                                 rss_before=rss_before, rss_after=rss_after, native_sgemm_calls=sum(shapes.values()),
                                 native_shapes=dict(shapes), sampled=not strict and step >= 6))
            if strict:
                for key in captures["baseline"]:
                    accepted.compare(torch, f"{step}.output.{key}", captures["baseline"][key], captures["control"][key], "tensor", result["metrics"])
                for key in losses["baseline"]:
                    accepted.compare(torch, f"{step}.loss.{key}", losses["baseline"][key], losses["control"][key], "tensor", result["metrics"])
                for i in (0,1):
                    accepted.compare(torch, f"{step}.input_grad.{i}", values["baseline"][i].grad, values["control"][i].grad, "tensor", result["metrics"])
                compare_models(torch, accepted, models["baseline"], models["control"],
                               [opts[role] for role in roles], initial, result["metrics"], f"{step}.")
            for row in rows:
                log.write(json.dumps(row) + "\n")
            log.flush()
            ledger.confirm(step)
            result["completed_updates"] = step
    if not strict:
        barrier(args, 26)
        residency(args.output, "observe_end")
        model, opt = models["baseline"], opts["baseline"]
        progress = dict(epoch_order=order, cursor=1600, optimizer_updates=25, planned_updates=25, epoch_completed=True)
        identity = dict(data=metadata["identity"], baseline_sha256=BASELINE, node=guard["receipt"]["node"])
        checkpoint = training.save_checkpoint(torch, args.output / "checkpoints/final.pt", model, opt, identity, progress, normalization)
        result["checkpoint"] = checkpoint
        ledger.value["recovery_probe"] = dict(status="POSSIBLY_USED_IN_RECOVERY_PROBE", frame_ids=train["frame_ids"][:2])
        ledger.save()
        result["recovery"] = training.verify_restore(torch, checkpoint, model, opt, factory, identity, progress, normalization,
                                                      training.batch(torch, train, [0,1], angles), accepted.compare)
        ledger.value["recovery_probe"]["status"] = "RECOVERY_PROBE_CONFIRMED_NO_UPDATE"
        ledger.save()
    data.load_descriptor(args.descriptor, args.descriptor_sha)
    result["final_model_sha256"] = training.model_sha(models["baseline"])
    finish_backend(runtime, expected)
    runtime_check(runtime)
    cpu36_guard.checkpoint(guard, "publish", torch)
    result["status"] = "PASS_STRICT_ENCODER5" if strict else "PASS_BASELINE25"


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", choices=("strict", "perf"), required=True)
    for flag in ("descriptor", "allocation", "phase-root", "output"):
        parser.add_argument("--" + flag, type=Path, required=True)
    parser.add_argument("--descriptor-sha", required=True)
    parser.add_argument("--deadline", required=True, type=float)
    args = parser.parse_args()
    args.output.mkdir(exist_ok=False)
    result = dict(status="STARTED", job_id=os.environ["CCS_JOB_ID"], host=os.uname().nodename,
                  phase=args.phase, pid=os.getpid(), started_ns=time.monotonic_ns(), metrics=[], completed_updates=0)
    try:
        run(args, result)
        code = 0
    except Exception as exc:
        result.update(status="FAIL_STOP", error=repr(exc), traceback=traceback.format_exc())
        code = 2
    result["finished_ns"] = time.monotonic_ns()
    write(args.output / "result.json", result)
    raise SystemExit(code)
