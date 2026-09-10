#!/usr/bin/env python3
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import shutil
from urllib.request import Request, urlopen

from revision_hf_archive import source_manifest


def verify_remote_archive(receipt):
    if (receipt["status"] != "VERIFIED"
            or receipt["decrypt_and_all_internal_hashes"] != "PASS"
            or receipt["repo"] != "AverageMetaheuristicsEnjoyer/silver-pomelo"
            or not re.fullmatch(r"[0-9a-f]{40}", receipt["commit"])
            or receipt["prefix"] != "violet-lime-v24/" + Path(receipt["source"]).name):
        raise ValueError("Expected a verified v24 immutable archive receipt")
    base = f"https://huggingface.co/{receipt['repo']}/resolve/{receipt['commit']}/{receipt['prefix']}"
    with urlopen(base + "/checksums.json", timeout=60) as response:
        checksums = json.load(response)
    if (checksums["manifest_sha256"] != receipt["manifest_sha256"]
            or checksums["sha256"] != receipt["anonymous_download_sha256"]):
        raise ValueError("Remote checksums differ from verified archive receipt")
    with urlopen(Request(base + "/resume.fernet", method="HEAD"), timeout=60) as response:
        if response.status != 200 or int(response.headers["Content-Length"]) != checksums["bytes"]:
            raise ValueError("Immutable archived blob is unavailable or has changed size")
    return checksums


def reclaim(receipt, source, proof_dir, execute=False):
    if source.resolve(strict=True) != source.absolute():
        raise ValueError("Source path must not traverse symlinks")
    if proof_dir.resolve().is_relative_to(source.resolve()):
        raise ValueError("Reclamation receipts must be outside the source")
    checksums = verify_remote_archive(receipt)
    manifest = source_manifest(source)
    if hashlib.sha256(manifest).hexdigest() != receipt["manifest_sha256"]:
        raise ValueError("Source inventory or hashes differ from archived source")
    files = json.loads(manifest)["files"]
    if len(files) != receipt["files"] or sum(row["bytes"] for row in files) != receipt["source_bytes"]:
        raise ValueError("Source file count or bytes differ from archive receipt")
    complete = json.loads((source / "COMPLETE.json").read_text())
    cell = Path(receipt["source"]).name
    if complete["status"] != "COMPLETE" or complete["cell"]["name"] != cell:
        raise ValueError("Source is not the completed archived cell")
    steps = [f"step_{step:06d}" for step in range(0, 1251, 125)]
    actual = sorted(path.name for path in (source / "training").glob("step_*"))
    if actual != steps or not all((source / "training" / step / "COMPLETE").is_file() for step in steps):
        raise ValueError("Expected all eleven complete checkpoint directories")
    removed = [row for row in files if row["path"].split("/")[:2] in [["training", step] for step in steps]]
    retained = [row for row in files if row not in removed]
    result = {"cell": cell, "source": str(source), "checked_at": datetime.now(timezone.utc).isoformat(),
              "status": "VALIDATED", "hf_receipt": receipt, "remote_checksums": checksums,
              "source_manifest": json.loads(manifest), "checkpoint_directories": steps,
              "reclaim_bytes": sum(row["bytes"] for row in removed), "removed_files": len(removed),
              "retained_files": len(retained), "filesystem_free_before": shutil.disk_usage(source).free}
    proof_dir.mkdir(parents=True, exist_ok=True)
    proof = proof_dir / (cell + ".json")
    if proof.exists():
        raise FileExistsError(proof)
    proof.write_text(json.dumps(result, indent=2) + "\n")
    if execute:
        for step in steps:
            shutil.rmtree(source / "training" / step)
        if json.loads(source_manifest(source))["files"] != retained:
            raise ValueError("Retained metadata differs after checkpoint removal")
        result.update(status="RECLAIMED", completed_at=datetime.now(timezone.utc).isoformat(),
                      filesystem_free_after=shutil.disk_usage(source).free)
        proof.write_text(json.dumps(result, indent=2) + "\n")
    print("RECLAMATION_RESULT=" + json.dumps({key: result[key] for key in
          ["cell", "source", "status", "reclaim_bytes", "removed_files", "retained_files"]}), flush=True)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--proof-dir", type=Path, required=True)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    plan = json.loads(args.plan.read_text())
    if plan["authorization"] != "USER_AUTHORIZED_20260910":
        raise ValueError("Expected the explicitly authorized cleanup plan")
    for row in plan["sources"]:
        source = Path(row["source"])
        if not source.is_relative_to(Path(plan["allowed_root"])):
            raise ValueError("Source is outside the authorized root")
        reclaim(row["receipt"], source, args.proof_dir, args.execute)


if __name__ == "__main__":
    main()
