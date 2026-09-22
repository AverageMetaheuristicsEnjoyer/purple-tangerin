import io
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile

with tempfile.TemporaryDirectory(prefix="sae-pilot-source-") as temporary:
    root = Path(temporary)
    deps = root / "dependencies"
    subprocess.run([sys.executable, "-m", "pip", "install", "--no-cache-dir", "--target", str(deps), "cryptography==46.0.5"], check=True)
    sys.path.insert(0, str(deps))
    from cryptography.fernet import Fernet
    payload = Path(__file__).with_name("payload.fernet").read_bytes()
    archive = Fernet(os.environ.pop("BUNDLE_KEY").encode()).decrypt(payload)
    source = root / "source"
    source.mkdir()
    with tarfile.open(fileobj=io.BytesIO(archive), mode="r:gz") as bundle:
        bundle.extractall(source, filter="data")
    raise SystemExit(subprocess.run([sys.executable, "job.py"], cwd=source).returncode)
