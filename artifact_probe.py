import hashlib
import json
from pathlib import Path
import shutil

root = Path("/home/jovyan/shares/SR006.nfs3/xandi281/moe-revision-20260917/gpt-oss-20b-civil-v2-reasoning-peft-pilot-v3")
paths = [
    "cloud_contract.json", "hub_manifest.json", "weight_hashes.json", "artifact_manifest.json",
    "pilot/contract.json", "pilot/teacher_generations.jsonl", "pilot/train_targets.jsonl",
    "pilot/teacher_summary.json", "pilot/summary.json", "pilot/prompt/training/manifest.json",
    "pilot/prompt/training/summary.json", "pilot/prompt/quality.json", "pilot/prompt/selection.json",
    "pilot/prefix-projected/training/summary.json", "pilot/prefix-projected/quality.json",
    "pilot/prefix-projected/selection.json",
]
report = {"root": str(root), "nfs_free_bytes": shutil.disk_usage(root.parent).free, "files": {}}
for name in paths:
    path = root / name
    row = {"exists": path.is_file()}
    if path.is_file():
        row["bytes"] = path.stat().st_size
        if path.stat().st_size < 10**7:
            row["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    report["files"][name] = row
teacher = root / "pilot/teacher_summary.json"
if teacher.is_file():
    info = json.loads(teacher.read_text())
    report["teacher"] = {key: info.get(key) for key in ("candidate_records", "accepted", "mean_completion_tokens", "mean_sequence_tokens", "targets_sha256")}
training = root / "pilot/prompt/training"
report["prompt_step_directories"] = sorted(path.name for path in training.glob("step_*") if path.is_dir())
print("REASONING_V3_INSPECT=" + json.dumps(report), flush=True)
