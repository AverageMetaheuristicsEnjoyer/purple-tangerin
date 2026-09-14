import json
from pathlib import Path
import shutil
import subprocess


def measure(path, depth):
    result = subprocess.run(
        ["du", "-x", "-B1", f"--max-depth={depth}", str(path)],
        capture_output=True,
        text=True,
    )
    rows = []
    for line in result.stdout.splitlines():
        size, name = line.split("\t", 1)
        rows.append({"bytes": int(size), "path": name})
    return {
        "path": str(path),
        "returncode": result.returncode,
        "errors": result.stderr.splitlines()[:20],
        "rows": sorted(rows, key=lambda row: row["bytes"], reverse=True),
    }


shares = Path("/home/jovyan/shares")
for name in ["SR006.nfs1", "SR006.nfs2", "SR006.nfs3"]:
    volume = shares / name
    usage = shutil.disk_usage(volume)
    print("GLOBAL_USAGE=" + json.dumps({
        "volume": name,
        "total_bytes": usage.total,
        "used_bytes": usage.used,
        "free_bytes": usage.free,
        "du": measure(volume, 1),
    }), flush=True)

targets = [
    shares / "SR006.nfs2/xandi281/encrypted-bundles",
    shares / "SR006.nfs2/xandi281/moe-revision-20260908/main-civil-v22",
    shares / "SR006.nfs2/xandi281/moe-revision-20260911",
    shares / "SR006.nfs3/xandi281/moe-revision-20260908/main-civil-v24",
    shares / "SR006.nfs3/xandi281/moe-revision-20260908/civil-v2-user-only-peft-v25",
]
for target in targets:
    if target.is_dir():
        print("TARGET_USAGE=" + json.dumps(measure(target, 3)), flush=True)
