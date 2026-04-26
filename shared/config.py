from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "Naso Forensic"
    DATABASE_URL: str = "postgresql+asyncpg://naso:naso@db:5432/naso"

    # JWT EdDSA
    JWT_PRIVATE_KEY: str | None = None
    JWT_PUBLIC_KEY: str | None = None
    ALGORITHM: str = "EdDSA"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    # Standard claims. Issuer ties tokens to this engine; audience ties
    # them to this API surface, so a token minted for a sister service
    # (e.g. an MCP-only signing key reused on the API path) is rejected.
    JWT_ISSUER: str = "naso-forensic-engine"
    JWT_AUDIENCE: str = "naso-api"
    # Clock-skew tolerance for nbf/exp/iat checks (seconds). Tight by
    # default — operators behind NTP shouldn't need more than a few.
    JWT_LEEWAY_SECONDS: int = 10

    # Redis Blacklist
    REDIS_HOST: str = "redis://naso-cache:6379/0"

    # API Security
    ALLOWED_CORS_ORIGINS: str = "http://localhost:5173,http://127.0.0.1:5173,http://localhost:8000"
    # Hosts the API answers to. TrustedHostMiddleware rejects anything else
    # with a 400 — so the prod deployer MUST override this to include the
    # public DNS name. The default keeps dev (localhost / docker) and the
    # two pytest httpx ASGITransport hostnames working out of the box.
    # Example: ALLOWED_HOSTS="naso.example.com,api.naso.example.com"
    ALLOWED_HOSTS: str = "localhost,127.0.0.1,host.docker.internal,naso-api,test,testserver"

    # Elasticsearch
    ES_HOST: str = "elasticsearch"
    ES_PORT: int = 9200
    ES_USER: str | None = None
    ES_PASSWORD: str | None = None
    # Whether the ES client verifies the server certificate. Default True
    # for prod safety; the dev compose ships a self-signed ES cert, so
    # set ES_VERIFY_CERTS=false in dev .env to skip verification there.
    ES_VERIFY_CERTS: bool = True

    # MinIO
    MINIO_ENDPOINT: str = "minio:9000"
    MINIO_ACCESS_KEY: str | None = None
    MINIO_SECRET_KEY: str | None = None
    MINIO_SECURE: bool = False

    # RabbitMQ
    RABBITMQ_HOST: str = "rabbitmq"
    RABBITMQ_USER: str | None = None
    RABBITMQ_PASS: str | None = None

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
    SMTP_USER: str | None = None
    SMTP_PASSWORD: str | None = None
    SMTP_FROM: str = "naso-engine@naso.local"
    ENABLE_NOTIFICATIONS: bool = True

    # Telegram Intelligence (#23)
    TELEGRAM_API_ID: str | None = None
    TELEGRAM_API_HASH: str | None = None
    TELEGRAM_SESSION_NAME: str = "naso_forensic_bot"

    # Shodan Integration
    SHODAN_API_KEY: str | None = None

    model_config = SettingsConfigDict(env_file=".env", secrets_dir="/run/secrets", extra="ignore")


settings = Settings()
