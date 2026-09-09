import json
import os
from pathlib import Path
import shutil

root = Path("/home/jovyan/shares")
for path in sorted(root.iterdir()):
    if path.is_dir():
        usage = shutil.disk_usage(path)
        print("VOLUME_INVENTORY=" + json.dumps({"path": str(path), "total_bytes": usage.total, "used_bytes": usage.used, "free_bytes": usage.free, "writable": os.access(path, os.W_OK), "device": path.stat().st_dev}), flush=True)
