import json
from pathlib import Path
import subprocess


roots = [
    "SR006.nfs1/rl_muon",
    "SR006.nfs1/data",
    "SR006.nfs1/hmoe-checkpoints",
    "SR006.nfs1/hmoe-cloud",
    "SR006.nfs1/hmoe-hf-cache-broad-v1",
    "SR006.nfs2/hmoe-checkpoints",
    "SR006.nfs2/hmoe-data",
    "SR006.nfs2/hmoe-cloud",
    "SR006.nfs2/dimativator",
    "SR006.nfs3/hmoe-checkpoints",
    "SR006.nfs3/hmoe-cloud",
    "SR006.nfs3/hmoe-membench",
    "SR006.nfs3/dimativator",
    "SR006.nfs3/tucker-late-growth-20260827",
    "SR006.nfs3/progressive-tucker-257m-optimized-20260825",
    "SR006.nfs3/dykaf-weights",
]
base = Path("/home/jovyan/shares")
for relative in roots:
    path = base / relative
    if not path.is_dir():
        continue
    result = subprocess.run(
        ["du", "-x", "-B1", "--max-depth=1", str(path)],
        capture_output=True,
        text=True,
    )
    rows = []
    for line in result.stdout.splitlines():
        size, name = line.split("\t", 1)
        rows.append({"bytes": int(size), "path": name})
    print("PROJECT_USAGE=" + json.dumps({
        "path": str(path),
        "returncode": result.returncode,
        "errors": result.stderr.splitlines()[:20],
        "rows": sorted(rows, key=lambda row: row["bytes"], reverse=True),
    }), flush=True)
