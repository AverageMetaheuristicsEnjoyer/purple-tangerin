import json
from pathlib import Path
import shutil


ROOT = Path("/home/jovyan/shares")
GATES = {
    "qwen3-2507": ROOT / "SR006.nfs2/xandi281/moe-revision-20260908/model-qwen3-2507-20260908T163305Z/result.json",
    "gpt-oss-20b": ROOT / "SR006.nfs2/xandi281/moe-revision-20260908/model-gpt-oss-20b-20260908T163310Z/result.json",
}


print("STORAGE_PROBE=" + json.dumps({
    "volumes": {
        name: {"total": shutil.disk_usage(ROOT / name).total,
               "used": shutil.disk_usage(ROOT / name).used,
               "free": shutil.disk_usage(ROOT / name).free}
        for name in ["SR006.nfs1", "SR006.nfs2", "SR006.nfs3"]
    },
    "model_gates": {
        name: {"exists": path.is_file(),
               "status": json.loads(path.read_text()).get("status") if path.is_file() else None}
        for name, path in GATES.items()
    },
}), flush=True)
