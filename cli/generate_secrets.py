#!/usr/bin/env python3
import os
import secrets

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519


def create_secret(path, content):
    with open(path, "w") as f:
        f.write(content)


def main():
    # Sicurezza Draconiana: garantiamo che i permessi siano limitati
    os.umask(0o077)
    os.makedirs(".secrets-mock", exist_ok=True)

    # 1. Generazione End-to-End Ed25519 (EdDSA)
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

    create_secret(".secrets-mock/jwt_private_key.pem", priv_pem.decode("utf-8"))
    create_secret(".secrets-mock/jwt_public_key.pem", pub_pem.decode("utf-8"))

    # 2. Generazione Hardened Passwords
    create_secret(".secrets-mock/db_password.txt", secrets.token_urlsafe(24))
    create_secret(".secrets-mock/rabbit_password.txt", secrets.token_urlsafe(24))
    create_secret(".secrets-mock/minio_password.txt", secrets.token_urlsafe(24))
    create_secret(".secrets-mock/elastic_password.txt", secrets.token_urlsafe(24))

    print("SOTA Secrets Mock generated successfully in .secrets-mock/")


if __name__ == "__main__":
    main()
