from __future__ import annotations

import json
import shutil
from pathlib import Path


TARGETS = (
    Path("/home/jovyan/shares/SR006.nfs3/progressive-tucker-257m-optimized-20260825/python_user"),
    Path("/home/jovyan/shares/SR006.nfs3/progressive-tucker-257m-optimized-20260825/pip_cache"),
    Path("/home/jovyan/shares/SR006.nfs3/tucker-late-growth-20260827/hf_eval_cache"),
)


def allocated_bytes(path: Path) -> int:
    if not path.exists():
        return 0
    return sum(entry.stat(follow_symlinks=False).st_blocks * 512 for entry in path.rglob("*"))


before_free = shutil.disk_usage(TARGETS[0].parent).free
deleted = []
for target in TARGETS:
    size = allocated_bytes(target)
    if target.exists():
        shutil.rmtree(target)
    deleted.append({"path": str(target), "allocated_bytes": size, "absent_after": not target.exists()})

after_free = shutil.disk_usage(TARGETS[0].parent).free
print(
    "CACHE_CLEANUP="
    + json.dumps(
        {
            "status": "PASS" if all(item["absent_after"] for item in deleted) else "FAIL",
            "deleted": deleted,
            "free_before": before_free,
            "free_after": after_free,
            "free_delta": after_free - before_free,
        },
        sort_keys=True,
    ),
    flush=True,
)
