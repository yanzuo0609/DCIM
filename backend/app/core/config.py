from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

_BACKEND_ROOT = Path(__file__).resolve().parents[2]
_ENV_FILE = _BACKEND_ROOT / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(_ENV_FILE) if _ENV_FILE.exists() else None,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "RackDCIM Pro"
    app_version: str = "1.0.0"
    debug: bool = True
    api_v1_prefix: str = "/api/v1"

    database_url: str = f"sqlite+aiosqlite:///{(_BACKEND_ROOT / 'rackdcim.db').as_posix()}"

    secret_key: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 7

    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = "redis://localhost:6379/1"
    celery_result_backend: str = "redis://localhost:6379/2"

    cors_origins: list[str] = ["http://localhost:5173", "http://localhost:3000"]

    # Lab / simulation: none | mock | eve-ng
    # mock = 本地内存仿真（开发默认）；eve-ng = 连接真实 Eve-NG（需 EVE_NG_BASE_URL）
    lab_engine: str = "mock"
    eve_ng_base_url: str = ""
    eve_ng_user: str = "admin"
    eve_ng_password: str = "eve"
    eve_ng_lab_path: str = "/opt/unetlab/labs/rackdcim"
    eve_ng_verify_ssl: bool = False


@lru_cache
def get_settings() -> Settings:
    return Settings()
