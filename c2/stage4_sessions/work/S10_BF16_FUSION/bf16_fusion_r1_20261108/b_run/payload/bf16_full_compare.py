"""Full Encoder B5 gates use the S04 module metric and category limits."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "fixture/tests"))
from common import metric
from check_alignment import limits


def compare(torch, original, step, name, ref, got, metrics):
    label = f"{step}.{name}"
    if name.endswith(".step") or name.startswith("buffer."):
        original.compare(torch, label, ref, got, "exact", metrics)
        return
    if name.startswith("state."):
        category = name.rsplit(".", 1)[1] + "." + name[6:]
    elif name.startswith("delta."):
        category = "update." + name[6:]
    elif name.startswith("grad."):
        category = "gradient." + name[5:]
    elif name.startswith("input_grad."):
        category = "input_gradient"
    else:
        category = name
    row = metric(label, ref, got, limits(category))
    row["same_dtype"] = ref.dtype == got.dtype
    row["passed"] = row["passed"] and row["same_dtype"]
    metrics.append(row)
