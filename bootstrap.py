import hashlib
import io
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile


def main():
    os.umask(0o077)
    key = os.environ.pop("BUNDLE_KEY")
    hf_token = os.environ.pop("HF_TOKEN")
    payload = (Path(__file__).resolve().parent / "payload.fernet").read_bytes()
    with tempfile.TemporaryDirectory(prefix="private-bundle-") as directory:
        root = Path(directory)
        dependencies = root / "dependencies"
        subprocess.run([
            sys.executable, "-m", "pip", "install", "--disable-pip-version-check",
            "--no-cache-dir", "--only-binary=:all:", "--target", str(dependencies),
            "cryptography==46.0.5",
            "huggingface-hub==1.30.0",
        ], check=True)
        sys.path.insert(0, str(dependencies))
        from cryptography.fernet import Fernet

        archive = Fernet(key.encode()).decrypt(payload)
        del key
        source = root / "source"
        source.mkdir()
        with tarfile.open(fileobj=io.BytesIO(archive), mode="r:gz") as bundle:
            bundle.extractall(source, filter="data")
        del archive
        print("BUNDLE_AUTHENTICATED sha256=" + hashlib.sha256(payload).hexdigest(), flush=True)
        job_environment = dict(os.environ)
        job_environment["HF_TOKEN"] = hf_token
        return subprocess.run([sys.executable, "job.py", *sys.argv[1:]], cwd=source,
                              env=job_environment).returncode


if __name__ == "__main__":
    raise SystemExit(main())
