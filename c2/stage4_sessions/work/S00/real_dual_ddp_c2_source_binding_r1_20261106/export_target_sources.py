"""One bounded installed-file export. Standard library only; never import Torch."""
import time
START = time.monotonic()
DEADLINE = START + 60
import base64
import datetime
import hashlib
import importlib.machinery
import json
import os
from pathlib import Path
import signal
import socket
import struct
import sys

ROOT = Path('/home/share/songzhenlong/eitfm/sw/torch_kml/torch')
PYTHON = Path('/home/share/dengqingtian/opt/stage4_sessions/S00/ENV_20261104T130730Z_R4/venv/bin/python3')
TARGETS = ['_tensor.py', 'nn/modules/linear.py', 'nn/modules/activation.py',
           'nn/modules/transformer.py', 'nn/functional.py', 'version.py']
ANCHORS = {str(ROOT/'__init__.py'): '9801e75447c7f585545f989f8a21940b60e0c4cc888effb2f08e739664b4b904',
           str(PYTHON): '41ed40932add50d0a953bbe92ba15a9e60a2ee476ce68cfd4798cf814647c383'}
TEXT_MAX = 2097152
TEXT_BYTES = 0
STABLE = {}
CURRENT = None
COUNTS = dict(anchor_reads=0, text_files_exported=0, core_files_hashed=0,
              identity_bytes_hashed=0, text_bytes_exported=0, directory_enumerations=0)


def stop(*_):
    raise TimeoutError('one common60s read/hash/export deadline')


def check():
    if time.monotonic() >= DEADLINE: stop()


def emit(value):
    check()
    print(json.dumps(value, sort_keys=True), flush=True)
    check()


def signature(st):
    return (st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns, st.st_ctime_ns)


def elf_identity(stream, size):
    """Read existing ELF64/AArch64 header and GNU PT_NOTE build IDs, not code."""
    check()
    stream.seek(0)
    head = stream.read(64)
    if len(head) != 64 or head[:6] != b'\x7fELF\x02\x01':
        raise ValueError('target core is not ELF64 little-endian')
    header = struct.unpack('<HHIQQQIHHHHHH', head[16:])
    if header[1] != 183: raise ValueError('target core is not AArch64')
    phoff, phsize, count = header[4], header[8], header[9]
    if phsize < 56 or count > 4096 or phoff + phsize*count > size:
        raise ValueError('invalid ELF program headers')
    ids = []
    for index in range(count):
        check()
        stream.seek(phoff + phsize*index)
        row = struct.unpack('<IIQQQQQQ', stream.read(56))
        if row[0] != 4: continue
        cursor, end = row[2], row[2] + row[5]
        if end > size: raise ValueError('ELF note outside file')
        while cursor + 12 <= end:
            check()
            stream.seek(cursor)
            namesz, descsz, kind = struct.unpack('<III', stream.read(12))
            desc = cursor + 12 + ((namesz+3)//4)*4
            following = desc + ((descsz+3)//4)*4
            if following > end: raise ValueError('invalid ELF note bounds')
            if namesz == 4 and kind == 3:
                stream.seek(cursor+12)
                if stream.read(4) == b'GNU\x00':
                    if not 0 < descsz <= 128: raise ValueError('invalid GNU build ID length')
                    stream.seek(desc)
                    ids.append(stream.read(descsz).hex())
            cursor = following
    return dict(format='ELF64', endian='little', machine='AArch64', machine_id=header[1],
                elf_type=header[0], flags=header[6], gnu_build_ids=ids,
                build_id_status='PRESENT' if ids else 'NOT_PRESENT_IN_EXISTING_PT_NOTE')


def read_file(path, kind, expected=None):
    global CURRENT, TEXT_BYTES
    check()
    real = path.resolve(strict=True)
    before = path.stat()
    if not path.is_file(): raise ValueError('not a regular installed file: '+str(path))
    if kind == 'source' and TEXT_BYTES + before.st_size > TEXT_MAX:
        raise ValueError('six source texts exceed2MiB before reading: '+str(path))
    CURRENT = dict(path=str(path), realpath=str(real), expected_bytes=before.st_size, bytes_hashed=0, kind=kind)
    emit(dict(event='file_begin', **CURRENT))
    digest = hashlib.sha256()
    chunks = []
    with path.open('rb') as stream:
        while True:
            check()
            chunk = stream.read(min(1024*1024, TEXT_MAX-TEXT_BYTES-CURRENT['bytes_hashed']+1)
                                if kind == 'source' else 1024*1024)
            if not chunk: break
            digest.update(chunk)
            CURRENT['bytes_hashed'] += len(chunk)
            if kind == 'source':
                if TEXT_BYTES + CURRENT['bytes_hashed'] > TEXT_MAX: raise ValueError('source byte cap exceeded')
                chunks.append(chunk)
            else: COUNTS['identity_bytes_hashed'] += len(chunk)
            check()
        elf = elf_identity(stream, before.st_size) if kind == 'core' or path == PYTHON else None
        after_fd = os.fstat(stream.fileno())
    after = path.stat()
    if (signature(before) != signature(after_fd) or signature(before) != signature(after)
            or path.resolve(strict=True) != real or CURRENT['bytes_hashed'] != after.st_size):
        raise ValueError('installed file identity changed while reading: '+str(path))
    actual = digest.hexdigest()
    if expected is not None and actual != expected: raise ValueError('frozen identity drift: '+str(path))
    record = dict(path=str(path), realpath=str(real), bytes=after.st_size, sha256=actual,
                  mtime_ns=after.st_mtime_ns, ctime_ns=after.st_ctime_ns, device=after.st_dev, inode=after.st_ino,
                  kind=kind, elf=elf, expected_sha256=expected, anchor_match=actual==expected if expected else None)
    STABLE[str(path)] = (signature(after), str(real))
    if kind == 'source':
        raw = b''.join(chunks)
        raw.decode('utf-8')
        TEXT_BYTES += len(raw)
        record.update(relative_path=path.relative_to(ROOT).as_posix(), content_base64=base64.b64encode(raw).decode())
        COUNTS['text_files_exported'] += 1
        COUNTS['text_bytes_exported'] = TEXT_BYTES
    elif kind == 'core': COUNTS['core_files_hashed'] += 1
    else: COUNTS['anchor_reads'] += 1
    emit(dict(event='file_complete', record=record))
    CURRENT = None


def main():
    signal.signal(signal.SIGALRM, stop)
    signal.signal(signal.SIGTERM, stop)
    signal.setitimer(signal.ITIMER_REAL, max(.001, DEADLINE-time.monotonic()))
    try:
        emit(dict(event='begin', utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
             host=socket.gethostname(), machine=os.uname().machine, package_root=str(ROOT),
             executable=sys.executable, executable_realpath=str(Path(sys.executable).resolve()),
             python_version=sys.version, sys_path=sys.path, no_site=sys.flags.no_site,
             PYTHONPATH=os.environ.get('PYTHONPATH'), common_seconds=60, text_bytes_max=TEXT_MAX,
             torch_imported=any(name=='torch' or name.startswith('torch.') for name in sys.modules)))
        if (Path(sys.executable) != PYTHON or sys.version_info[:3] != (3,9,9)
                or os.uname().machine != 'aarch64' or not sys.flags.no_site):
            raise ValueError('pinned R4 interpreter/architecture/no-site mismatch')
        spec = importlib.machinery.PathFinder.find_spec('torch', [str(ROOT.parent)])
        if spec is None or Path(spec.origin).resolve() != (ROOT/'__init__.py').resolve():
            raise ValueError('package-root/interpreter resolution mismatch')
        emit(dict(event='package_association', origin=spec.origin,
                  search_locations=list(spec.submodule_search_locations), framework_executed=False,
                  method='stdlib PathFinder metadata only; frozen R4 PYTHONPATH, -S, no Torch import'))
        for name, digest in ANCHORS.items(): read_file(Path(name), 'anchor', digest)
        for name in TARGETS: read_file(ROOT/name, 'source')
        # Exactly the two authorized nonrecursive directory inventories.
        entries = sorted(ROOT.iterdir())
        COUNTS['directory_enumerations'] += 1
        candidates = [p for p in entries if p.name.startswith('_C') and p.name.endswith('.so')]
        extension = importlib.machinery.PathFinder.find_spec('torch._C', [str(ROOT)])
        if extension is None or Path(extension.origin) not in candidates:
            raise ValueError('cannot resolve actual installed _C extension without import')
        extensions = [Path(extension.origin)]
        lib = ROOT/'lib'
        libraries = sorted(lib.iterdir())
        COUNTS['directory_enumerations'] += 1
        libraries = [p for p in libraries if (p.name.startswith('libtorch') or p.name.startswith('libc10'))
                     and (p.name.endswith('.so') or '.so.' in p.name)]
        required = {'libtorch_cpu.so', 'libtorch_python.so', 'libc10.so'}
        if not required <= {p.name for p in libraries}: raise FileNotFoundError('missing CPU/autograd core library')
        emit(dict(event='direct_core_inventory', extension=[str(p) for p in extensions],
                  extension_candidates=[str(p) for p in candidates],
                  core_libraries=[str(p) for p in libraries], recursive=False))
        for path in extensions+libraries: read_file(path, 'core')
        for name, digest in ANCHORS.items(): read_file(Path(name), 'anchor', digest)
        for name, (stat_identity, real) in STABLE.items():
            check()
            path = Path(name)
            if signature(path.stat()) != stat_identity or str(path.resolve(strict=True)) != real:
                raise ValueError('installed file changed before packet completion: '+name)
        if any(name=='torch' or name.startswith('torch.') for name in sys.modules):
            raise ValueError('unexpected Torch import')
        emit(dict(event='complete', status='SOURCE_PACKET_COMPLETE_FOR_REVIEW', elapsed_seconds=time.monotonic()-START,
                  counts=COUNTS, text_sources=TARGETS, final_stat_recheck_files=len(STABLE),
                  frozen_anchors_checked_twice=True, binary_payload_bytes_exported=0, torch_imports=0))
        return 0
    except BaseException as exc:
        signal.setitimer(signal.ITIMER_REAL, 0)
        print(json.dumps(dict(event='stopped', status='BLOCKED_SOURCE_PACKET', error=repr(exc),
              current_partial=CURRENT, counts=COUNTS, elapsed_seconds=time.monotonic()-START,
              binary_payload_bytes_exported=0)), flush=True)
        return 124 if isinstance(exc, TimeoutError) else 1
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)


if __name__ == '__main__': raise SystemExit(main())
