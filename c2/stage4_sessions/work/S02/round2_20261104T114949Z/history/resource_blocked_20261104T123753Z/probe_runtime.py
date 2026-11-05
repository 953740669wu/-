"""Actual torch import/autograd unit checks and meta model count; no model step."""
from datetime import datetime, timezone
import importlib.util
import json
from pathlib import Path
import platform
import sys
import torch
import numpy

ROOT = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('s02_check', ROOT / 'tests' / 'check_equivalence.py')
check = importlib.util.module_from_spec(spec)
spec.loader.exec_module(check)
torch.set_num_threads(4)
unit = check.loss_unit_checks(torch)
definitions = check.model_definitions(torch)
with torch.device('meta'):
    enc, dec = definitions['Encoder'](), definitions['UNet']()
counts = dict(encoder=sum(p.numel() for p in enc.parameters()),
              decoder=sum(p.numel() for p in dec.parameters()))
expected = json.loads((ROOT / 'evidence' / 'static_memory.json').read_text())['parameters']
assert all(counts[k] == expected[k] for k in counts), (counts, expected)
record = dict(captured_utc=datetime.now(timezone.utc).isoformat(), python=sys.executable,
              python_version=sys.version, host=platform.node(), torch=torch.__version__,
              torch_file=torch.__file__, numpy=numpy.__version__, numpy_file=numpy.__file__,
              torch_config=torch.__config__.show(), threads=torch.get_num_threads(),
              interop_threads=torch.get_num_interop_threads(), loss_unit_check=unit,
              actual_full_model_parameter_counts_on_meta=counts, parameter_count_check='PASS',
              model_forward_backward='NOT_RUN_RESOURCE_GATE_PENDING', kml_loaded=False,
              hbm_available=False)
(ROOT / 'evidence' / 'runtime_probe.json').write_text(json.dumps(record, indent=2) + '\n', encoding='utf-8')
print(json.dumps({k: v for k, v in record.items() if k != 'torch_config'}, indent=2))
