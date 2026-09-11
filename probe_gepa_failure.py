import hashlib
import json
from pathlib import Path


RUN = Path(
    "/home/jovyan/shares/SR006.nfs2/xandi281/moe-revision-20260911/"
    "civil-gepa-v2-user-only-v2/runs/gepa-gpt-oss-20b-n200-s42"
)


def rows(path):
    with path.open() as handle:
        return [json.loads(line) for line in handle if line.strip()]


evaluations = rows(RUN / "evaluations.jsonl")
truncated = [row for row in evaluations if row.get("finish_reason") == "length"]
files = []
for path in sorted((RUN / "gepa_logs").rglob("*")):
    if path.is_file():
        files.append({"path": str(path.relative_to(RUN)), "bytes": path.stat().st_size})

print("GEPA_FAILURE_PROBE=" + json.dumps({
    "calls": len(evaluations),
    "truncated": [{
        "key": row.get("key"),
        "candidate_sha256": hashlib.sha256(
            json.dumps(row.get("candidate"), sort_keys=True).encode()
        ).hexdigest(),
        "candidate_chars": len(next(iter((row.get("candidate") or {}).values()), "")),
        "final_chars": len(row.get("raw") or ""),
        "usage": row.get("usage"),
        "raw_usage": row.get("raw_usage"),
        "request_attempts": row.get("request_attempts"),
        "retry_events": row.get("retry_events"),
    } for row in truncated],
    "gepa_files": files,
    "summary_exists": (RUN / "summary.json").is_file(),
    "stop_marker": (RUN / "reflection_queue" / "stopped.json").is_file(),
}, sort_keys=True), flush=True)
