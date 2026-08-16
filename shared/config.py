from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "Naso Forensic"
    DATABASE_URL: str = "postgresql+asyncpg://naso:naso@db:5432/naso"

    # JWT EdDSA
    JWT_PRIVATE_KEY: Optional[str] = None
    JWT_PUBLIC_KEY: Optional[str] = None
    ALGORITHM: str = "EdDSA"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    # Issuer and audience are asserted on every token and verified on every
    # decode. Without them a token minted by any other service that happens to
    # share this key pair would be accepted here, and a NASO token would be
    # replayable against a sibling deployment. Override both when you run more
    # than one instance.
    JWT_ISSUER: str = "naso"
    JWT_AUDIENCE: str = "naso-api"
    # Tolerance for clock skew between whatever mints the token and whatever
    # validates it, applied to exp/nbf/iat. Seconds.
    JWT_LEEWAY_SECONDS: int = 30

    # Redis Blacklist
    REDIS_HOST: str = "redis://naso-cache:6379/0"

    # API Security
    ALLOWED_CORS_ORIGINS: str = "http://localhost:5173,http://127.0.0.1:5173,http://localhost:8000"

    # Elasticsearch
    ES_HOST: str = "elasticsearch"
    ES_PORT: int = 9200
    ES_USER: Optional[str] = None
    ES_PASSWORD: Optional[str] = None
    # Defaults to verifying, so a deployment that says nothing gets the safe
    # behaviour. The development stack runs Elasticsearch with a self-signed
    # certificate and opts out explicitly in .env.example — an opt-out you can
    # see beats a default you cannot.
    ES_VERIFY_CERTS: bool = True

    # MinIO
    MINIO_ENDPOINT: str = "minio:9000"
    MINIO_ACCESS_KEY: Optional[str] = None
    MINIO_SECRET_KEY: Optional[str] = None
    MINIO_SECURE: bool = False

    # RabbitMQ
    RABBITMQ_HOST: str = "rabbitmq"
    RABBITMQ_USER: Optional[str] = None
    RABBITMQ_PASS: Optional[str] = None

    # System Performance Constants
    DB_POOL_SIZE: int = 20
    DB_MAX_OVERFLOW: int = 10
    API_TIMEOUT_SECONDS: int = 60

    # Forensic Constants
    DEFAULT_SEVERITY_SCORE: int = 0
    MAX_SEVERITY_SCORE: int = 100
    CRITICAL_SCORE_THRESHOLD: int = 80

    # Local AI — LM Studio / Ollama (OpenAI-compatible)
    # When running backend in Docker, use host.docker.internal:1234
    # When running locally, use localhost:1234
    AI_ENDPOINT: str = "http://localhost:1234/v1"
    AI_MODEL: str = "gemma-4-e2b-it"
    AI_ENABLE_THINKING: bool = False

    # SMTP / Notifications (#9)
    SMTP_HOST: str = "smtp.naso.local"
    SMTP_PORT: int = 587
    SMTP_USER: Optional[str] = None
    SMTP_PASSWORD: Optional[str] = None
    SMTP_FROM: str = "naso-engine@naso.local"
    ENABLE_NOTIFICATIONS: bool = True

    # Telegram Intelligence (#23)
    TELEGRAM_API_ID: Optional[str] = None
    TELEGRAM_API_HASH: Optional[str] = None
    TELEGRAM_SESSION_NAME: str = "naso_forensic_bot"

    # Shodan Integration
    SHODAN_API_KEY: Optional[str] = None

    model_config = SettingsConfigDict(env_file=".env", secrets_dir="/run/secrets", extra="ignore")


settings = Settings()
