#!/usr/bin/env python3
"""Bootstrap NASO secrets and a working .env for the dev stack.

Run via ``make bootstrap`` or directly. Idempotent by default — existing
secrets and ``.env`` are left untouched. Use ``--force`` to regenerate.

What it does:

  1. Creates ``.secrets-mock/`` with mode 0700.
  2. Generates an Ed25519 keypair and writes the PEMs to two pairs of files:
       - ``.secrets-mock/JWT_PRIVATE_KEY`` and ``JWT_PUBLIC_KEY`` (no
         extension): consumed by pydantic-settings via ``secrets_dir``.
         The file *name* must equal the env-var *name*.
       - ``.secrets-mock/jwt_private_key.pem`` / ``jwt_public_key.pem``:
         kept for any tool that still expects PEM filenames.
  3. Generates random hex passwords and writes them to:
       - ``db_password.txt``, ``rabbit_password.txt``,
         ``minio_password.txt``, ``elastic_password.txt`` — these are
         consumed by docker-compose ``*_PASSWORD_FILE``.
  4. If ``.env`` does not exist (or ``--force``), copies ``.env.example``
     into ``.env`` and substitutes every remaining ``CHANGE_ME`` with the
     password matching the surrounding key. This is what makes the
     backend (which reads ``DATABASE_URL`` / ``RABBITMQ_PASS`` as plain
     strings, not as file mounts) actually able to authenticate.

The result: ``make bootstrap && make up && make demo`` works on a clean
checkout — no manual editing required.
"""

from __future__ import annotations

import argparse
import os
import re
import secrets
import sys
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519

REPO_ROOT = Path(__file__).resolve().parent.parent
SECRETS_DIR = REPO_ROOT / ".secrets-mock"
ENV_EXAMPLE = REPO_ROOT / ".env.example"
ENV_FILE = REPO_ROOT / ".env"


def _write_secret(path: Path, content: str, mode: int = 0o600) -> None:
    """Write *content* to *path* with the requested mode. Owner-only by default."""
    path.write_text(content)
    os.chmod(path, mode)


def _generate_jwt_keys() -> tuple[str, str]:
    private_key = ed25519.Ed25519PrivateKey.generate()
    public_key = private_key.public_key()
    priv_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("utf-8")
    pub_pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("utf-8")
    return priv_pem, pub_pem


def _populate_secrets(force: bool) -> dict[str, str]:
    """Generate the secrets directory. Returns a dict of password values
    so the .env renderer can reuse the exact same strings.
    """
    SECRETS_DIR.mkdir(mode=0o700, exist_ok=True)
    os.chmod(SECRETS_DIR, 0o700)  # tighten in case the dir already existed

    priv_pem, pub_pem = _generate_jwt_keys()

    # Pydantic-settings reads files whose NAME equals the env-var name when
    # secrets_dir is configured. Keep the legacy *.pem copies too so any
    # ad-hoc tooling that hard-coded those names keeps working.
    targets: dict[str, str] = {
        "JWT_PRIVATE_KEY": priv_pem,
        "JWT_PUBLIC_KEY": pub_pem,
        "jwt_private_key.pem": priv_pem,
        "jwt_public_key.pem": pub_pem,
    }
    passwords: dict[str, str] = {
        "db_password.txt": secrets.token_urlsafe(24),
        "rabbit_password.txt": secrets.token_urlsafe(24),
        "minio_password.txt": secrets.token_urlsafe(24),
        "elastic_password.txt": secrets.token_urlsafe(24),
    }

    for name, content in {**targets, **passwords}.items():
        target = SECRETS_DIR / name
        if target.exists() and not force:
            continue
        _write_secret(target, content)

    return {
        "DB_PASSWORD": (SECRETS_DIR / "db_password.txt").read_text().strip(),
        "RABBIT_PASSWORD": (SECRETS_DIR / "rabbit_password.txt").read_text().strip(),
        "MINIO_PASSWORD": (SECRETS_DIR / "minio_password.txt").read_text().strip(),
        "ELASTIC_PASSWORD": (SECRETS_DIR / "elastic_password.txt").read_text().strip(),
    }


def _render_env(passwords: dict[str, str], force: bool) -> bool:
    """Write .env from .env.example, substituting CHANGE_ME placeholders.

    Returns True iff a new file was written. Refuses to overwrite an
    existing .env unless ``--force`` was passed — operator edits are
    sacred.
    """
    if ENV_FILE.exists() and not force:
        return False
    if not ENV_EXAMPLE.exists():
        raise FileNotFoundError(f".env.example missing at {ENV_EXAMPLE}")

    text = ENV_EXAMPLE.read_text()

    # Keys whose CHANGE_ME placeholder gets replaced by a generated value.
    # We match KEY=CHANGE_ME at line start so we don't accidentally
    # rewrite a comment or an unrelated occurrence.
    substitutions = {
        "DB_PASSWORD": passwords["DB_PASSWORD"],
        "RABBIT_PASSWORD": passwords["RABBIT_PASSWORD"],
        "RABBITMQ_PASS": passwords["RABBIT_PASSWORD"],
        "MINIO_ROOT_PASSWORD": passwords["MINIO_PASSWORD"],
        "MINIO_SECRET_KEY": passwords["MINIO_PASSWORD"],
        "ELASTIC_PASSWORD": passwords["ELASTIC_PASSWORD"],
        "ES_PASSWORD": passwords["ELASTIC_PASSWORD"],
        # 32 random bytes hex — matches the .env.example comment hint.
        "NASO_WEBHOOK_SIGNING_SECRET": secrets.token_hex(32),
    }
    for key, value in substitutions.items():
        text = re.sub(
            rf"^{re.escape(key)}=CHANGE_ME$",
            f"{key}={value}",
            text,
            flags=re.MULTILINE,
        )

    # DATABASE_URL embeds the DB password inline. The example value uses
    # `naso_admin:CHANGE_ME` — replace just that segment.
    text = re.sub(
        r"^(DATABASE_URL=postgresql\+asyncpg://[^:]+:)CHANGE_ME(@.*)$",
        rf"\g<1>{passwords['DB_PASSWORD']}\g<2>",
        text,
        flags=re.MULTILINE,
    )

    ENV_FILE.write_text(text)
    os.chmod(ENV_FILE, 0o600)
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing secrets and .env. Destructive — use with care.",
    )
    args = parser.parse_args()

    os.umask(0o077)
    passwords = _populate_secrets(force=args.force)
    env_written = _render_env(passwords, force=args.force)

    print("[ok] .secrets-mock/ populated")
    if env_written:
        print("[ok] .env created from .env.example with generated passwords")
    else:
        print("[skip] .env exists — left untouched (use --force to regenerate)")
    print("\nNext steps:")
    print("  export NASO_ADMIN_PASSWORD=...")
    print("  make up && make demo")
    return 0


if __name__ == "__main__":
    sys.exit(main())
