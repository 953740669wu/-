"""Read-only audit of shared inputs; writes evidence only inside this S02 root."""
from datetime import datetime, timezone
import difflib
import hashlib
import importlib.util
import json
from pathlib import Path
import platform
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
PROJECT = ROOT.parents[3]
S00 = ROOT.parent / 'S00'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(name, obj):
    (ROOT / 'evidence' / name).write_text(json.dumps(obj, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')


def parameter_counts():
    # Analytic nn.Linear/Conv2d/GroupNorm/MHA parameter counts for frozen defaults.
    linear = lambda i, o: i * o + o
    conv = lambda i, o, k: i * o * k * k + o
    w, f = 512, 2048
    layer = 4 * w * w + 4 * w + linear(w, f) + linear(f, w) + 4 * w
    enc = linear(1, w) + linear(65, w) + w + 12 * layer + linear(w, 1) + linear(w, 256)
    enc_heads = w + linear(w, 1) + linear(w, 256)
    def block(ci, co, attention):
        n = 2 * ci + conv(ci, co, 3) + linear(512, co) + 2 * co + conv(co, co, 3)
        if ci != co:
            n += conv(ci, co, 1)
        if attention:
            # q/co→co, k&v/ctx512→co, output co→co, and na GroupNorm.
            n += co * co + 2 * 512 * co + 3 * co + linear(co, co) + 2 * co
        return n
    ch = [128, 256, 256, 512]
    dec = 2 * linear(512, 512) + conv(1, 128, 3)
    ci = ch[0]
    for i, co in enumerate(ch):
        dec += block(ci, co, i >= 2)
        ci = co
    dec += block(ci, ci, True)
    for i in reversed(range(4)):
        dec += block(ci + ch[i], ch[i], i >= 2)
        ci = ch[i]
    dec += 2 * ci + conv(ci, 1, 3)
    return {'encoder': enc, 'decoder': dec, 'encoder_inactive_in_dec': enc_heads}


def audit():
    original = json.loads((S00 / 'evidence' / 'source_before.json').read_text('utf-8'))['files']
    sources = []
    for entry in original:
        path = PROJECT / entry['path']
        current = sha(path) if path.is_file() else None
        sources.append(dict(path=entry['path'], expected=entry['sha256'], actual=current,
                            passed=current == entry['sha256']))
    artifacts = []
    for line in (S00 / 'ARTIFACT_SHA256.txt').read_text('utf-8').splitlines():
        expected, name = line.split('  ', 1)
        actual = sha(S00 / name)
        artifacts.append(dict(path=name, expected=expected, actual=actual, passed=actual == expected))
    dependency_paths = [ROOT.parent.parent / 'README.md', ROOT.parent.parent / 'S02_WORKING_SET.md',
                        ROOT.parent.parent / 'REPORT_TEMPLATE.md', ROOT.parent / 'COORDINATION' / 'STATUS.md',
                        ROOT.parent / 'COORDINATION' / 'S00_REVIEW.md', S00 / 'REPORT.md',
                        S00 / 'INPUT_CONTRACT.md', S00 / 'ARTIFACT_SHA256.txt']
    deps = {str(p.relative_to(PROJECT)).replace('\\', '/'): sha(p) for p in dependency_paths}
    write('source_integrity.json', dict(captured_utc=datetime.now(timezone.utc).isoformat(),
          original_sources=sources, s00_artifacts=artifacts, dependencies=deps,
          passed=all(x['passed'] for x in sources + artifacts)))
    assert all(x['passed'] for x in sources + artifacts), 'shared source/S00 integrity failed'
    print(f'PASS: {len(sources)} original sources and {len(artifacts)} S00 artifacts unchanged')


if __name__ == '__main__':
    (ROOT / 'evidence').mkdir(exist_ok=True)
    if '--final' in sys.argv:
        before = json.loads((ROOT / 'evidence' / 'source_integrity_before.json').read_text('utf-8'))
        audit()
        after = json.loads((ROOT / 'evidence' / 'source_integrity.json').read_text('utf-8'))
        # Coordination may legitimately change concurrently; report that instead
        # of changing its snapshot or treating it as our write.
        write('dependency_changes.json', {k: {'before': v, 'after': after['dependencies'][k]}
              for k, v in before['dependencies'].items() if after['dependencies'][k] != v})
        for path in ROOT.rglob('*.py'):
            compile(path.read_text('utf-8'), str(path), 'exec')
        diff = ''.join(difflib.unified_diff([], (ROOT / 'candidate' / 'training_step.py').read_text('utf-8').splitlines(True),
                                          fromfile='/dev/null', tofile='candidate/training_step.py'))
        (ROOT / 'candidate' / 'training_step.diff').write_text(diff, encoding='utf-8')
        lines = [sha(p) + '  ' + p.relative_to(ROOT).as_posix() for p in sorted(ROOT.rglob('*'))
                 if p.is_file() and p.name != 'ARTIFACT_SHA256.txt' and '__pycache__' not in p.parts]
        (ROOT / 'ARTIFACT_SHA256.txt').write_text('\n'.join(lines) + '\n', encoding='utf-8')
        print(f'PASS: Python syntax and {len(lines)} artifact hashes; diff regenerated')
        sys.exit(0)
    audit()
    (ROOT / 'evidence' / 'source_integrity_before.json').write_bytes((ROOT / 'evidence' / 'source_integrity.json').read_bytes())
    (ROOT / 'baseline').mkdir(exist_ok=True)
    copies = []
    for name in ('s4_models.py', 'kml_ops.py'):
        source = S00 / 'baseline' / name
        target = ROOT / 'baseline' / name
        target.write_bytes(source.read_bytes())
        copies.append(dict(source=str(source), copy=str(target), sha256=sha(target)))
    write('baseline_manifest.json', copies)
    interpreters = [Path(sys.executable)] + [Path(f'E:/Codex/home/cache/{name}-speed-venv/Scripts/python.exe')
                                           for name in ('phase2', 'phase3', 'phase4')]
    probes = []
    code = "import sys,importlib.util,json; print(json.dumps({'python':sys.executable,'version':sys.version,'torch':str(importlib.util.find_spec('torch')),'numpy':str(importlib.util.find_spec('numpy'))}))"
    for exe in interpreters:
        r = subprocess.run([str(exe), '-I', '-B', '-c', code], capture_output=True, text=True, timeout=30)
        probes.append(dict(executable=str(exe), exit_code=r.returncode, stdout=r.stdout, stderr=r.stderr))
    write('environment.json', dict(captured_utc=datetime.now(timezone.utc).isoformat(), host=platform.node(),
          platform=platform.platform(), machine=platform.machine(), probes=probes,
          torch_available_here=importlib.util.find_spec('torch') is not None,
          installation_performed=False, network_attempts=0, jobs_submitted=0, node_hours=0))
    counts = parameter_counts()
    E, U, inactive = counts['encoder'], counts['decoder'], counts['encoder_inactive_in_dec']
    static = dict(status='ANALYTIC_LOGICAL_BYTES_NOT_PEAK_OR_RESIDENCY', parameters=counts,
                  fp32_weights_bytes=4 * (E + U), both_phase_adam_moments_bytes=8 * (E + U),
                  fresh_pre_state_bytes=8 * E, fresh_dec_state_bytes=8 * (E + U - inactive),
                  pre_gradient_bytes=4 * E, dec_gradient_bytes=4 * (E + U - inactive), shapes=[])
    for M in (208, 928):
        for B in (16, 32, 64):
            static['shapes'].append(dict(B=B, M=M, encoder_h_bytes=4 * B * M * 512,
                encoder_ff_hidden_bytes=4 * B * M * 2048,
                one_attention_score_if_materialized_bytes=4 * B * 8 * M * M,
                unet_first_feature_bytes=4 * B * 128 * 64 * 64,
                full_effective_batch_v_y0_noise_t_mask_bytes=4 * 64 * M + 8 * 64 * 4096 + 8 * 64 + 64 * M))
    write('static_memory.json', static)
    print('Prepared byte-identical local model copies, environment probes and analytic memory inventory.')
