from typing import Literal
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Core
    APP_NAME: str = "repoAnalyzer"
    ENVIRONMENT: Literal["development", "staging", "production"] = "development"
    DEBUG: bool = True
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # Agent Model
    DEFAULT_MODEL: str = "gemini-3.8-flash-medium"


    # CORS
    CORS_ORIGINS: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]

    # Database (SQLAlchemy 2.0)
    DATABASE_URL: str = "sqlite+aiosqlite:///./repo_analyzer.db"

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # Message Queue (RabbitMQ / NATS / Kafka)
    RABBITMQ_URL: str = "amqp://guest:guest@localhost:5672/"

    # Observability
    OTEL_SERVICE_NAME: str = "repoAnalyzer"
    PROMETHEUS_METRICS_ENABLED: bool = True


settings = Settings()
