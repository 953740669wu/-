"""Run the new compiled-C cases; no source-pattern matching or real HBM."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

from cases import cases


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("executable", type=Path)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--version", choices=("previous", "candidate"), required=True)
    parser.add_argument("--json", type=Path, required=True)
    args = parser.parse_args()
    records = []
    for case in cases():
        command = [str(args.executable.resolve())] + case["args"]
        try:
            run = subprocess.run(command, capture_output=True, text=True, timeout=10)
            success = run.returncode == 0 and "RESULT PASS\n" in run.stdout
            expected_failure = args.version == "previous" and case["previous_failure"]
            if expected_failure:
                # Infrastructure aborts/timeouts are never evidence of a defect.
                accepted = run.returncode == 1 and (
                    "CHECK_FAIL " in run.stderr or
                    (case["sanitizer_failure"] and "runtime error:" in run.stderr))
            else:
                accepted = success
            row = dict(case=case["name"], command=command, passed=success,
                       expected_failure=expected_failure, expectation_met=accepted,
                       exitcode=run.returncode, stdout=run.stdout, stderr=run.stderr)
        except subprocess.TimeoutExpired as exc:
            row = dict(case=case["name"], expectation_met=False, timeout=True,
                       stdout=str(exc.stdout), stderr=str(exc.stderr))
        records.append(row)
        print(f"{'OK' if row['expectation_met'] else 'FAIL'} {case['name']}")
    summary = dict(scope="ACTUAL_INCLUDED_C_WITH_OS_AND_FAILURE_SUBSTITUTES",
                   version=args.version, source=str(args.source.resolve()),
                   source_sha256=hashlib.sha256(args.source.read_bytes()).hexdigest(),
                   executable_sha256=hashlib.sha256(args.executable.read_bytes()).hexdigest(),
                   real_hbm=False, real_kernel_policy=False,
                   cases=records, expectations_met=sum(r["expectation_met"] for r in records))
    args.json.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return 0 if all(row["expectation_met"] for row in records) else 1


if __name__ == "__main__":
    sys.exit(main())
