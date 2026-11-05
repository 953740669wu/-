"""Freeze local S00 evidence without importing the pipeline or writing outside S00."""
import ast
import datetime
import difflib
import hashlib
import importlib.util
import json
from pathlib import Path
import platform
import shutil
import subprocess
import sys

WORK = Path(__file__).resolve().parent
ROOT = WORK.parents[3]


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


files = ['s1_prepare.py', 's2_mesh.py', 's3_forward.py', 's4_models.py', 'kml_ops.py', 's6_corpus.py',
         'README.md', 'c2/STAGE4_HANDOVER.md', 'c2/STAGE4_C2_PLAN.md', 'c2/C2_OPTIMIZATION_REPORT.md',
         'c2/PRODUCTION_C2.md', 'c2/prod_setup.sh', 'c2/prod_tasks.sh']
files += ['c2/opt/' + name for name in [
    'run_node16.sh', 'hbm_alloc.c', 'kml_sgemm_shim.c', 'run_hbm_ab.sh', 'run_hbm_fix.sh',
    'run_kml_shim.sh', 'run_bench_s4.sh', 'run_mem_probe.sh', 'check_linear.py', 'check_attn.py',
    'check_kconv.py', 's4_models_gpu_orig.py']]
rows = []
for relative in files:
    source = ROOT / relative
    dest = WORK / 'baseline' / relative
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and dest.read_bytes() != source.read_bytes():
        raise RuntimeError('Refusing to replace a different frozen copy: ' + str(dest))
    if not dest.exists():
        shutil.copyfile(source, dest)
    rows.append(dict(source=relative, copy=dest.relative_to(WORK).as_posix(),
                     bytes=source.stat().st_size, sha256=hashlib.sha256(source.read_bytes()).hexdigest()))
write_json(WORK / 'evidence/baseline_manifest.json', rows)
(WORK / 'evidence/source_sha256.txt').write_text(''.join(
    r['sha256'] + '  ' + r['source'] + '\n' for r in rows), encoding='utf-8')
(WORK / 'evidence/baseline_sha256.txt').write_text(''.join(
    r['sha256'] + '  ' + r['copy'] + '\n' for r in rows), encoding='utf-8')

# Only path substitution; retain all legacy synchronization and summary behavior for S01.
original = (ROOT / 'c2/opt/run_node16.sh').read_text(encoding='utf-8')
isolated = original.replace('H=/home/share/songzhenlong/eitfm; O=$H/opt/s4;',
    'H=/home/share/songzhenlong/eitfm; S00_RUN=${S00_RUN:?set an absolute unique S00 run directory}; '
    'O=$S00_RUN/output; S00_CODE=$S00_RUN/baseline; S00_LIB=$S00_RUN/lib;')
isolated = isolated.replace('$H/opt/code', '$S00_CODE')
isolated = isolated.replace('$H/sw/kml_shim', '$S00_LIB').replace('$H/sw/hbm_alloc', '$S00_LIB')
(WORK / 'candidate').mkdir(exist_ok=True)
(WORK / 'candidate/run_node16_isolated.sh').write_text(isolated, encoding='utf-8', newline='\n')
(WORK / 'candidate/launcher_paths.diff').write_text(''.join(difflib.unified_diff(
    original.splitlines(True), isolated.splitlines(True),
    fromfile='baseline/c2/opt/run_node16.sh', tofile='candidate/run_node16_isolated.sh')), encoding='utf-8')

common = dict(DEVICE='cpu', AMP='fp32', CHANNELS_LAST='0', COMPILE='0', MKLDNN='1', KML_CONV='0',
              KML_LINEAR='1', LINEAR_DTYPE='fp32', CKPT='0', SAMPLING='0', GN='0', REPS='5',
              ROUNDS='3', SKIP_BUSY='1', BELTS='16_adjacent,32_skip4', PARTS='pre,dec',
              HBM_MB='3800', HBM_MIN_KB='256', OMP_PLACES='cores', OMP_PROC_BIND='close')
configs = {}
for name, batch, hbm, policy in [('DDR_B32_MEMBIND', '32', '0', 'membind'),
                                 ('HBM_B32_MEMBIND', '32', '1', 'membind'),
                                 ('DDR_B64_PREFERRED', '64', '0', 'preferred')]:
    configs[name] = dict(env=dict(common, BATCH=batch, HBM=hbm, MEMPOL=policy),
        domains_sequence=[1, 4, 16], cases=['s0322p0', 's0322p1'],
        gradient_accumulation=1, independent_models=True, distributed_training=False,
        global_batch=None, warmup='2 pre + 2 decoder updates per belt, even when PARTS filters timing',
        seed=0, status='PREPARED_NOT_RUN')
write_json(WORK / 'baseline_configs.json', configs)

tree = ast.parse((ROOT / 's6_corpus.py').read_text(encoding='utf-8'))
node = next(n.value for n in tree.body if isinstance(n, ast.Assign)
            and any(isinstance(t, ast.Name) and t.id == 'CFG' for t in n.targets))
cfg = eval(compile(ast.Expression(node), 'CFG_source_literal', 'eval'), {'__builtins__': {}, 'dict': dict})
code_hash = hashlib.sha1((ROOT / 's6_corpus.py').read_bytes()).hexdigest()[:10]
cfg_hash = hashlib.sha1(json.dumps(cfg, sort_keys=True).encode()).hexdigest()[:10]
write_json(WORK / 'evidence/corpus_identity.json', dict(
    method='AST evaluation of the CFG literal only, no imports or CFG_OVERRIDE applied',
    code_hash=code_hash, expected_code_hash='d8b2be8d1f', code_match=code_hash == 'd8b2be8d1f',
    config_hash=cfg_hash, expected_config_hash='b1049eac1a', config_match=cfg_hash == 'b1049eac1a',
    code_hash_scope='s6_corpus.py bytes ONLY; not an aggregate of stages 1-3', config=cfg,
    actual_manifest='NOT_PRESENT_LOCALLY', subject_split='NOT_PRESENT_LOCALLY'))

commands = [
    ['ssh', '-G', 'hpc-vpn'],
    ['ssh', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=12', '-o', 'ConnectionAttempts=1',
     'hpc-vpn', 'printf S00_READ_ONLY_CONNECTION_OK'],
    [r'C:\Program Files\Git\bin\bash.exe', '--version']]
observations = []
for command in commands:
    result = subprocess.run(command, capture_output=True, timeout=25)
    stdout = result.stdout.decode('mbcs', errors='replace')
    if command[1:2] == ['-G']:
        stdout = '\n'.join(line for line in stdout.splitlines() if line.startswith(
            ('hostname ', 'user ', 'port ', 'proxyjump ', 'connecttimeout ', 'batchmode ')))
    observations.append(dict(command=command, exit_code=result.returncode, stdout=stdout,
                             stderr=result.stderr.decode('mbcs', errors='replace')))
write_json(WORK / 'evidence/environment.json', dict(
    captured_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(), host=platform.node(),
    platform=platform.platform(), architecture=platform.machine(), python=sys.executable,
    python_version=sys.version, torch_present=importlib.util.find_spec('torch') is not None,
    numpy_present=importlib.util.find_spec('numpy') is not None, observations=observations,
    remote_status='NOT_VERIFIED_CONNECTION_FAILED', submitted_jobs=0, node_hours=0))
print(json.dumps(dict(frozen_files=len(rows), corpus_code_hash=code_hash, corpus_config_hash=cfg_hash,
                      remote_exit=observations[1]['exit_code']), indent=2))
