#!/usr/bin/env python3
import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tempfile
from urllib.error import HTTPError
from urllib.request import urlopen


def digest_file(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024**2), b""):
            digest.update(block)
    return digest.hexdigest()


def source_manifest(source):
    files = []
    for path in sorted(source.rglob("*")):
        if path.is_symlink():
            raise ValueError("Archive source must not contain symlinks")
        if path.is_file():
            files.append({"path": str(path.relative_to(source)), "bytes": path.stat().st_size,
                          "sha256": digest_file(path)})
    if not files:
        raise ValueError("Archive source is empty")
    return json.dumps({"files": files}, sort_keys=True, indent=2).encode()


def verify_archive(path, key, manifest):
    from cryptography.fernet import Fernet

    plaintext = Fernet(key).decrypt(path.read_bytes())
    with tarfile.open(fileobj=io.BytesIO(plaintext), mode="r:gz") as archive:
        assert archive.extractfile("archive_manifest.json").read() == manifest
        files = json.loads(manifest)["files"]
        assert sorted(member.name for member in archive) == sorted(["archive_manifest.json", *["run/" + row["path"] for row in files]])
        for row in files:
            member = archive.getmember("run/" + row["path"])
            assert member.isfile() and member.size == row["bytes"]
            digest = hashlib.sha256()
            with archive.extractfile(member) as stream:
                for block in iter(lambda: stream.read(8 * 1024**2), b""):
                    digest.update(block)
            assert digest.hexdigest() == row["sha256"], row["path"]


def make_archive(source, output, key, manifest):
    from cryptography.fernet import Fernet

    with tempfile.TemporaryFile() as compressed:
        with tarfile.open(fileobj=compressed, mode="w:gz") as archive:
            member = tarfile.TarInfo("archive_manifest.json")
            member.size = len(manifest)
            archive.addfile(member, io.BytesIO(manifest))
            for row in json.loads(manifest)["files"]:
                archive.add(source / row["path"], arcname="run/" + row["path"], recursive=False)
        compressed.seek(0)
        output.write_bytes(Fernet(key).encrypt(compressed.read()))
    verify_archive(output, key, manifest)


def archive_source(source, repo, prefix, receipts, key, token, temporary):
    from huggingface_hub import CommitOperationAdd, HfApi

    manifest = source_manifest(source)
    manifest_hash = hashlib.sha256(manifest).hexdigest()
    remote = prefix.strip("/") + "/" + source.name
    api = HfApi(token=token)
    commit = api.model_info(repo).sha
    base = f"https://huggingface.co/{repo}/resolve/{commit}/{remote}"
    try:
        with urlopen(base + "/checksums.json", timeout=60) as response:
            checksums = json.load(response)
    except HTTPError as error:
        if error.code != 404:
            raise
        checksums = None
    archive = temporary / "resume.fernet"
    if checksums is None:
        source_bytes = sum(row["bytes"] for row in json.loads(manifest)["files"])
        if shutil.disk_usage(temporary).free < 4 * source_bytes + 1024**3:
            raise RuntimeError("Insufficient ephemeral space for archive and verification copies")
        make_archive(source, archive, key, manifest)
        checksums = {"format": "Fernet authenticated tar.gz; key supplied separately",
                     "manifest_sha256": manifest_hash, "bytes": archive.stat().st_size,
                     "sha256": digest_file(archive)}
        result = api.create_commit(repo_id=repo, operations=[
            CommitOperationAdd(path_in_repo=remote + "/resume.fernet", path_or_fileobj=str(archive)),
            CommitOperationAdd(path_in_repo=remote + "/checksums.json", path_or_fileobj=json.dumps(checksums, indent=2).encode())],
            commit_message="Archive completed research checkpoint snapshot")
        commit = result.oid
        base = f"https://huggingface.co/{repo}/resolve/{commit}/{remote}"
    elif checksums["manifest_sha256"] != manifest_hash:
        raise ValueError("Existing HF snapshot differs; refusing to overwrite it")
    downloaded = temporary / "downloaded.fernet"
    with urlopen(base + "/resume.fernet", timeout=300) as response, downloaded.open("wb") as stream:
        shutil.copyfileobj(response, stream, 8 * 1024**2)
    assert downloaded.stat().st_size == checksums["bytes"]
    assert digest_file(downloaded) == checksums["sha256"]
    verify_archive(downloaded, key, manifest)
    if source_manifest(source) != manifest:
        raise ValueError("Source changed during archival; no verified receipt written")
    files = json.loads(manifest)["files"]
    receipt = {"status": "VERIFIED", "repo": repo, "prefix": remote, "commit": commit,
               "source": str(source), "files": len(files), "source_bytes": sum(row["bytes"] for row in files),
               "anonymous_download_sha256": checksums["sha256"], "manifest_sha256": manifest_hash,
               "decrypt_and_all_internal_hashes": "PASS", "originals_deleted": False,
               "source_filesystem_free_bytes": shutil.disk_usage(source).free}
    receipts.mkdir(parents=True, exist_ok=True)
    (receipts / (source.name + ".json")).write_text(json.dumps(receipt, indent=2) + "\n")
    print("HF_ARCHIVE_RESULT=" + json.dumps(receipt), flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, action="append", required=True)
    parser.add_argument("--repo")
    parser.add_argument("--prefix")
    parser.add_argument("--receipts", type=Path)
    parser.add_argument("--inventory", action="store_true")
    parser.add_argument("--install-deps", action="store_true")
    args = parser.parse_args()
    os.umask(0o077)
    sources = [path.resolve(strict=True) for path in args.source]
    if args.inventory:
        for source in sources:
            files = [path for path in source.rglob("*") if path.is_file()]
            print("DISK_INVENTORY=" + json.dumps({"source": str(source), "files": len(files),
                  "source_bytes": sum(path.stat().st_size for path in files),
                  "filesystem_free_bytes": shutil.disk_usage(source).free}), flush=True)
        return
    if not all([args.repo, args.prefix, args.receipts]):
        parser.error("Archive mode requires --repo, --prefix and --receipts")
    key = os.environ.pop("ARCHIVE_KEY").encode()
    token = os.environ.pop("HF_TOKEN")
    os.environ["HF_HUB_DISABLE_IMPLICIT_TOKEN"] = "1"
    if len({source.name for source in sources}) != len(sources):
        raise ValueError("Source basenames must be unique within this archive batch")
    if any(args.receipts.resolve().is_relative_to(source) for source in sources):
        raise ValueError("Receipts must be outside archived sources")
    with tempfile.TemporaryDirectory(prefix="checkpoint-archive-") as directory:
        temporary = Path(directory)
        os.environ["HF_HOME"] = str(temporary / "hf")
        if args.install_deps:
            dependencies = temporary / "dependencies"
            subprocess.run([sys.executable, "-m", "pip", "install", "--no-cache-dir", "--target", str(dependencies),
                            "cryptography==46.0.5", "huggingface-hub==1.30.0"], check=True)
            sys.path.insert(0, str(dependencies))
        for source in sources:
            archive_source(source, args.repo, args.prefix, args.receipts, key, token, temporary)


if __name__ == "__main__":
    main()
