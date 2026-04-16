from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    PROJECT_NAME: str = "Naso Forensic"
    DATABASE_URL: str = "postgresql+asyncpg://naso_admin:rigorous_admin_password_2026@db:5432/naso_db"
    SECRET_KEY: str = "PROD_SECRET_KEY_REQUIRED_FOR_SECURITY"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    
    # Elasticsearch
    ES_HOST: str = "elasticsearch"
    ES_PORT: int = 9200
    ES_USER: Optional[str] = None
    ES_PASSWORD: Optional[str] = "rigorous_admin_password_2026"
    
    # MinIO
    MINIO_ENDPOINT: str = "minio:9000"
    MINIO_ACCESS_KEY: str = "naso_storage_admin"
    MINIO_SECRET_KEY: str = "rigorous_admin_password_2026"
    MINIO_SECURE: bool = False
    
    # RabbitMQ
    RABBITMQ_HOST: str = "rabbitmq"
    RABBITMQ_USER: str = "naso_broker_admin"
    RABBITMQ_PASS: str = "rigorous_admin_password_2026"
    
    # System Performance Constants
    DB_POOL_SIZE: int = 20
    DB_MAX_OVERFLOW: int = 10
    API_TIMEOUT_SECONDS: int = 60
    
    # Forensic Constants
    DEFAULT_SEVERITY_SCORE: int = 0
    MAX_SEVERITY_SCORE: int = 100
    CRITICAL_SCORE_THRESHOLD: int = 80
    
    # Local AI - Gemma 4 Elite
    AI_ENDPOINT: str = "http://host.docker.internal:1234/v1"
    AI_MODEL: str = "google/gemma-4-E2B-it"
    AI_ENABLE_THINKING: bool = True

    # SMTP / Notifications (#9)
    SMTP_HOST: str = "smtp.naso.local"
    SMTP_PORT: int = 587
    SMTP_USER: str = "notifications@naso.local"
    SMTP_PASSWORD: str = "rigorous_admin_password_2026"
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
