#!/usr/bin/env python3
"""Generate the local development secrets mounted at /run/secrets.

Permissions matter here and are not arbitrary. The API and worker containers
run with ``cap_drop: ALL``. Root's ability to ignore file permissions comes
from CAP_DAC_OVERRIDE and CAP_DAC_READ_SEARCH, so once those are dropped the
container's root is subject to ordinary DAC checks like any other user — and
its uid 0 does not match the host user that ran this script.

A 0700 directory therefore made ``/run/secrets`` unlistable inside the
container, and every process died at import with

    PermissionError: [Errno 13] Permission denied: '/run/secrets'

because pydantic-settings lists that directory once per settings field. This
never reproduced on macOS, where Docker Desktop's file sharing presents host
files as owned by the container user.

The modes below mirror what Docker itself does when it mounts real secrets:
a world-traversable directory containing world-readable, non-writable files.
This is a local mock for the development stack, not a production secret
store — see SECURITY.md.
"""

import os
import secrets

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519

SECRETS_DIR = ".secrets-mock"

# Docker mounts real secrets as 0444 files under a 0755 mount point.
DIR_MODE = 0o755
FILE_MODE = 0o444


def create_secret(name, content):
    path = os.path.join(SECRETS_DIR, name)
    with open(path, "w") as f:
        f.write(content)
    # Set explicitly rather than relying on the umask, which the caller's
    # shell controls and which cannot widen a mode anyway.
    os.chmod(path, FILE_MODE)


def main():
    os.makedirs(SECRETS_DIR, exist_ok=True)
    # makedirs does not touch the mode of a directory that already exists.
    os.chmod(SECRETS_DIR, DIR_MODE)

    # 1. Generate the Ed25519 (EdDSA) key pair
    private_key = ed25519.Ed25519PrivateKey.generate()
    public_key = private_key.public_key()

    priv_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    pub_pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM, format=serialization.PublicFormat.SubjectPublicKeyInfo
    )

    create_secret("jwt_private_key.pem", priv_pem.decode("utf-8"))
    create_secret("jwt_public_key.pem", pub_pem.decode("utf-8"))

    # 2. Generate hardened passwords
    create_secret("db_password.txt", secrets.token_urlsafe(24))
    create_secret("rabbit_password.txt", secrets.token_urlsafe(24))
    create_secret("minio_password.txt", secrets.token_urlsafe(24))
    create_secret("elastic_password.txt", secrets.token_urlsafe(24))

    print(f"Development secrets generated in {SECRETS_DIR}/ (dir 0755, files 0444).")


if __name__ == "__main__":
    main()
