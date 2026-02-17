"""Конфигурация приложения."""
from functools import lru_cache
from pydantic_settings import BaseSettings
from pydantic import ConfigDict


class Settings(BaseSettings):
    model_config = ConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")
    app_env: str = "development"
    secret_key: str = "dev-secret-change-in-production"
    debug: bool = True
    public_base_url: str | None = None

    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "teachbaseai"
    postgres_user: str = "teachbaseai"
    postgres_password: str = "changeme"

    redis_host: str = "localhost"
    redis_port: int = 6379

    bitrix_client_id: str = ""
    bitrix_client_secret: str = ""
    bitrix_app_client_id: str = ""
    bitrix_app_client_secret: str = ""

    token_encryption_key: str = ""  # min 32 chars для шифрования токенов порталов

    admin_default_email: str = "admin@localhost"
    admin_default_password: str = "changeme"

    jwt_secret: str = "your-jwt-secret-min-32-chars"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60

    debug_endpoints_enabled: bool = False
    kb_storage_path: str = "/app/storage/kb"
    token_refresh_enabled: bool = True
    token_refresh_interval_minutes: int = 30
    kb_watchdog_enabled: bool = True
    kb_watchdog_interval_seconds: int = 120
    kb_processing_stale_seconds: int = 600
    kb_watchdog_batch_limit: int = 200
    kb_job_timeout_seconds: int = 3600
    rq_ingest_queue_name: str = "ingest"
    rq_outbox_queue_name: str = "outbox"
    kb_pgvector_enabled: bool = False


@lru_cache
def get_settings() -> Settings:
    return Settings()
