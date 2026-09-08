# Encrypted Cloud launcher

This branch contains only a generic launcher and an authenticated Fernet ciphertext.
The decryption key is supplied separately at job submission and is not stored in Git.
The launcher removes the key from its environment before dependency installation and
does not pass it to the private subprocess.

This protects the payload from public GitHub readers. It does not protect it from the
Cloud runtime, Cloud administrators, or gateway administrators involved in submission.
Repository history also exposes ciphertext sizes and publication times.
