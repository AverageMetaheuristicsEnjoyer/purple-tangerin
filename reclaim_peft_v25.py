import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
from urllib.request import Request, urlopen


REPO = "AverageMetaheuristicsEnjoyer/silver-pomelo"
PREFIX = "civil-v2-user-only-v25"
VERSION = "civil-v2-user-only-peft-v25"
BASE = Path("/home/jovyan/shares")
STEPS = [f"step_{step:06d}" for step in range(0, 1251, 125)]


def digest(path):
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024**2), b""):
            value.update(block)
    return value.hexdigest()


def source_manifest(source):
    files = []
    for path in sorted(source.rglob("*")):
        if path.is_symlink():
            raise ValueError("Archive source must not contain symlinks")
        if path.is_file():
            files.append({"path": str(path.relative_to(source)), "bytes": path.stat().st_size,
                          "sha256": digest(path)})
    return json.dumps({"files": files}, sort_keys=True, indent=2).encode()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--cell", required=True)
    parser.add_argument("--nfs-volume", choices=["SR006.nfs1", "SR006.nfs2", "SR006.nfs3"], required=True)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    if not re.fullmatch(r"multilabel-v2-user-only-(qwen3-2507|gpt-oss-20b)-(prompt|prefix-projected)-m(100|200|500)-s(42|43|44)", args.cell):
        raise ValueError("Cell name is outside the frozen v25 matrix")
    volume = BASE / args.nfs_volume
    root = volume / "xandi281/moe-revision-20260908" / VERSION / "runs"
    source = root / args.cell
    receipt_path = volume / "xandi281/moe-revision-20260908/hf-receipts-v25-user-only" / f"{args.cell}.json"
    proof_dir = volume / "xandi281/moe-revision-20260908/reclaim-proofs-v25-user-only"
    proof_path = proof_dir / f"{args.cell}.json"
    if proof_path.is_file() and json.loads(proof_path.read_text()).get("status") == "RECLAIMED":
        print("RECLAMATION_ALREADY_COMPLETE=" + args.cell, flush=True)
        return
    if source.resolve(strict=True) != source.absolute() or source.parent != root:
        raise ValueError("Source path is not the exact frozen v25 cell")
    receipt = json.loads(receipt_path.read_text())
    expected_remote = f"{PREFIX}/{args.cell}"
    if (receipt.get("status") != "VERIFIED"
            or receipt.get("decrypt_and_all_internal_hashes") != "PASS"
            or receipt.get("repo") != REPO
            or receipt.get("prefix") != expected_remote
            or not re.fullmatch(r"[0-9a-f]{40}", receipt.get("commit", ""))):
        raise ValueError("Expected a verified immutable v25 archive receipt")
    base = f"https://huggingface.co/{REPO}/resolve/{receipt['commit']}/{expected_remote}"
    with urlopen(base + "/checksums.json", timeout=60) as response:
        checksums = json.load(response)
    if (checksums.get("manifest_sha256") != receipt.get("manifest_sha256")
            or checksums.get("sha256") != receipt.get("anonymous_download_sha256")):
        raise ValueError("Remote checksums differ from the verified receipt")
    with urlopen(Request(base + "/resume.fernet", method="HEAD"), timeout=60) as response:
        if response.status != 200 or int(response.headers["Content-Length"]) != checksums["bytes"]:
            raise ValueError("Archived blob is unavailable or differs in size")
    manifest = source_manifest(source)
    if hashlib.sha256(manifest).hexdigest() != receipt.get("manifest_sha256"):
        raise ValueError("Current source differs from the verified archive")
    complete = json.loads((source / "COMPLETE.json").read_text())
    if complete.get("status") != "COMPLETE" or complete.get("cell", {}).get("name") != args.cell:
        raise ValueError("Source is not a completed frozen v25 cell")
    actual_steps = sorted(path.name for path in (source / "training").glob("step_*"))
    if actual_steps != STEPS or not all((source / "training" / step / "COMPLETE").is_file() for step in STEPS):
        raise ValueError("Expected all eleven complete checkpoint directories")
    files = json.loads(manifest)["files"]
    removed = [row for row in files if row["path"].split("/")[:2] in [["training", step] for step in STEPS]]
    retained = [row for row in files if row not in removed]
    result = {
        "cell": args.cell, "source": str(source), "status": "VALIDATED",
        "checked_at": datetime.now(timezone.utc).isoformat(), "hf_receipt": receipt,
        "remote_checksums": checksums, "source_manifest": json.loads(manifest),
        "checkpoint_directories": STEPS, "reclaim_bytes": sum(row["bytes"] for row in removed),
        "removed_files": len(removed), "retained_files": len(retained),
        "filesystem_free_before": shutil.disk_usage(source).free,
    }
    proof_dir.mkdir(parents=True, exist_ok=True)
    temporary = proof_path.with_suffix(f".{os.getpid()}.tmp")
    temporary.write_text(json.dumps(result, indent=2) + "\n")
    os.replace(temporary, proof_path)
    if args.execute:
        for step in STEPS:
            shutil.rmtree(source / "training" / step)
        if json.loads(source_manifest(source))["files"] != retained:
            raise ValueError("Retained metadata differs after checkpoint reclamation")
        result.update(status="RECLAIMED", completed_at=datetime.now(timezone.utc).isoformat(),
                      filesystem_free_after=shutil.disk_usage(source).free)
        temporary.write_text(json.dumps(result, indent=2) + "\n")
        os.replace(temporary, proof_path)
    print("RECLAMATION_RESULT=" + json.dumps({key: result[key] for key in [
        "cell", "status", "reclaim_bytes", "removed_files", "retained_files"]}), flush=True)


if __name__ == "__main__":
    main()
