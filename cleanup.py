import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

parser = argparse.ArgumentParser()
parser.add_argument("--volume", choices=["SR006.nfs1", "SR006.nfs2", "SR006.nfs3"], required=True)
parser.add_argument("--execute", action="store_true")
args = parser.parse_args()
os.umask(0o077)
key = os.environ.pop("BUNDLE_KEY").encode()
root = Path(__file__).resolve().parent
checks = json.loads((root / "checksums.json").read_text())
for name, digest in checks.items():
    assert hashlib.sha256((root / name).read_bytes()).hexdigest() == digest, name
with tempfile.TemporaryDirectory(prefix="checkpoint-reclamation-") as temporary:
    deps = Path(temporary) / "deps"
    subprocess.run([sys.executable, "-m", "pip", "install", "--no-cache-dir", "--target", str(deps), "cryptography==46.0.5"], check=True)
    sys.path.insert(0, str(deps))
    from cryptography.fernet import Fernet
    from reclaim_revision_checkpoints import reclaim
    plan = json.loads(Fernet(key).decrypt((root / "cleanup_plan.fernet").read_bytes()))
    assert plan["authorization"] == "USER_AUTHORIZED_20260910"
    volume = Path("/home/jovyan/shares") / args.volume
    runroot = volume / "xandi281/moe-revision-20260908/main-civil-v24/runs"
    proofs = volume / "xandi281/moe-revision-20260908/reclamation-v24-20260910"
    selected = [row for row in plan["sources"] if Path(row["source"]).is_relative_to(volume)]
    for row in selected:
        source = Path(row["source"])
        assert source.parent == runroot and source == Path(row["receipt"]["source"])
        reclaim(row["receipt"], source, proofs, args.execute)
    print("RECLAMATION_BATCH_COMPLETE=" + json.dumps({"volume": str(volume), "cells": len(selected), "execute": args.execute}), flush=True)
