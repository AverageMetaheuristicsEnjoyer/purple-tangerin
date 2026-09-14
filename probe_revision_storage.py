import json
from pathlib import Path
import shutil


root = Path("/home/jovyan/shares/SR006.nfs2/xandi281/moe-revision-20260911")
rows = []
for child in sorted(path for path in root.iterdir() if path.is_dir()):
    total = sum(path.stat().st_size for path in child.rglob("*") if path.is_file())
    rows.append({"name": child.name, "bytes": total})
print("REVISION_STORAGE=" + json.dumps({
    "free_bytes": shutil.disk_usage(root).free,
    "directories": sorted(rows, key=lambda row: row["bytes"], reverse=True),
}))
