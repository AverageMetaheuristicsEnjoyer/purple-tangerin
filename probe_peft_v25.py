import json
from pathlib import Path
import shutil


BASE = Path("/home/jovyan/shares")
VERSION = "civil-v2-user-only-peft-v25"


report = {"volumes": {}, "cells": []}
for volume_name in ["SR006.nfs1", "SR006.nfs2", "SR006.nfs3"]:
    volume = BASE / volume_name
    report["volumes"][volume_name] = {"free": shutil.disk_usage(volume).free}
    root = volume / "xandi281/moe-revision-20260908" / VERSION / "runs"
    receipts = volume / "xandi281/moe-revision-20260908/hf-receipts-v25-user-only"
    for run in sorted(root.glob("multilabel-v2-user-only-*")):
        steps = sorted(path.name for path in (run / "training").glob("step_*"))
        receipt = receipts / f"{run.name}.json"
        report["cells"].append({
            "name": run.name,
            "volume": volume_name,
            "complete": (run / "COMPLETE.json").is_file(),
            "summary": json.loads((run / "training/summary.json").read_text()).get("status")
                       if (run / "training/summary.json").is_file() else None,
            "steps": len(steps),
            "last_step": steps[-1] if steps else None,
            "quality": (run / "quality.json").is_file(),
            "selection": (run / "selection.json").is_file(),
            "hf_verified": receipt.is_file() and json.loads(receipt.read_text()).get("status") == "VERIFIED",
        })
print("PEFT_V25_PROBE=" + json.dumps(report), flush=True)
