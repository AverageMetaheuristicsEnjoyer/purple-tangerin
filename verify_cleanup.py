import json
from pathlib import Path
import shutil


root = Path(
    "/home/jovyan/shares/SR006.nfs2/xandi281/moe-revision-20260911/"
    "civil-gepa-v2-user-only-v2"
)
runs = root / "runs"
receipt = json.loads((root / "cleanup_verified_20260914.json").read_text())
active = []
for run in sorted(path for path in runs.iterdir() if path.is_dir()):
    servers = sorted(path.name for path in run.glob("task_server_*") if path.is_dir())
    active.append({
        "run": run.name,
        "state": (run / "gepa_logs/gepa_state.bin").is_file(),
        "summary": (run / "summary.json").is_file(),
        "servers": servers,
    })
print("CLEANUP_VERIFY=" + json.dumps({
    "receipt": receipt,
    "free_bytes_now": shutil.disk_usage(root).free,
    "remaining_runs": active,
}))
