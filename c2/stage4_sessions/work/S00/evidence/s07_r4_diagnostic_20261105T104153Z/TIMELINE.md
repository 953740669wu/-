# 2041165事件时间线

同一节点cn21338；以supervisor_begin的monotonic_ns为0。时间包含事件写入/刷盘及调度开销，不是纯导入或通信性能。

## rank0

| 相对秒 | 事件 | 关键字段 |
|---:|---|---|
| 0.726124509 | worker_ready | {"pid": 310132, "rank": 0, "job_id": "2041165", "run_id": "normal"} |
| 0.736611929 | checkpoint_begin | {"pid": 310132, "stage": "before_framework"} |
| 0.754296297 | checkpoint_end | {"pid": 310132, "stage": "before_framework"} |
| 0.755904758 | torch_import_begin | {"pid": 310132} |
| 16.383993928 | torch_import_end | {"pid": 310132} |
| 16.385912950 | distributed_import_begin | {"pid": 310132} |
| 16.387361769 | distributed_import_end | {"pid": 310132} |
| 16.388766309 | runtime_metadata_begin | {"pid": 310132} |
| 16.392615994 | library_sha_begin | {"pid": 310132, "library": "/home/share/songzhenlong/eitfm/sw/torch_kml/torch/_C.cpython-39-aarch64-linux-gnu.so"} |
| 16.395494832 | library_sha_end | {"pid": 310132, "library": "/home/share/songzhenlong/eitfm/sw/torch_kml/torch/_C.cpython-39-aarch64-linux-gnu.so"} |
| 16.408834079 | library_sha_begin | {"pid": 310132, "library": "/home/share/songzhenlong/eitfm/sw/torch_kml/torch/lib/libc10.so"} |
| 16.413885312 | library_sha_end | {"pid": 310132, "library": "/home/share/songzhenlong/eitfm/sw/torch_kml/torch/lib/libc10.so"} |
| 16.416034416 | library_sha_begin | {"pid": 310132, "library": "/home/share/songzhenlong/eitfm/sw/torch_kml/torch/lib/libtorch.so"} |
| 16.418674753 | library_sha_end | {"pid": 310132, "library": "/home/share/songzhenlong/eitfm/sw/torch_kml/torch/lib/libtorch.so"} |
| 16.420449274 | library_sha_begin | {"pid": 310132, "library": "/home/share/songzhenlong/eitfm/sw/torch_kml/torch/lib/libtorch_cpu.so"} |

## rank1

| 相对秒 | 事件 | 关键字段 |
|---:|---|---|
| 0.806368185 | worker_ready | {"pid": 310133, "rank": 1, "job_id": "2041165", "run_id": "normal"} |
| 0.810602513 | checkpoint_begin | {"pid": 310133, "stage": "before_framework"} |
| 0.816924636 | checkpoint_end | {"pid": 310133, "stage": "before_framework"} |
| 0.818202054 | torch_import_begin | {"pid": 310133} |
| 8.874563692 | torch_import_end | {"pid": 310133} |
| 8.876594075 | distributed_import_begin | {"pid": 310133} |
| 8.877748873 | distributed_import_end | {"pid": 310133} |
| 8.878718749 | runtime_metadata_begin | {"pid": 310133} |
| 8.882183062 | library_sha_begin | {"pid": 310133, "library": "/home/share/songzhenlong/eitfm/sw/torch_kml/torch/_C.cpython-39-aarch64-linux-gnu.so"} |
| 8.884703689 | library_sha_end | {"pid": 310133, "library": "/home/share/songzhenlong/eitfm/sw/torch_kml/torch/_C.cpython-39-aarch64-linux-gnu.so"} |
| 8.886215569 | library_sha_begin | {"pid": 310133, "library": "/home/share/songzhenlong/eitfm/sw/torch_kml/torch/lib/libc10.so"} |
| 8.891472373 | library_sha_end | {"pid": 310133, "library": "/home/share/songzhenlong/eitfm/sw/torch_kml/torch/lib/libc10.so"} |
| 8.893446106 | library_sha_begin | {"pid": 310133, "library": "/home/share/songzhenlong/eitfm/sw/torch_kml/torch/lib/libtorch.so"} |
| 8.895554610 | library_sha_end | {"pid": 310133, "library": "/home/share/songzhenlong/eitfm/sw/torch_kml/torch/lib/libtorch.so"} |
| 8.896991360 | library_sha_begin | {"pid": 310133, "library": "/home/share/songzhenlong/eitfm/sw/torch_kml/torch/lib/libtorch_cpu.so"} |
| 9.291489525 | library_sha_end | {"pid": 310133, "library": "/home/share/songzhenlong/eitfm/sw/torch_kml/torch/lib/libtorch_cpu.so"} |
| 9.293313767 | library_sha_begin | {"pid": 310133, "library": "/home/share/songzhenlong/eitfm/sw/torch_kml/torch/lib/libtorch_global_deps.so"} |
| 9.295000668 | library_sha_end | {"pid": 310133, "library": "/home/share/songzhenlong/eitfm/sw/torch_kml/torch/lib/libtorch_global_deps.so"} |
| 9.296287097 | library_sha_begin | {"pid": 310133, "library": "/home/share/songzhenlong/eitfm/sw/torch_kml/torch/lib/libtorch_python.so"} |
| 9.335831417 | library_sha_end | {"pid": 310133, "library": "/home/share/songzhenlong/eitfm/sw/torch_kml/torch/lib/libtorch_python.so"} |
| 9.393871239 | runtime_metadata_end | {"pid": 310133} |
| 9.395461549 | checkpoint_begin | {"pid": 310133, "stage": "init_process_group"} |
| 9.400268861 | checkpoint_end | {"pid": 310133, "stage": "init_process_group"} |
| 9.401416219 | init_process_group_begin | {"pid": 310133, "pg_timeout_seconds": 5, "rank": 1, "world_size": 2, "backend": "gloo", "init_method": "file:///home/share/dengqingtian/opt/stage4_sessions/S00/S07_INIT_DIAG_R4_20261105T104153Z/payload/checks_current_job/normal/rendezvous"} |
| 15.924754694 | worker_error | {"pid": 310133, "stage": "init_process_group", "error": "RuntimeError: Wait timeout"} |

## supervisor

| 相对秒 | 事件 | 关键字段 |
|---:|---|---|
| 0.000000000 | supervisor_begin | {"pid": 310130, "deadline_seconds": 30} |
| 0.002975040 | spawn_begin | {"pid": 310130, "rank": 0} |
| 0.052818323 | spawned | {"pid": 310130, "rank": 0, "child_pid": 310132} |
| 0.054840717 | spawn_begin | {"pid": 310130, "rank": 1} |
| 0.109341012 | spawned | {"pid": 310130, "rank": 1, "child_pid": 310133} |
| 16.567949732 | cleanup_begin | {"pid": 310130, "reason": "child_failed", "exit_codes": [null, 1]} |
| 16.569892145 | signal_sent | {"pid": 310130, "child_pid": 310132, "signal": 15} |
| 16.672296420 | child_reaped | {"pid": 310130, "child_pid": 310132, "exit_code": -15} |
| 16.674224303 | child_reaped | {"pid": 310130, "child_pid": 310133, "exit_code": 1} |
| 16.676002744 | supervisor_end | {"pid": 310130, "reason": "child_failed", "exit_codes": [-15, 1], "all_reaped": true} |

