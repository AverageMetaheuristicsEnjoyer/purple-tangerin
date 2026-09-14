import json
from pathlib import Path


roots = [
    Path("/home/jovyan/shares/SR006.nfs2/xandi281/moe-revision-20260908/main-civil-v22"),
    Path("/home/jovyan/shares/SR006.nfs3/xandi281/moe-revision-20260908/main-civil-v24"),
    Path("/home/jovyan/shares/SR006.nfs3/xandi281/moe-revision-20260908/civil-v2-user-only-peft-v25"),
]
for root in roots:
    runs = root / "runs"
    rows = []
    for run in sorted(path for path in runs.iterdir() if path.is_dir()):
        steps = list(run.rglob("step_*"))
        rows.append({
            "name": run.name,
            "complete": (run / "COMPLETE.json").is_file(),
            "training_summary": (run / "training/summary.json").is_file(),
            "schedule_result": (run / "result.json").is_file(),
            "step_directories": sum(path.is_dir() for path in steps),
            "step_complete_markers": sum((path / "COMPLETE").is_file() for path in steps if path.is_dir()),
        })
    print("CIVIL_USAGE=" + json.dumps({
        "root": str(root),
        "runs": len(rows),
        "complete_runs": sum(row["complete"] for row in rows),
        "training_summaries": sum(row["training_summary"] for row in rows),
        "schedule_results": sum(row["schedule_result"] for row in rows),
        "step_directories": sum(row["step_directories"] for row in rows),
        "step_complete_markers": sum(row["step_complete_markers"] for row in rows),
        "details": rows,
    }), flush=True)
