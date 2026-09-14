import json
from pathlib import Path
import subprocess


for volume in ["SR006.nfs1", "SR006.nfs2", "SR006.nfs3"]:
    root = Path("/home/jovyan/shares") / volume / "xandi281"
    if not root.is_dir():
        continue
    result = subprocess.run(
        ["du", "-x", "-B1", "--max-depth=2", str(root)],
        check=True,
        capture_output=True,
        text=True,
    )
    rows = []
    for line in result.stdout.splitlines():
        size, path = line.split("\t", 1)
        rows.append({"bytes": int(size), "path": path})
    print("OWNED_USAGE=" + json.dumps({"volume": volume, "rows": sorted(rows, key=lambda row: row["bytes"], reverse=True)}), flush=True)
