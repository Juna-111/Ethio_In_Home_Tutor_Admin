import os
from typing import Optional, Union
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)


class Settings(BaseSettings):
    DATABASE_URL: str = "sqlite+aiosqlite:///./mentorlink.db"
    BOT_TOKEN: Optional[str] = None
    ADMIN_GROUP_ID: Optional[Union[int, str]] = None
    SUPER_ADMIN_ID: Optional[int] = None
    ADMIN_IDS: list[int] = []
    PARENT_REQUESTS_TOPIC_ID: Optional[int] = None
    TUTOR_REGISTRATION_TOPIC_ID: Optional[int] = None
    WEBAPP_URL: Optional[str] = None
    MINI_APP_URL: Optional[str] = None
    ENVIRONMENT: str = "development"
    ALLOW_UNVERIFIED_WEB_PREVIEW: bool = False

    @field_validator("ADMIN_IDS", mode="before")
    @classmethod
    def parse_admin_ids(cls, v):
        if not v:
            return []
        if isinstance(v, list):
            return [int(x) for x in v if str(x).strip()]
        if isinstance(v, str):
            return [int(x.strip()) for x in v.split(",") if x.strip().isdigit()]
        return []

    @field_validator(
        "PARENT_REQUESTS_TOPIC_ID",
        "TUTOR_REGISTRATION_TOPIC_ID",
        "SUPER_ADMIN_ID",
        mode="before",
    )
    @classmethod
    def empty_str_to_none_int(cls, v):
        if v == "" or v is None:
            return None
        return int(v)

    @field_validator("ADMIN_GROUP_ID", mode="before")
    @classmethod
    def validate_admin_group_id(cls, v):
        if v == "" or v is None:
            return None
        if isinstance(v, str):
            v = v.strip()
            if not v:
                return None
            try:
                return int(v)
            except ValueError:
                return v
        return v

    @field_validator("BOT_TOKEN", mode="before")
    @classmethod
    def sanitize_bot_token(cls, v):
        if v is None:
            return None
        if isinstance(v, str):
            v = v.strip().strip("'\"")
            if not v:
                return None
            return v
        return v

    @field_validator("ALLOW_UNVERIFIED_WEB_PREVIEW", mode="before")
    @classmethod
    def parse_preview_flag(cls, v):
        if isinstance(v, str):
            return v.strip().lower() in ("true", "1", "yes", "t")
        return bool(v)

    @field_validator("MINI_APP_URL", "WEBAPP_URL", mode="before")
    @classmethod
    def sanitize_urls(cls, v):
        if v is None:
            return None
        if isinstance(v, str):
            v = v.strip().strip("'\"")
            if not v:
                return None
            return v.rstrip("/")
        return v

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )


settings = Settings()