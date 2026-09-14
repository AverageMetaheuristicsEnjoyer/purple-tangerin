import base64
import binascii
import hashlib
import hmac
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tempfile
from urllib.request import urlopen


REPO = "AverageMetaheuristicsEnjoyer/silver-pomelo"
COMMIT = "11fe7efee69d2b6c6e36f4d89a95ed2a42064074"
CELL = "multilabel-v2-user-only-qwen3-2507-prefix-projected-m100-s42-lr3e-5"
PREFIX = "civil-v2-user-only-peft-lr-screen-v26/" + CELL
EXPECTED = {
    "manifest_sha256": "cc51a2a562d2014f25d41902398c428473d05d35fe43c7d7db103dabd59dd688",
    "bytes": 4161167160,
    "sha256": "27874a6741772d9aa9306a67fa8505a09831e08f37826d0929ddcfee98982e98",
}
CHUNK = 4 * 1024**2


def digest(path):
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(CHUNK), b""):
            value.update(block)
    return value.hexdigest()


def decrypt(encoded, output, key):
    raw_key = base64.b64decode(key, altchars=b"-_", validate=True)
    if len(raw_key) != 32:
        raise ValueError("Invalid Fernet key")
    from cryptography.exceptions import InvalidSignature
    from cryptography.hazmat.primitives import padding
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

    with tempfile.TemporaryFile(dir=output.parent) as decoded:
        with encoded.open("rb") as stream:
            try:
                for block in iter(lambda: stream.read(CHUNK), b""):
                    decoded.write(base64.b64decode(block, altchars=b"-_", validate=True))
            except binascii.Error as error:
                raise InvalidSignature from error
        size = decoded.tell()
        decoded.seek(0)
        header = decoded.read(25)
        ciphertext_size = size - 25 - 32
        if len(header) != 25 or header[0] != 0x80 or ciphertext_size < 16 or ciphertext_size % 16:
            raise InvalidSignature
        decoded.seek(0)
        signature = hmac.new(raw_key[:16], digestmod=hashlib.sha256)
        remaining = size - 32
        while remaining:
            block = decoded.read(min(CHUNK, remaining))
            signature.update(block)
            remaining -= len(block)
        if not hmac.compare_digest(signature.digest(), decoded.read(32)):
            raise InvalidSignature
        decoded.seek(25)
        decryptor = Cipher(algorithms.AES(raw_key[16:]), modes.CBC(header[9:25])).decryptor()
        unpadder = padding.PKCS7(128).unpadder()
        with output.open("xb") as stream:
            remaining = ciphertext_size
            while remaining:
                block = decoded.read(min(CHUNK, remaining))
                stream.write(unpadder.update(decryptor.update(block)))
                remaining -= len(block)
            stream.write(unpadder.update(decryptor.finalize()))
            stream.write(unpadder.finalize())


def main():
    key = os.environ.pop("ARCHIVE_KEY").encode()
    base = f"https://huggingface.co/{REPO}/resolve/{COMMIT}/{PREFIX}"
    with tempfile.TemporaryDirectory(prefix="p004-archive-verify-") as directory:
        temporary = Path(directory)
        dependencies = temporary / "dependencies"
        subprocess.run([sys.executable, "-m", "pip", "install", "--no-cache-dir", "--target", str(dependencies),
                        "cryptography==46.0.5"], check=True)
        sys.path.insert(0, str(dependencies))
        with urlopen(base + "/checksums.json", timeout=60) as response:
            checksums = json.load(response)
        if checksums != {"format": "Fernet authenticated tar.gz; key supplied separately", **EXPECTED}:
            raise ValueError("Immutable checksums differ")
        encoded = temporary / "resume.fernet"
        for attempt in range(3):
            try:
                with urlopen(base + "/resume.fernet", timeout=900) as response, encoded.open("wb") as stream:
                    shutil.copyfileobj(response, stream, CHUNK)
                break
            except TimeoutError:
                encoded.unlink(missing_ok=True)
                if attempt == 2:
                    raise
        if encoded.stat().st_size != EXPECTED["bytes"] or digest(encoded) != EXPECTED["sha256"]:
            raise ValueError("Downloaded archive checksum mismatch")
        compressed = temporary / "resume.tar.gz"
        decrypt(encoded, compressed, key)
        with tarfile.open(compressed, "r:gz") as archive:
            manifest = archive.extractfile("archive_manifest.json").read()
            if hashlib.sha256(manifest).hexdigest() != EXPECTED["manifest_sha256"]:
                raise ValueError("Authenticated manifest differs")
            rows = json.loads(manifest)["files"]
            expected_names = {"archive_manifest.json", *["run/" + row["path"] for row in rows]}
            members = archive.getmembers()
            if {member.name for member in members} != expected_names or not all(member.isfile() for member in members):
                raise ValueError("Unexpected archive members")
            for row in rows:
                value = hashlib.sha256()
                with archive.extractfile("run/" + row["path"]) as stream:
                    for block in iter(lambda: stream.read(CHUNK), b""):
                        value.update(block)
                if value.hexdigest() != row["sha256"]:
                    raise ValueError("Internal file hash mismatch: " + row["path"])
        receipt = {"status": "VERIFIED", "repo": REPO, "prefix": PREFIX, "commit": COMMIT,
                   "source": "/tmp/revision-matrix-output/civil-v2-user-only-peft-lr-screen-v26/runs/" + CELL,
                   "files": len(rows), "source_bytes": sum(row["bytes"] for row in rows),
                   "anonymous_download_sha256": EXPECTED["sha256"],
                   "manifest_sha256": EXPECTED["manifest_sha256"],
                   "decrypt_and_all_internal_hashes": "PASS", "originals_deleted": False}
        receipts = Path("/home/jovyan/shares/SR006.nfs1/xandi281/moe-revision-20260908/hf-receipts-v26-lr-screen")
        receipts.mkdir(parents=True, exist_ok=True)
        (receipts / (CELL + ".json")).write_text(json.dumps(receipt, indent=2) + "\n")
        print("HF_ARCHIVE_RESULT=" + json.dumps(receipt), flush=True)


if __name__ == "__main__":
    main()
