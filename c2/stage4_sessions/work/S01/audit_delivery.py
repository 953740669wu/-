"""Read-only outside S01; snapshots, diffs and evidence hashes stay inside S01."""
import argparse
import difflib
import hashlib
import importlib.util
import json
from pathlib import Path
import platform
import shutil
import subprocess
import sys
from datetime import datetime, timezone

WORK = Path(__file__).resolve().parent
ROOT = WORK.parents[3]
S00 = WORK.parent / 'S00'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(name, data):
    (WORK / 'evidence' / name).write_text(json.dumps(data, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')


def shared_files():
    originals = json.loads((S00 / 'evidence/source_before.json').read_text())['files']
    paths = [ROOT / row['path'] for row in originals]
    paths += [p for p in S00.rglob('*') if p.is_file()]
    paths += [p for p in (WORK.parent / 'COORDINATION').rglob('*') if p.is_file()]
    return {p.relative_to(ROOT).as_posix(): sha(p) for p in sorted(set(paths))}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('mode', choices=['before', 'after'])
    args = parser.parse_args()
    if args.mode == 'before':
        write('shared_before.json', shared_files())
        frozen = json.loads((S00 / 'evidence/baseline_manifest.json').read_text())
        errors = [row['source'] for row in frozen
                  if sha(S00 / row['copy']) != row['sha256'] or sha(ROOT / row['source']) != row['sha256']]
        index_errors = []
        for line in (S00 / 'ARTIFACT_SHA256.txt').read_text().splitlines():
            digest, relative = line.split(None, 1)
            if sha(S00 / relative.strip()) != digest.lower():
                index_errors.append(relative)
        write('baseline_validation.json', dict(frozen_count=len(frozen), frozen_errors=errors,
                                               s00_artifact_errors=index_errors,
                                               s00_report_sha256=sha(S00 / 'REPORT.md')))
        write('environment.json', dict(captured_utc=datetime.now(timezone.utc).isoformat(),
              host=platform.node(), platform=platform.platform(), python=sys.executable,
              python_version=sys.version, torch_present=importlib.util.find_spec('torch') is not None,
              numpy_present=importlib.util.find_spec('numpy') is not None,
              bash_on_path=shutil.which('bash'), cluster_run=False, submitted_jobs=0, node_hours=0))
        if errors or index_errors:
            raise SystemExit('S00 identity mismatch')
    else:
        before = json.loads((WORK / 'evidence/shared_before.json').read_text())
        changed = [p for p, digest in before.items() if not (ROOT / p).is_file() or sha(ROOT / p) != digest]
        added = sorted(set(shared_files()) - set(before))
        original_rows = json.loads((S00 / 'evidence/source_before.json').read_text())['files']
        baseline_changed = [row['path'] for row in original_rows if sha(ROOT / row['path']) != row['sha256']]
        write('shared_integrity.json', dict(checked=len(before), changed=changed, added=added,
              captured_utc=datetime.now(timezone.utc).isoformat(),
              original_baseline_count=len(original_rows), original_baseline_changed=baseline_changed,
              scope='108 original files plus all S00 and coordination files; no remote data claim'))
        diff = ''
        for original, candidate in [('baseline/s4_models.py', 's4_models.py'),
                                     ('evidence/remote_sources/run_node16_latest.sh', 'run_node16.sh')]:
            diff += ''.join(difflib.unified_diff((S00 / original).read_text().splitlines(True),
                (WORK / 'candidate' / candidate).read_text().splitlines(True),
                fromfile='a/' + candidate, tofile='b/' + candidate))
        for name in ['runner.py', 'legacy_inputs.json']:
            diff += ''.join(difflib.unified_diff([], (WORK / 'candidate' / name).read_text().splitlines(True),
                           fromfile='/dev/null', tofile='b/' + name))
        (WORK / 'candidate/minimal.diff').write_text(diff, encoding='utf-8', newline='\n')
        write('source_hashes.json', {str(p): sha(p) for p in [S00 / 'baseline/s4_models.py',
              S00 / 'baseline/c2/opt/run_node16.sh', S00 / 'evidence/remote_sources/run_node16.sh',
              S00 / 'evidence/remote_sources/run_node16_latest.sh', *sorted((WORK / 'candidate').glob('*'))] if p.is_file()})
        rows = [f'{sha(p)}  {p.relative_to(WORK).as_posix()}' for p in sorted(WORK.rglob('*'))
                if p.is_file() and p != WORK / 'ARTIFACT_SHA256.txt' and '__pycache__' not in p.parts]
        (WORK / 'ARTIFACT_SHA256.txt').write_text('\n'.join(rows) + '\n', encoding='utf-8')
        if changed or baseline_changed:
            raise SystemExit('Shared files changed: ' + str(changed))
    print('audit', args.mode, 'OK')


if __name__ == '__main__':
    main()
