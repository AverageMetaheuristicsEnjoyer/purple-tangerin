import json
from pathlib import Path
import shutil


root = Path(
    "/home/jovyan/shares/SR006.nfs2/xandi281/moe-revision-20260911/"
    "civil-gepa-v2-user-only-v2/runs"
)
indices = {
    9: "gepa-qwen3-2507-n200-s42",
    11: "gepa-qwen3-2507-n1000-s42",
    12: "gepa-qwen3-2507-n200-s43",
    13: "gepa-qwen3-2507-n500-s43",
    14: "gepa-qwen3-2507-n1000-s43",
    15: "gepa-qwen3-2507-n200-s44",
    16: "gepa-qwen3-2507-n500-s44",
    17: "gepa-qwen3-2507-n1000-s44",
}
rows = []
for index, name in indices.items():
    run = root / name
    evaluations = run / "evaluations.jsonl"
    rows.append({
        "index": index,
        "name": name,
        "state": (run / "gepa_logs/gepa_state.bin").is_file(),
        "evaluations": sum(1 for _ in evaluations.open()) if evaluations.is_file() else 0,
        "summary": (run / "summary.json").is_file(),
    })
print("RESUME_PROBE=" + json.dumps({
    "free_bytes": shutil.disk_usage(root).free,
    "runs": rows,
}))
