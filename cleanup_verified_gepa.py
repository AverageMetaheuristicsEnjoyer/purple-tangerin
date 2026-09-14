import hashlib
import json
from pathlib import Path
import shutil
from urllib.parse import quote
from urllib.request import urlopen


root = Path(
    "/home/jovyan/shares/SR006.nfs2/xandi281/moe-revision-20260911/"
    "civil-gepa-v2-user-only-v2"
)
runs = root / "runs"
receipt_path = root / "cleanup_verified_20260914.json"


def tree_bytes(path):
    return sum(item.stat().st_size for item in path.rglob("*") if item.is_file())


completed = []
active = []
for run in sorted(path for path in runs.iterdir() if path.is_dir()):
    if (run / "summary.json").is_file():
        completed.append(run)
    elif run.name.startswith("gepa-qwen3-2507-"):
        active.append(run)

if len(completed) != 11 or len(active) != 7:
    raise RuntimeError(
        f"Expected 11 completed and 7 active v2 runs, got {len(completed)} and {len(active)}"
    )

deleted_completed = []
for run in completed:
    summary = json.loads((run / "summary.json").read_text())
    cloud = json.loads((run / "cloud_result.json").read_text())
    receipt = json.loads((run / "hf_receipt.json").read_text())
    manifest = run / "artifact_manifest.json"
    if summary.get("status") != "PASS" or cloud.get("status") != "PASS":
        raise RuntimeError(f"Completed run is not PASS: {run.name}")
    if receipt.get("status") != "VERIFIED":
        raise RuntimeError(f"HF receipt is not VERIFIED: {run.name}")
    local_sha = hashlib.sha256(manifest.read_bytes()).hexdigest()
    if local_sha != receipt.get("artifact_manifest_sha256"):
        raise RuntimeError(f"Local artifact manifest differs from receipt: {run.name}")
    url = (
        f"https://huggingface.co/datasets/{receipt['repo']}/resolve/main/"
        f"{quote(receipt['prefix'], safe='/')}/artifact_manifest.json"
    )
    with urlopen(url, timeout=120) as response:
        remote_sha = hashlib.sha256(response.read()).hexdigest()
    if remote_sha != local_sha:
        raise RuntimeError(f"Current HF artifact manifest differs: {run.name}")
    deleted_completed.append({
        "run": run.name,
        "bytes": tree_bytes(run),
        "hf_repo": receipt["repo"],
        "hf_prefix": receipt["prefix"],
        "artifact_manifest_sha256": local_sha,
    })

deleted_old_servers = []
for run in active:
    if not (run / "gepa_logs/gepa_state.bin").is_file():
        raise RuntimeError(f"Active run has no resumable state: {run.name}")
    servers = sorted(path for path in run.glob("task_server_*") if path.is_dir())
    if len(servers) < 2:
        raise RuntimeError(f"Expected old and current task-server directories: {run.name}")
    keep = servers[-1]
    for server in servers[:-1]:
        deleted_old_servers.append({
            "run": run.name,
            "directory": server.name,
            "bytes": tree_bytes(server),
            "kept": keep.name,
        })

free_before = shutil.disk_usage(root).free
for row in deleted_completed:
    shutil.rmtree(runs / row["run"])
for row in deleted_old_servers:
    shutil.rmtree(runs / row["run"] / row["directory"])
free_after = shutil.disk_usage(root).free

result = {
    "status": "PASS",
    "free_before": free_before,
    "free_after": free_after,
    "freed_bytes": free_after - free_before,
    "deleted_completed": deleted_completed,
    "deleted_old_servers": deleted_old_servers,
}
receipt_path.write_text(json.dumps(result, indent=2) + "\n")
print("CLEANUP_RESULT=" + json.dumps({
    "status": result["status"],
    "completed_runs": len(deleted_completed),
    "old_server_directories": len(deleted_old_servers),
    "free_before": free_before,
    "free_after": free_after,
    "freed_bytes": free_after - free_before,
}))
