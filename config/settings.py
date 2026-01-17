import os
from dataclasses import dataclass


def _require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise ValueError(f"Missing required env var: {name}")
    return value


def _get_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None or value == "":
        return default
    return int(value)


@dataclass(frozen=True)
class Settings:
    api_id: int
    api_hash: str
    session_name: str
    target_chat_names: list[str]
    postgres_host: str
    postgres_port: int
    postgres_db: str
    postgres_user: str
    postgres_password: str
    analysis_days: int
    min_messages: int

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )


def load_settings() -> Settings:
    target_raw = _require_env("TARGET_CHAT_NAMES")
    target_names = [name.strip() for name in target_raw.split(",") if name.strip()]
    if not target_names:
        raise ValueError("TARGET_CHAT_NAMES must contain at least one chat name")

    return Settings(
        api_id=int(_require_env("API_ID")),
        api_hash=_require_env("API_HASH"),
        session_name=_require_env("SESSION_NAME"),
        target_chat_names=target_names,
        postgres_host=_require_env("POSTGRES_HOST"),
        postgres_port=_get_int("POSTGRES_PORT", 5432),
        postgres_db=_require_env("POSTGRES_DB"),
        postgres_user=_require_env("POSTGRES_USER"),
        postgres_password=_require_env("POSTGRES_PASSWORD"),
        analysis_days=_get_int("ANALYSIS_DAYS", 7),
        min_messages=_get_int("MIN_MESSAGES", 100),
    )
