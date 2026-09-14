import json
from pathlib import Path
import shutil


root = Path(
    "/home/jovyan/shares/SR006.nfs2/xandi281/moe-revision-20260911/"
    "civil-gepa-v2-user-only-v2/runs"
)
rows = []
for run in sorted(path for path in root.iterdir() if path.is_dir()):
    groups = {}
    total = 0
    for path in run.rglob("*"):
        if not path.is_file():
            continue
        size = path.stat().st_size
        total += size
        relative = path.relative_to(run)
        group = relative.parts[0]
        groups[group] = groups.get(group, 0) + size
    rows.append({
        "name": run.name,
        "bytes": total,
        "summary": (run / "summary.json").is_file(),
        "hf_verified": (run / "hf_receipt.json").is_file(),
        "groups": dict(sorted(groups.items(), key=lambda item: item[1], reverse=True)[:6]),
    })
print("STORAGE_PROBE=" + json.dumps({
    "free_bytes": shutil.disk_usage(root).free,
    "runs": sorted(rows, key=lambda row: row["bytes"], reverse=True),
}))
