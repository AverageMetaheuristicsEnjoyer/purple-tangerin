from __future__ import annotations

import hashlib
import io
import json
import os
import shutil
import tempfile
from pathlib import Path


os.environ.setdefault("HF_HOME", "/tmp/tucker-late-hf-home")
os.environ.setdefault("HF_HUB_CACHE", "/tmp/tucker-late-hf-home/hub")

from huggingface_hub import HfApi, hf_hub_download


REPO_ID = "AverageMetaheuristicsEnjoyer/progressive-tucker-checkpoints"
PREFIX = "tucker-late-growth-cloud-20260827"
ROOT = Path("/home/jovyan/shares/SR006.nfs3/tucker-late-growth-20260827")
SOURCES = {
    "225-to-257/latest/main.pt": ROOT / "exps/1xChinchilla-tucker-retract/llama257m_tucker_late_225m_to_257m_customfb_bs16acc8/ckpts/latest/main.pt",
    "225-to-257/latest/worker_0.pt": ROOT / "exps/1xChinchilla-tucker-retract/llama257m_tucker_late_225m_to_257m_customfb_bs16acc8/ckpts/latest/worker_0.pt",
    "225-to-257/best_val/main.pt": ROOT / "exps/1xChinchilla-tucker-retract/llama257m_tucker_late_225m_to_257m_customfb_bs16acc8/ckpts/best_val/main.pt",
    "225-to-257/best_val/worker_0.pt": ROOT / "exps/1xChinchilla-tucker-retract/llama257m_tucker_late_225m_to_257m_customfb_bs16acc8/ckpts/best_val/worker_0.pt",
    "169-to-257/best_val/main.pt": ROOT / "exps/1xChinchilla-tucker-retract/llama257m_tucker_late_169m_to_257m_customfb_bs16acc8_run1/ckpts/best_val/main.pt",
    "169-to-257/best_val/worker_0.pt": ROOT / "exps/1xChinchilla-tucker-retract/llama257m_tucker_late_169m_to_257m_customfb_bs16acc8_run1/ckpts/best_val/worker_0.pt",
}
DELETE_DIRS = sorted({path.parent for path in SOURCES.values()}, key=str)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


token = os.environ["HF_TOKEN"]
api = HfApi(token=token)
repo = api.model_info(REPO_ID)
if repo.private:
    raise RuntimeError(f"{REPO_ID} must remain public for anonymous verification")

files = []
for relative, source in SOURCES.items():
    if not source.is_file():
        raise FileNotFoundError(source)
    files.append(
        {
            "source": str(source),
            "hf_path": f"{PREFIX}/{relative}",
            "size": source.stat().st_size,
            "sha256": sha256(source),
        }
    )

manifest = {
    "schema": "tucker-late-growth-cloud-checkpoint-archive-v1",
    "repo": REPO_ID,
    "prefix": PREFIX,
    "files": files,
}
for item in files:
    api.upload_file(
        path_or_fileobj=item["source"],
        path_in_repo=item["hf_path"],
        repo_id=REPO_ID,
        repo_type="model",
        commit_message=f"Archive {item['hf_path']}",
    )
api.upload_file(
    path_or_fileobj=io.BytesIO((json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode()),
    path_in_repo=f"{PREFIX}/manifest.json",
    repo_id=REPO_ID,
    repo_type="model",
    commit_message="Add Tucker late-growth Cloud archive manifest",
)
archive_commit = api.model_info(REPO_ID).sha

with tempfile.TemporaryDirectory(prefix="tucker-late-verify-") as temp:
    for item in files:
        downloaded = Path(
            hf_hub_download(
                REPO_ID,
                filename=item["hf_path"],
                repo_type="model",
                revision=archive_commit,
                token=False,
                force_download=True,
                cache_dir=temp,
            )
        )
        item["downloaded_size"] = downloaded.stat().st_size
        item["downloaded_sha256"] = sha256(downloaded)
        item["verified"] = (
            item["downloaded_size"] == item["size"]
            and item["downloaded_sha256"] == item["sha256"]
        )

if not all(item["verified"] for item in files):
    raise RuntimeError("anonymous HF re-download verification failed; Cloud sources retained")

free_before = shutil.disk_usage(ROOT).free
deleted = []
for directory in DELETE_DIRS:
    shutil.rmtree(directory)
    deleted.append({"path": str(directory), "absent_after": not directory.exists()})
free_after = shutil.disk_usage(ROOT).free

receipt = {
    "status": "PASS" if all(item["absent_after"] for item in deleted) else "FAIL",
    "repo": REPO_ID,
    "prefix": PREFIX,
    "archive_commit": archive_commit,
    "anonymous_redownload": "PASS",
    "files": files,
    "deleted": deleted,
    "free_before": free_before,
    "free_after": free_after,
    "free_delta": free_after - free_before,
}
receipt_dir = ROOT / "hf_archive_receipts"
receipt_dir.mkdir(exist_ok=True)
receipt_path = receipt_dir / f"{PREFIX}.json"
receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
api.upload_file(
    path_or_fileobj=str(receipt_path),
    path_in_repo=f"{PREFIX}/receipt.json",
    repo_id=REPO_ID,
    repo_type="model",
    commit_message="Record verified Tucker late-growth Cloud cleanup",
)
print("TUCKER_LATE_ARCHIVE=" + json.dumps(receipt, sort_keys=True), flush=True)
