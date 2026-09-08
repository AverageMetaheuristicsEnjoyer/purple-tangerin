# Encrypted Python job launcher

The launcher authenticates and decrypts `payload.fernet` with a separately supplied
`BUNDLE_KEY`, extracts it into a temporary directory, and runs its `job.py` entrypoint.
Arguments to `bootstrap.py` are forwarded to `job.py`. Python 3.12 is required.
The temporary source directory is removed when the launcher exits normally.

Encryption uses the standard `cryptography` Fernet implementation. The random key
is not included in this repository. The key is removed from the launcher's Python
environment before dependency installation and is not inherited by the job process.
Never print the key, dump the complete job environment, or use a real key in a
submission tool's dry-run output.

This protects archive contents from public repository readers. It does not protect
running code or keys from administrators of the execution environment. Ciphertext
size, creation timestamp and repository history remain public metadata.
