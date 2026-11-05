# gmsh on the C2 cluster: build, accuracy, throughput (2026-11-01)

## Build
- gmsh 4.15.1, the same version as amax's anaconda gmsh. Source: GitHub mirror `live-clones/gmsh`, tag `gmsh_4_15_1`, sha256 `48b89d5a…352093a`. gmsh.info and gitlab.onelab.info failed TLS from the PC and timed out from amax.
- Built by `build_gmsh.sh` (job 2001977) on cn21338.
  - Compilers: gcc 10.3.1, plus the relocated login-node g++ in `sw/gxx`.
  - Options: OpenMP, HXT and Netgen on; OCC, FLTK, BLAS/LAPACK, MPI, PETSc and MMG off.
  - Installed in `sw/gmsh`; the Python API is in `sw/gmsh/lib64`, recorded in `sw/gmsh_pylib.txt`.
- Mesher: `s2_mesh.py` with `VOLUME_ONLY=1`.
  - It meshes the per-case `body_base.stl` made on amax (8.6 MB, 3.9 MB gzipped).
  - Subdivision is linear and done in numpy. It reproduces amax's pyvista surface exactly on s0322: 344,026 points, 688,048 triangles, area and volume equal, closed.
  - It needs no pyvista, scikit-image or scipy.

## s0322 placement 0 (level D, belt plane 0, 0.086089077, 0.996287444, d 0.173619534)

| run | threads | nodes | tets | volume (L) | min tet (m³) | gmsh volume step (s) |
|---|---|---|---|---|---|---|
| amax (smoke run) | 4 | 598,931 | 2,426,521 | 19.468423 | 1.59e-12 | 209 |
| amax | 1 | 599,223 | 2,428,153 | 19.468423 | 1.19e-12 | 674 (tOptimize 655) |
| C2 | 1 | 599,223 | 2,428,166 | 19.468423 | 1.70e-12 | 933 (tOptimize 906) |
| C2 | 4 / 16 / 32 | 598,992 / 599,132 / 599,040 | ~2.427 M | 19.468423 | 1.2–1.6e-12 | 978 / 1,034 / 1,099 |

- **Single-threaded meshing is deterministic.**
  - On C2, three separate 1-thread runs (alone, and inside the 8- and 16-way concurrent sets) gave byte-identical `mesh.npz` (md5 `3736eb73…`).
  - Across hosts, the 1-thread meshes have the same node count; tet counts differ by 13 of 2.43 M, from different compiler and floating-point builds.
  - Multi-threaded HXT is not deterministic: node counts vary by about 0.03% between thread counts.
- **Threads do not help on C2.** The optimisation stage (`tOptimize`) takes about 97% of the time and does not speed up with threads in this build. On amax, 4 threads gave a 3.2× speed-up.
- **Per core**, C2 is 1.39× slower than amax (933 s against 674 s single-threaded).

## Concurrency (one 32-core NUMA-packed allocation, one pinned core per mesh)

| concurrent meshes | allocation wall (s) | per-mesh time (s) | effective s / mesh |
|---|---|---|---|
| 1 | 937 | 937 | 937 |
| 8 | 991 | 938–977 | 124 |
| 16 | 987 | 943–972 | 62 |

- Scaling is close to linear: running 16 meshes at once costs only about 5% per mesh.
- Each mesh peaks at 1.9 GB RSS. A 64 GB allocation holds about 30 meshes, and one 32 GB NUMA domain about 14–16.

## Recommendation
- Mesh on C2 with `GMSH_THREADS=1`, many meshes per allocation. Use 16 per 32-core, 64 GB allocation, or 32 per allocation with about 70 GB.
  - That is about 30–60 s of allocation time per mesh, and it scales with the number of allocations.
  - The alternatives are 209 s per mesh on shared amax (4 threads), or about 30 s per mesh of serial transfer over the 1 MB/s link.
  - Only `prep.npz` plus `body_base.stl` cross the link: about 4.5 MB gzipped per case, instead of 29 MB per placement.
- Use 1 thread on amax too, for production meshes. Meshes then depend only on (case, placement), which the plan's determinism rule needs. The pilot's 4-thread meshes are valid level-D meshes, but they are not bit-reproducible.
- **Still open:** confirm on C2 that the forward results on C2 meshes match amax-mesh results within the level-D tolerance (2% / 1%). This waits for the PETSc/CHOLMOD build owned by the main session.
