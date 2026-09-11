import json
import shutil
from pathlib import Path


ROOT = Path(
    "/home/jovyan/shares/SR006.nfs2/xandi281/moe-revision-20260911/"
    "civil-gepa-v2-user-only-v2/runs"
)


def read_json(path):
    return json.loads(path.read_text()) if path.is_file() else None


def jsonl_count(path):
    if not path.is_file():
        return 0
    with path.open() as handle:
        return sum(bool(line.strip()) for line in handle)


cells = []
for run in sorted(path for path in ROOT.iterdir() if path.is_dir()):
    summary = read_json(run / "summary.json")
    cloud = read_json(run / "cloud_result.json")
    receipt = read_json(run / "hf_receipt.json")
    error = cloud.get("error") if cloud else None
    cells.append({
        "name": run.name,
        "cloud": cloud.get("status") if cloud else None,
        "error": error.split(":", 1)[0] if error else None,
        "summary": summary.get("status") if summary else None,
        "calls": jsonl_count(run / "evaluations.jsonl"),
        "truncated": sum(
            json.loads(line).get("finish_reason") == "length"
            for line in (run / "evaluations.jsonl").open()
        ) if (run / "evaluations.jsonl").is_file() else 0,
        "reflections": jsonl_count(run / "reflection.jsonl"),
        "worker_done": (run / "reflection_queue" / "stopped.json").is_file(),
        "hf_verified": bool(receipt and receipt.get("status") == "VERIFIED"),
    })

print("GEPA_COMPACT_PROBE=" + json.dumps({
    "cells": cells,
    "free_bytes": shutil.disk_usage(ROOT).free,
}, sort_keys=True), flush=True)
