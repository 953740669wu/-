"""Revalidate the same frozen real32 input files without loading arrays."""
import json
from pathlib import Path
import sys

root = Path(__file__).resolve().parent
sys.path.insert(0, str(root/"payload"))
from data_gate import engineering_data as data

binding = json.loads((root/"M23_RUN_BINDING.json").read_bytes())
try:
    meta = data.load_descriptor(root/"ENGINEERING_DESCRIPTOR.json", binding["descriptor_sha256"])
    print(json.dumps(dict(status="FIXED32_CURRENT_SOURCE_SHA_PASS", data_contract="REAL32_ENGINEERING",
                          identity=meta["identity"]), indent=2))
except Exception as exc:
    print(json.dumps(dict(status="SOURCE_CHANGED", error=repr(exc)), indent=2))
    raise
