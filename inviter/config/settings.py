import os
from dataclasses import dataclass
from zoneinfo import ZoneInfo


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


def _get_timezone(name: str, default: str) -> ZoneInfo:
    value = os.getenv(name) or default
    return ZoneInfo(value)


@dataclass(frozen=True)
class Settings:
    api_id: int
    api_hash: str
    session_name: str
    postgres_host: str
    postgres_port: int
    postgres_db: str
    postgres_user: str
    postgres_password: str
    invite_target_chat: str
    invites_per_hour: int
    invite_window_start: int
    invite_window_end: int
    invite_timezone: ZoneInfo

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )


def load_settings() -> Settings:
    invite_window_start = _get_int("INVITE_WINDOW_START", 10)
    invite_window_end = _get_int("INVITE_WINDOW_END", 17)
    if invite_window_start < 0 or invite_window_start > 23:
        raise ValueError("INVITE_WINDOW_START must be 0..23")
    if invite_window_end < 0 or invite_window_end > 24:
        raise ValueError("INVITE_WINDOW_END must be 0..24")
    if invite_window_end <= invite_window_start:
        raise ValueError("INVITE_WINDOW_END must be greater than INVITE_WINDOW_START")

    return Settings(
        api_id=int(_require_env("API_ID")),
        api_hash=_require_env("API_HASH"),
        session_name=_require_env("SESSION_NAME"),
        postgres_host=_require_env("POSTGRES_HOST"),
        postgres_port=_get_int("POSTGRES_PORT", 5432),
        postgres_db=_require_env("POSTGRES_DB"),
        postgres_user=_require_env("POSTGRES_USER"),
        postgres_password=_require_env("POSTGRES_PASSWORD"),
        invite_target_chat=_require_env("INVITE_TARGET_CHAT"),
        invites_per_hour=_get_int("INVITES_PER_HOUR", 2),
        invite_window_start=invite_window_start,
        invite_window_end=invite_window_end,
        invite_timezone=_get_timezone("INVITE_TIMEZONE", "UTC"),
    )
