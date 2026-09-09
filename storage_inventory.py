import argparse
import json
from pathlib import Path
import shutil

parser = argparse.ArgumentParser()
parser.add_argument("--relative-root", required=True)
args = parser.parse_args()
relative = Path(args.relative_root)
if relative.is_absolute() or ".." in relative.parts:
    parser.error("relative-root must stay inside each mounted volume")
for name in ("SR006.nfs1", "SR006.nfs2", "SR006.nfs3"):
    volume = Path("/home/jovyan/shares") / name
    source = volume / relative
    cells = []
    if source.is_dir():
        for cell in sorted(source.iterdir()):
            if not cell.is_dir():
                continue
            files = [p for p in cell.rglob("*") if p.is_file()]
            checkpoints = [p for p in (cell / "training").glob("step_*") if (p / "COMPLETE").is_file()]
            cells.append({"name": cell.name, "bytes": sum(p.stat().st_size for p in files),
                          "complete": (cell / "COMPLETE.json").is_file(),
                          "checkpoint_steps": sorted(int(p.name.split("_")[1]) for p in checkpoints),
                          "complete_checkpoint_bytes": sum(p.stat().st_size for c in checkpoints for p in c.rglob("*") if p.is_file())})
    print("STORAGE_INVENTORY=" + json.dumps({"volume": str(volume), "source": str(source),
          "source_exists": source.is_dir(), "free_bytes": shutil.disk_usage(volume).free,
          "cells": cells}), flush=True)
