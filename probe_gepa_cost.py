import json
from pathlib import Path


ROOT = Path(
    "/home/jovyan/shares/SR006.nfs2/xandi281/moe-revision-20260911/"
    "civil-gepa-v2-user-only-v2/runs"
)


def cost(path):
    total = 0.0
    calls = 0
    if path.is_file():
        for line in path.read_text().splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            usage = row.get("raw_usage") or row.get("usage") or {}
            total += usage.get("cost") or 0.0
            calls += 1
    return calls, total


cells = []
for run in sorted(ROOT.glob("gepa-gpt-oss-20b-*")):
    task_calls, task_cost = cost(run / "evaluations.jsonl")
    reflection_calls, reflection_cost = cost(run / "reflection.jsonl")
    cells.append({
        "name": run.name,
        "complete": (run / "summary.json").is_file(),
        "task_calls": task_calls,
        "task_cost": task_cost,
        "reflection_calls": reflection_calls,
        "reflection_cost": reflection_cost,
    })
print("GEPA_COST_PROBE=" + json.dumps(cells, sort_keys=True), flush=True)
