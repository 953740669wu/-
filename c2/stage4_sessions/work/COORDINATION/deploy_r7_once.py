"""Run on the C2 login node, beside the original R7 ZIP in a new S00 directory."""
import hashlib
import json
import shutil
import subprocess
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path


ZIP_SHA = "288a74181c36ec87b3953be5cde7e26575e45c219e9f446a21fca0683659119c"
SHIM_SHA = "a52c4da1a87b1a65b11121ecab2b8d0ca3fd2a03a5c92422873592381a92dd73"
BASE = Path("/home/share/dengqingtian/opt/stage4_sessions/S00")
ENV = BASE / "ENV_20261104T130730Z_R4"


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    root = Path(__file__).resolve().parent
    require(sys.platform == "linux", "Run this entry on the C2 login node.")
    require(root.parent == BASE and root.name.startswith("R7_"), "Use a fresh S00/R7_* directory.")
    archive = root / "S01_CPU36_MODEL_R7.zip"
    require(sha(archive) == ZIP_SHA, "Original R7 ZIP SHA mismatch.")
    payload = root / "payload"
    payload.mkdir()  # Refuse reuse, including after a failed submission.
    with zipfile.ZipFile(archive) as bundle:
        bundle.extractall(payload)  # The entire archive was authenticated by its frozen SHA above.
    manifest = json.loads((payload / "SOURCE_MANIFEST.json").read_text())
    checked = {}
    for name, expected in manifest["files"].items():
        path = payload / name
        require(path.stat().st_size == expected["bytes"] and sha(path) == expected["sha256"], name)
        checked[name] = sha(path)
        if path.suffix in (".sh", ".env"):
            require(b"\r" not in path.read_bytes(), "CR bytes: " + name)
            subprocess.run(["bash", "-n", str(path)], check=True)
        elif path.suffix == ".py":
            compile(path.read_bytes(), str(path), "exec")
    (payload / "lib").mkdir()
    shim = ENV / "S01_payload/lib/libkml_sgemm_shim.so"
    require(sha(shim) == SHIM_SHA, "Previously verified shim changed.")
    shutil.copy2(shim, payload / "lib" / shim.name)
    identity = json.loads((payload / "candidate/legacy_inputs.json").read_text())
    for case, expected in identity["cases"].items():
        source = ENV / "S01_payload/output/cases" / case / "frames.npz"
        require(sha(source) == expected, "Previously verified input changed: " + case)
        target = payload / "output/cases" / case / "frames.npz"
        target.parent.mkdir(parents=True)
        shutil.copy2(source, target)
        require(sha(target) == expected, "Copied input mismatch: " + case)
        checked[str(target.relative_to(payload))] = sha(target)
    require(sha(payload / "lib" / shim.name) == SHIM_SHA, "Copied shim mismatch.")
    checked["lib/" + shim.name] = SHIM_SHA
    command = [
        "dsub", "-J", "-q", "q_hpcai", "-R", "cpu=38,mem=24576MB",
        "-RL", "mem=24576MB", "-a", "numa[count=1,distribution=pack]", "-T", "900",
        "--env", "none", "--cwd", str(payload), "-oo", str(root / "job.log"),
        "env", "S01_RUN=" + str(payload), "bash", str(payload / "interfaces/run_s01_startup36.sh"),
    ]
    (root / "pre_submit_checks.json").write_text(json.dumps({
        "captured_utc": datetime.now(timezone.utc).isoformat(),
        "status": "SHA_LF_LINUX_SYNTAX_PASS_NOT_MODEL_ACCEPTANCE",
        "package_sha256": ZIP_SHA, "payload_files": checked, "command": command,
        "actual_compute_cores": 36, "requested_allocation_cores": 38,
        "memory_MB": 24576, "wall_limit_s": 900,
    }, indent=2) + "\n")
    with (root / "submit_once.marker").open("x") as marker:
        marker.write(datetime.now(timezone.utc).isoformat() + "\n")
    result = subprocess.run([
        "bash", "-c", 'set -e; source /etc/profile.d/donaukit_scheduler.sh; exec "$@"',
        "--", *command,
    ], capture_output=True, text=True)
    (root / "submission.json").write_text(json.dumps({
        "returncode": result.returncode, "stdout": result.stdout, "stderr": result.stderr,
    }, indent=2) + "\n")
    print(result.stdout, end="")
    print(result.stderr, end="", file=sys.stderr)
    raise SystemExit(result.returncode)


if __name__ == "__main__":
    main()
