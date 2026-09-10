import json
import shutil
from pathlib import Path


ROOT = Path(
    "/home/jovyan/shares/SR006.nfs2/xandi281/moe-revision-20260911/"
    "civil-gepa-v2-user-only-v1/runs"
)


def read_json(path: Path):
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text())
    except Exception as exc:
        return {"read_error": f"{type(exc).__name__}: {exc}"}


def evaluation_stats(path: Path):
    if not path.is_file():
        return {"calls": 0, "truncated": 0, "last_truncated": None}
    calls = 0
    truncated = 0
    last_truncated = None
    with path.open() as handle:
        for line in handle:
            if not line.strip():
                continue
            calls += 1
            row = json.loads(line)
            if row.get("finish_reason") == "length":
                truncated += 1
                last_truncated = {
                    "key": row.get("key"),
                    "raw_chars": len(row.get("raw") or ""),
                    "usage": row.get("usage"),
                    "raw_usage": row.get("raw_usage"),
                }
    return {"calls": calls, "truncated": truncated, "last_truncated": last_truncated}


def jsonl_count(path: Path):
    if not path.is_file():
        return 0
    with path.open() as handle:
        return sum(bool(line.strip()) for line in handle)


def tail(path: Path, limit: int = 5000):
    if not path.is_file():
        return None
    return path.read_text(errors="replace")[-limit:]


cells = []
if ROOT.is_dir():
    for cell_dir in sorted(path for path in ROOT.iterdir() if path.is_dir()):
        summary = read_json(cell_dir / "summary.json")
        cloud_result = read_json(cell_dir / "cloud_result.json")
        receipt = read_json(cell_dir / "hf_upload_receipt.json")
        queue = cell_dir / "reflection_queue"
        evaluations = evaluation_stats(cell_dir / "evaluations.jsonl")
        cells.append(
            {
                "name": cell_dir.name,
                "summary_status": summary.get("status") if isinstance(summary, dict) else None,
                "best_idx": summary.get("best_idx") if isinstance(summary, dict) else None,
                "best_score": summary.get("best_score") if isinstance(summary, dict) else None,
                "seed_score": summary.get("seed_score") if isinstance(summary, dict) else None,
                "metric_calls": summary.get("total_metric_calls") if isinstance(summary, dict) else None,
                "cloud_status": cloud_result.get("status") if isinstance(cloud_result, dict) else None,
                "cloud_error": cloud_result.get("error") if isinstance(cloud_result, dict) else None,
                "evaluations": evaluations,
                "reflections": jsonl_count(cell_dir / "reflection.jsonl"),
                "requests": len(list(queue.glob("request-*.json"))) if queue.is_dir() else 0,
                "responses": len(list(queue.glob("response-*.json"))) if queue.is_dir() else 0,
                "worker_done": (queue / "WORKER_DONE.json").is_file(),
                "hf_verified": bool(receipt and receipt.get("verified")),
                "hf_commit": receipt.get("commit_sha") if isinstance(receipt, dict) else None,
                "gepa_tail": tail(cell_dir / "gepa_stdout.log")
                if isinstance(cloud_result, dict) and cloud_result.get("status") == "FAIL"
                else None,
            }
        )

usage = shutil.disk_usage(ROOT if ROOT.exists() else ROOT.parent)
print(
    "GEPA_FULL_PROBE="
    + json.dumps(
        {
            "root": str(ROOT),
            "cells": cells,
            "disk": {
                "free_bytes": usage.free,
                "total_bytes": usage.total,
            },
        },
        sort_keys=True,
    ),
    flush=True,
)
