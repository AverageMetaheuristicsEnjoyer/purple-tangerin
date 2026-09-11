import json
import shutil
from pathlib import Path


ROOT = Path(
    "/home/jovyan/shares/SR006.nfs2/xandi281/moe-revision-20260911/"
    "civil-gepa-v2-user-only-v2/runs"
)
print("GEPA_DIRS=" + json.dumps({
    "dirs": sorted(path.name for path in ROOT.iterdir() if path.is_dir()),
    "free_bytes": shutil.disk_usage(ROOT).free,
}), flush=True)
