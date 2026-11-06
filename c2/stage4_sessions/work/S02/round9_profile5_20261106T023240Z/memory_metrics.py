"""Linux per-process RSS counters; no tensors, sampling threads or snapshots."""
from pathlib import Path


def rss():
    fields = {}
    for line in Path('/proc/self/status').read_text().splitlines():
        key, _, value = line.partition(':')
        if key in ('VmRSS', 'VmHWM', 'HugetlbPages'):
            parts = value.split()
            if len(parts) != 2 or parts[1] != 'kB' or int(parts[0]) < 0:
                raise ValueError('invalid RSS units/value: ' + line)
            fields[key] = int(parts[0]) * 1024
    if set(fields) != {'VmRSS', 'VmHWM', 'HugetlbPages'} or fields['HugetlbPages'] != 0:
        raise ValueError('missing process RSS evidence or unexpected hugetlb allocation')
    return dict(rss_bytes=fields['VmRSS'], peak_rss_bytes=fields['VmHWM'],
                rss_MiB=fields['VmRSS'] / 2**20, peak_rss_MiB=fields['VmHWM'] / 2**20,
                hugetlb_bytes=fields['HugetlbPages'])


def reset_peak():
    try:
        Path('/proc/self/clear_refs').write_text('5\n', encoding='ascii')
    except OSError as exc:
        return dict(available=False, error=repr(exc), method='/proc/self/clear_refs=5')
    return dict(available=True, method='/proc/self/clear_refs=5')
