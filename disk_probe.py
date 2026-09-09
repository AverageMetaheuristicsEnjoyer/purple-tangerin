#!/usr/bin/env python3
import os
import subprocess
from pathlib import Path


def filesystem(path):
    stats = os.statvfs(path)
    device = os.stat(path).st_dev
    return stats.f_blocks * stats.f_frsize, stats.f_bavail * stats.f_frsize, device


def main():
    candidates = {
        Path("/"),
        Path("/tmp"),
        Path("/home/jovyan"),
        Path("/home/jovyan/data"),
        Path("/home/jovyan/shares"),
    }
    shares = Path("/home/jovyan/shares")
    if shares.is_dir():
        candidates.update(path for path in shares.iterdir() if path.is_dir())

    print("HIMOE_DISK_AUDIT_BEGIN", flush=True)
    for path in sorted(candidates, key=str):
        if not path.exists():
            print(f"FILESYSTEM path={path} exists=false", flush=True)
            continue
        total, available, device = filesystem(path)
        print(
            f"FILESYSTEM path={path} exists=true total_bytes={total}"
            f" available_bytes={available} device={device} writable={os.access(path, os.W_OK)}",
            flush=True,
        )

    owned_roots = []
    if shares.is_dir():
        for share in sorted(shares.iterdir()):
            candidate = share / "xandi281"
            if candidate.is_dir():
                owned_roots.append(candidate)
                total, available, device = filesystem(candidate)
                print(
                    f"OWNED_ROOT path={candidate} total_bytes={total}"
                    f" available_bytes={available} device={device}"
                    f" writable={os.access(candidate, os.W_OK)}",
                    flush=True,
                )

    artifact_root = Path(
        "/home/jovyan/shares/SR006.nfs2/xandi281/encrypted-bundles"
    )
    if artifact_root.is_dir():
        completed = subprocess.run(
            ["du", "-x", "-B1", "--max-depth=1", str(artifact_root)],
            check=True,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        for line in completed.stdout.splitlines():
            print(f"ARTIFACT_DU {line}", flush=True)

    for root in owned_roots:
        print(f"OWNED_CHILDREN root={root}", flush=True)
        for child in sorted(root.iterdir()):
            try:
                stat = child.stat()
            except FileNotFoundError:
                continue
            print(
                f"OWNED_CHILD path={child} type={'dir' if child.is_dir() else 'file'}"
                f" size_bytes={stat.st_size} mtime_ns={stat.st_mtime_ns}",
                flush=True,
            )

    print("HIMOE_DISK_AUDIT_RESULT=PASS", flush=True)


if __name__ == "__main__":
    main()
