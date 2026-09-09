import argparse
import json
from pathlib import Path
import shutil

parser = argparse.ArgumentParser()
parser.add_argument("--source", type=Path, required=True)
args = parser.parse_args()
for cell in sorted(args.source.iterdir()):
    if not cell.is_dir():
        continue
    files = [path for path in cell.rglob("*") if path.is_file()]
    checkpoints = sorted(int(path.name.split("_")[1]) for path in (cell / "training").glob("step_*") if (path / "COMPLETE").is_file())
    print("CELL_INVENTORY=" + json.dumps({"name": cell.name, "files": len(files), "bytes": sum(path.stat().st_size for path in files), "complete": (cell / "COMPLETE.json").is_file(), "checkpoint_steps": checkpoints}), flush=True)
usage = shutil.disk_usage(args.source)
print("DISK_INVENTORY=" + json.dumps({"source": str(args.source), "filesystem_free_bytes": usage.free}), flush=True)
