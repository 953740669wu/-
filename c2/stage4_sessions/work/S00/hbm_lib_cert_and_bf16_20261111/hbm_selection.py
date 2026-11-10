"""Select the original S03 allocator before a worker is allowed to launch."""
from pathlib import Path

from prepare import sha

ALLOCATOR_SHA = "89f295754a199dcb6206f8e6217e6cf57651bceed2d364b1a6e4cc83eea6095d"


def select(root, request):
    if request is None:
        path = root / "FROZEN_HBM_ALLOCATOR.so"
    else:
        private = root / "lib"
        path = (private / Path(request)).resolve()
        if private.resolve() != private or private not in path.parents:
            raise ValueError("outside_private_lib")
    if not path.is_file():
        raise ValueError("missing")
    if sha(path) != ALLOCATOR_SHA:
        raise ValueError("sha256")
    return dict(HBM_LIB=request, allocator_origin=path.as_posix(), allocator_sha256=ALLOCATOR_SHA)


def bound_selection(root, binding):
    selected = binding["hbm_selections"]
    expected = {side: select(root, row["HBM_LIB"]) for side, row in selected.items()}
    if selected != expected or set(selected) != {"baseline", "candidate"}:
        raise ValueError("frozen HBM selection differs")
    if binding["allocator_sha256"] != ALLOCATOR_SHA:
        raise ValueError("frozen HBM SHA differs")
    return expected
