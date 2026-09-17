import json
from pathlib import Path
import shutil
print("PROGRESS_PROBE_STARTED", flush=True)

root = Path("/home/jovyan/shares/SR006.nfs1/xandi281/moe-revision-20260917/gpt-oss-20b-civil-v2-reasoning-peft-pilot-v5")
result = {"root_exists": root.is_dir()}
print("PROGRESS_PROBE_ROOT_EXISTS=" + str(result["root_exists"]), flush=True)
result["nfs1_free_bytes"] = shutil.disk_usage(root.parent).free
if root.is_dir():
    result["top_files"] = sorted(p.name for p in root.iterdir())
    pilot = root / "pilot"
    result["pilot_files"] = sorted(p.name for p in pilot.iterdir()) if pilot.is_dir() else []
    for method in ("prompt", "prefix-projected"):
        path = pilot / method
        training = path / "training"
        result[method] = {
            "files": sorted(p.name for p in path.iterdir()) if path.is_dir() else [],
            "training_files": sorted(p.name for p in training.iterdir()) if training.is_dir() else [],
            "complete_steps": sorted(p.name for p in training.glob("step_*") if (p / "COMPLETE").is_file()),
            "adapter_steps": sorted(p.name for p in training.glob("step_*") if (p / "ADAPTER_ONLY").is_file()),
        }
        for name in ("summary.json", "quality.json", "selection.json"):
            file = training / name if name == "summary.json" else path / name
            if file.is_file():
                result[method][name] = json.loads(file.read_text())
print("PROGRESS_PROBE=" + json.dumps(result, ensure_ascii=False), flush=True)
