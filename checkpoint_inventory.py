import json
import os
from pathlib import Path


roots = [
    Path("/home/jovyan/shares/SR006.nfs1/hmoe-checkpoints"),
    Path("/home/jovyan/shares/SR006.nfs2/hmoe-checkpoints"),
    Path("/home/jovyan/shares/SR006.nfs3/hmoe-checkpoints"),
    Path("/home/jovyan/shares/SR006.nfs2/xandi281/encrypted-bundles"),
    Path("/home/jovyan/shares/SR006.nfs3/xandi281/hi-moe-megatron/encrypted-bundles"),
    Path("/home/jovyan/shares/SR006.nfs3/tucker-late-growth-20260827/exps"),
    Path("/home/jovyan/shares/SR006.nfs3/progressive-tucker-257m-optimized-20260825/exps"),
]
marker_names = {
    "COMPLETE",
    "latest_checkpointed_iteration.txt",
    "main.pt",
    "model_optim_rng.pt",
    "worker_0.pt",
}
minimum_bytes = 1024 * 1024

for root in roots:
    if not root.is_dir():
        print("ROOT=" + json.dumps({"path": str(root), "present": False}), flush=True)
        continue
    rows = []
    logical_bytes = 0
    physical = {}
    for directory, _, names in os.walk(root):
        for name in names:
            path = Path(directory) / name
            try:
                stat = path.stat()
            except FileNotFoundError:
                continue
            logical_bytes += stat.st_size
            physical[(stat.st_dev, stat.st_ino)] = stat.st_blocks * 512
            if stat.st_size >= minimum_bytes or name in marker_names:
                row = {
                    "path": str(path.relative_to(root)),
                    "bytes": stat.st_size,
                    "blocks_bytes": stat.st_blocks * 512,
                    "nlink": stat.st_nlink,
                    "mtime_ns": stat.st_mtime_ns,
                }
                if name == "latest_checkpointed_iteration.txt":
                    row["tracker"] = path.read_text(errors="replace").strip()[:80]
                rows.append(row)
    print("ROOT=" + json.dumps({
        "path": str(root),
        "present": True,
        "logical_bytes": logical_bytes,
        "unique_blocks_bytes": sum(physical.values()),
        "reported_files": len(rows),
    }, sort_keys=True), flush=True)
    for row in sorted(rows, key=lambda item: item["path"]):
        print("FILE=" + json.dumps(row, sort_keys=True), flush=True)
