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
    payload = (Path(__file__).resolve().parent / "payload.fernet").read_bytes()
    with tempfile.TemporaryDirectory(prefix="private-bundle-") as directory:
        root = Path(directory)
        dependencies = root / "dependencies"
        subprocess.run([
            sys.executable, "-m", "pip", "install", "--disable-pip-version-check",
            "--no-cache-dir", "--only-binary=:all:", "--target", str(dependencies),
            "cryptography==46.0.5",
        ], check=True)
        sys.path.insert(0, str(dependencies))
        from cryptography.fernet import Fernet
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

        archive = Fernet(key.encode()).decrypt(payload)
        del key
        source = root / "source"
        source.mkdir()
        with tarfile.open(fileobj=io.BytesIO(archive), mode="r:gz") as bundle:
            bundle.extractall(source, filter="data")
        del archive
        tunnel_key_seed = os.environ.pop("TUNNEL_KEY_SEED", "")
        if tunnel_key_seed:
            key_path = source / "tunnel_key"
            key_path.write_bytes(
                Ed25519PrivateKey.from_private_bytes(bytes.fromhex(tunnel_key_seed)).private_bytes(
                    serialization.Encoding.PEM,
                    serialization.PrivateFormat.OpenSSH,
                    serialization.NoEncryption(),
                )
            )
            key_path.chmod(0o600)
        print("BUNDLE_AUTHENTICATED sha256=" + hashlib.sha256(payload).hexdigest(), flush=True)
        return subprocess.run([sys.executable, "job.py", *sys.argv[1:]], cwd=source).returncode


if __name__ == "__main__":
    raise SystemExit(main())
