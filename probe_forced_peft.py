import json
from pathlib import Path


root = Path("/home/jovyan/shares/SR006.nfs3/xandi281/moe-revision-20260915/peft-forced-reasoning-pilot-v1")
rows = []
for run in sorted(root.glob("multilabel-v2-user-only-gpt-oss-20b-*")):
    item = {"cell": run.name}
    for mode in ("native", "forced_analysis"):
        output = run / f"{mode}.jsonl"
        summary = run / f"{mode}.summary.json"
        item[mode] = {
            "rows": sum(1 for _ in output.open()) if output.is_file() else 0,
            "summary": json.loads(summary.read_text()) if summary.is_file() else None,
        }
    rows.append(item)
print("PEFT_FORCED_REASONING_PROGRESS=" + json.dumps(rows))
