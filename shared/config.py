from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    PROJECT_NAME: str = "Naso Forensic"
    DATABASE_URL: str
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    
    # Elasticsearch
    ES_HOST: str = "elasticsearch"
    ES_PORT: int = 9200
    ES_USER: Optional[str] = None
    ES_PASSWORD: str
    
    # MinIO
    MINIO_ENDPOINT: str = "minio:9000"
    MINIO_ACCESS_KEY: str
    MINIO_SECRET_KEY: str
    MINIO_SECURE: bool = False
    
    # RabbitMQ
    RABBITMQ_HOST: str = "rabbitmq"
    RABBITMQ_USER: str
    RABBITMQ_PASS: str
    
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
    SMTP_USER: str
    SMTP_PASSWORD: str
    SMTP_FROM: str = "naso-engine@naso.local"
    ENABLE_NOTIFICATIONS: bool = True

    # Telegram Intelligence (#23)
    TELEGRAM_API_ID: Optional[str] = None
    TELEGRAM_API_HASH: Optional[str] = None
    TELEGRAM_SESSION_NAME: str = "naso_forensic_bot"

    class Config:
        env_file = ".env"
        extra = "ignore"

settings = Settings()
