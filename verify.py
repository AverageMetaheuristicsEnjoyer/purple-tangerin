import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile

root = Path(__file__).resolve().parent
key = os.environ.pop('BUNDLE_KEY').encode()
for name, digest in json.loads((root / 'checksums.json').read_text()).items():
    assert hashlib.sha256((root / name).read_bytes()).hexdigest() == digest, name
with tempfile.TemporaryDirectory(prefix='scientific-bundle-') as temporary:
    deps = Path(temporary) / 'deps'
    subprocess.run([sys.executable, '-m', 'pip', 'install', '--no-cache-dir', '--target', str(deps), 'cryptography==46.0.5'], check=True)
    sys.path.insert(0, str(deps))
    from cryptography.fernet import Fernet
    source = Path(temporary) / 'source'
    source.mkdir()
    with tarfile.open(fileobj=io.BytesIO(Fernet(key).decrypt((root / 'verification.fernet').read_bytes())), mode='r:gz') as archive:
        archive.extractall(source, filter='data')
    env = dict(os.environ, PYTHONPATH=str(deps))
    subprocess.run([sys.executable, str(source / 'worker.py'), *sys.argv[1:]], env=env, check=True)
