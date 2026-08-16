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
ENV_FILE = ".env"
ENV_TEMPLATE = ".env.example"

# Docker mounts real secrets as 0444 files under a 0755 mount point.
DIR_MODE = 0o755
FILE_MODE = 0o444
# Elasticsearch validates the mode of its own password file and accepts only
# 400 or 600. See the comment at the call site.
ES_FILE_MODE = 0o600


def create_secret(name, content, mode=FILE_MODE):
    path = os.path.join(SECRETS_DIR, name)
    with open(path, "w") as f:
        f.write(content)
    # Set explicitly rather than relying on the umask, which the caller's
    # shell controls and which cannot widen a mode anyway.
    os.chmod(path, mode)


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

    # The *.pem names are for humans. pydantic-settings resolves secrets_dir
    # entries by settings-field name, so the application only picks these up
    # from files named exactly after the fields.
    create_secret("jwt_private_key.pem", priv_pem.decode("utf-8"))
    create_secret("jwt_public_key.pem", pub_pem.decode("utf-8"))
    create_secret("JWT_PRIVATE_KEY", priv_pem.decode("utf-8"))
    create_secret("JWT_PUBLIC_KEY", pub_pem.decode("utf-8"))

    # 2. Generate hardened passwords. The *.txt names are the ones
    # docker-compose.yml references in its top-level `secrets:` block.
    passwords = {
        "db": secrets.token_urlsafe(24),
        "rabbit": secrets.token_urlsafe(24),
        "minio": secrets.token_urlsafe(24),
        "elastic": secrets.token_urlsafe(24),
    }
    create_secret("db_password.txt", passwords["db"])
    create_secret("rabbit_password.txt", passwords["rabbit"])
    create_secret("minio_password.txt", passwords["minio"])
    # Elasticsearch is the exception, and it is not negotiable: its entrypoint
    # refuses to start with
    #   "File /run/secrets/elastic_password from ELASTIC_PASSWORD_FILE must
    #    have file permissions 400 or 600, but actually has: 444"
    # and crash-loops. 0444 is right for every other secret here -- the
    # application containers run cap_drop: ALL, have no CAP_DAC_OVERRIDE, and
    # so cannot read a file they do not own -- but the Elasticsearch container
    # keeps its capabilities and starts as root, so it can read 0600 whoever
    # owns it. Nothing else reads this file: the API and the workers take
    # ES_PASSWORD from .env, not from /run/secrets, because pydantic-settings
    # matches secret files by field name and this one is elastic_password.
    create_secret("elastic_password.txt", passwords["elastic"], mode=ES_FILE_MODE)

    print(f"Development secrets generated in {SECRETS_DIR}/ (dir 0755, files 0444; elastic_password 0600).")
    write_env(passwords)


def write_env(passwords):
    """Render .env from .env.example with the generated values filled in.

    Without this the two halves disagree: Postgres, Elasticsearch and MinIO are
    provisioned from the generated secret files, while the application reads
    DATABASE_URL and friends from .env — which ships CHANGE_ME. The API then
    starts, answers 200, and reports {"status": "degraded"} forever because
    every database connection fails authentication.

    An existing .env is never modified; this only fills in a fresh one.
    """
    if os.path.exists(ENV_FILE):
        print(f"{ENV_FILE} already exists, leaving it untouched.")
        return
    if not os.path.exists(ENV_TEMPLATE):
        print(f"{ENV_TEMPLATE} not found, skipping {ENV_FILE} generation.")
        return

    replacements = {
        "DB_PASSWORD": passwords["db"],
        "ELASTIC_PASSWORD": passwords["elastic"],
        "ES_PASSWORD": passwords["elastic"],
        "RABBIT_PASSWORD": passwords["rabbit"],
        "RABBITMQ_PASS": passwords["rabbit"],
        "MINIO_ROOT_PASSWORD": passwords["minio"],
        "MINIO_SECRET_KEY": passwords["minio"],
        "NASO_WEBHOOK_SIGNING_SECRET": secrets.token_hex(32),
        "NASO_ADMIN_PASSWORD": secrets.token_urlsafe(18),
    }
    # .env wins over secrets_dir in pydantic-settings, so an empty
    # JWT_PRIVATE_KEY= line here would shadow the file in /run/secrets.
    commented = {"JWT_PRIVATE_KEY", "JWT_PUBLIC_KEY"}

    with open(ENV_TEMPLATE, encoding="utf-8") as f:
        template_lines = f.read().splitlines()

    out = []
    for line in template_lines:
        stripped = line.lstrip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            out.append(line)
            continue
        key = stripped.split("=", 1)[0].strip()
        if key in commented:
            out.append(f"# {line}  # provided via /run/secrets/{key}")
        elif key in replacements:
            out.append(f"{key}={replacements[key]}")
        elif "CHANGE_ME" in line:
            # DATABASE_URL embeds the password inside a connection string.
            out.append(line.replace("CHANGE_ME", passwords["db"]))
        else:
            out.append(line)

    with open(ENV_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(out) + "\n")
    os.chmod(ENV_FILE, 0o600)
    print(f"{ENV_FILE} written from {ENV_TEMPLATE} with the generated values (0600).")


if __name__ == "__main__":
    main()
