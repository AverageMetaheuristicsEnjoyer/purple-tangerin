import json
from pathlib import Path
import shutil


roots = [
    Path("/home/jovyan/shares/SR006.nfs3/xandi281"),
    Path("/home/jovyan/shares/SR006.nfs2/xandi281"),
]
rows = []
for root in roots:
    if not root.is_dir():
        continue
    for output in root.rglob("reasoning_low_4096.jsonl"):
        summary = output.with_name("reasoning_low_4096.summary.json")
        rows.append({
            "path": str(output),
            "rows": sum(1 for _ in output.open()),
            "bytes": output.stat().st_size,
            "mtime": output.stat().st_mtime,
            "summary": summary.is_file(),
        })
print("REASONING_PROGRESS=" + json.dumps({
    "matches": sorted(rows, key=lambda row: row["path"]),
    "free_bytes": {
        str(root): shutil.disk_usage(root).free
        for root in roots
        if root.is_dir()
    },
}))
