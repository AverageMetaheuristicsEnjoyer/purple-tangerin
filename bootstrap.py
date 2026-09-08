#!/usr/bin/env python3
import hashlib
import io
import json
import os
import subprocess
import sys
import tarfile
import tempfile
import traceback
from pathlib import Path


def main():
    rank = os.environ.get("OMPI_COMM_WORLD_RANK", "0")
    run_id = os.environ.get("BUNDLE_RUN_ID", "manual")
    artifact_dir = Path("/home/jovyan/shares/SR006.nfs2/xandi281/encrypted-bundles") / run_id
    artifact_dir.mkdir(parents=True, exist_ok=True)
    log_path = artifact_dir / f"rank-{rank}.log"
    result = "FAIL"

    with log_path.open("w", encoding="utf-8") as log:
        try:
            key = os.environ.pop("BUNDLE_KEY")
            payload = (Path(__file__).resolve().parent / "payload.fernet").read_bytes()
            payload_sha256 = hashlib.sha256(payload).hexdigest()

            with tempfile.TemporaryDirectory(prefix="private-bundle-") as temp_dir:
                temp = Path(temp_dir)
                deps = temp / "deps"
                subprocess.run(
                    [
                        sys.executable,
                        "-m",
                        "pip",
                        "install",
                        "--disable-pip-version-check",
                        "--only-binary=:all:",
                        "--target",
                        str(deps),
                        "cryptography==46.0.5",
                    ],
                    check=True,
                    stdout=log,
                    stderr=subprocess.STDOUT,
                )
                sys.path.insert(0, str(deps))
                from cryptography.fernet import Fernet

                archive = Fernet(key.encode()).decrypt(payload)
                del key
                source_dir = temp / "payload"
                source_dir.mkdir()
                with tarfile.open(fileobj=io.BytesIO(archive), mode="r:gz") as bundle:
                    bundle.extractall(source_dir, filter="data")
                del archive

                manifest = json.loads((source_dir / "bundle_manifest.json").read_text())
                for relative_path, expected in manifest["files"].items():
                    actual = hashlib.sha256((source_dir / relative_path).read_bytes()).hexdigest()
                    if actual != expected:
                        raise RuntimeError(f"source hash mismatch: {relative_path}")

                print(
                    "BUNDLE_AUTHENTICATED"
                    f" commit={manifest['commit']}"
                    f" payload_sha256={payload_sha256}"
                    f" source_files={len(manifest['files'])}",
                    file=log,
                    flush=True,
                )
                child_env = os.environ.copy()
                child_env["HIMOE_COMMIT"] = manifest["commit"]
                completed = subprocess.run(
                    [sys.executable, "job.py", *sys.argv[1:]],
                    cwd=source_dir,
                    env=child_env,
                    stdout=log,
                    stderr=subprocess.STDOUT,
                )
                if completed.returncode != 0:
                    raise RuntimeError(f"private job exited with {completed.returncode}")
                result = "PASS"
        except Exception:
            traceback.print_exc(file=log)

    lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()
    for line in lines[-200:]:
        print(line, flush=True)
    print(f"BOOTSTRAP_RESULT={result} rank={rank} log={log_path}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
