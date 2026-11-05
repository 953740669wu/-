# HBM feasibility and bandwidth, one process per domain: three 1 GB fp32 arrays either in ordinary (DDR, process
# mempolicy) memory or in 2 MB hugetlb pages bound with mbind(MPOL_BIND) to the domain's HBM node (16 + domain).
# Triad a = b + 2c with torch (OMP threads); reports GB/s counting 3 x 1 GB moved per pass.
# argv: mode (ddr | hbm), domain, passes. Optional SYNC_DIR/SYNC_N barrier before timing.
import ctypes, mmap, os, sys, time, json
import torch

mode, dom, passes = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
GB, n = 1 << 30, (1 << 30) // 4
libc = ctypes.CDLL(None, use_errno=True)
SYS_MBIND = 235  # aarch64


def hbm_tensor():
    m = mmap.mmap(-1, GB, flags=mmap.MAP_PRIVATE | mmap.MAP_ANONYMOUS | 0x40000)  # MAP_HUGETLB
    addr = ctypes.addressof(ctypes.c_char.from_buffer(m))
    mask = (ctypes.c_ulong * 1)(1 << (16 + dom))
    if libc.syscall(SYS_MBIND, ctypes.c_void_p(addr), ctypes.c_ulong(GB), 2, mask, 64, 0) != 0:
        raise OSError(ctypes.get_errno(), 'mbind')
    t = torch.frombuffer(m, dtype=torch.float32, count=n)
    t.fill_(1.0)  # fault in now
    return t, m


if mode == 'hbm':
    keep = [hbm_tensor() for _ in range(3)]
    a, b, c = (t for t, _ in keep)
else:
    a, b, c = (torch.ones(n) for _ in range(3))
node_of = lambda: open(f'/sys/devices/system/node/node{16 + dom}/meminfo').read().split('HugePages_Free:')[1].split()[0]
free_after = node_of()
S, N = os.environ.get('SYNC_DIR'), int(os.environ.get('SYNC_N', '1'))
if S:
    open(f'{S}/{dom}', 'w').close()
    while len(os.listdir(S)) < N:
        time.sleep(0.05)
torch.add(b, c, alpha=2.0, out=a)
t0 = time.time()
for _ in range(passes):
    torch.add(b, c, alpha=2.0, out=a)
dt = time.time() - t0
print(json.dumps({'mode': mode, 'domain': dom, 'GBps': round(3 * passes / dt, 1), 'hbm_hugepages_free_after_alloc': int(free_after),
                  'threads': torch.get_num_threads()}))
