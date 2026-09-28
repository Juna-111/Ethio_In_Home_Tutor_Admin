import os
from typing import Literal, Optional, Union
from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)


class Settings(BaseSettings):
    DATABASE_URL: str = "sqlite+aiosqlite:///./mentorlink.db"
    BOT_TOKEN: Optional[str] = None
    BOT_MODE: Literal["polling", "webhook"] = "polling"
    WEBHOOK_URL: Optional[str] = None
    WEBHOOK_SECRET: Optional[str] = None
    ADMIN_GROUP_ID: Optional[Union[int, str]] = None
    SUPER_ADMIN_ID: Optional[int] = None
    ADMIN_IDS: list[int] = Field(default_factory=list)
    PARENT_REQUESTS_TOPIC_ID: Optional[int] = None
    TUTOR_REGISTRATION_TOPIC_ID: Optional[int] = None
    WEBAPP_URL: Optional[str] = None
    MINI_APP_URL: Optional[str] = None
    ADMIN_MINI_APP_SHORT_NAME: Optional[str] = None
    # How "Review in App" buttons open the admin app: "direct" (t.me/<bot>/<app>?startapp=),
    # "bot" (t.me/<bot>?start=review_..., the bot replies with a Mini App button; always works),
    # or "both" (two buttons; default). Direct links can be resolved by Telegram to the bot chat.
    ADMIN_REVIEW_LINK_MODE: str = "both"
    CORS_EXTRA_ORIGINS: Optional[str] = None
    ENVIRONMENT: str = "development"
    ALLOW_UNVERIFIED_WEB_PREVIEW: bool = False
    CRON_SECRET: Optional[str] = None

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

    @field_validator("WEBHOOK_URL", "WEBHOOK_SECRET", mode="before")
    @classmethod
    def sanitize_webhook_settings(cls, v):
        if v is None:
            return None
        if isinstance(v, str):
            v = v.strip().strip("'\"")
            return v or None
        return v

    @model_validator(mode="after")
    def validate_runtime_settings(self):
        if self.ENVIRONMENT.lower() == "production" and self.ALLOW_UNVERIFIED_WEB_PREVIEW:
            raise ValueError("ALLOW_UNVERIFIED_WEB_PREVIEW must be false in production")
        if self.BOT_MODE == "webhook":
            if not self.WEBHOOK_URL or not self.WEBHOOK_SECRET:
                raise ValueError("WEBHOOK_URL and WEBHOOK_SECRET are required when BOT_MODE=webhook")
            if not self.WEBHOOK_URL.startswith("https://"):
                raise ValueError("WEBHOOK_URL must use HTTPS")
        return self

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )


settings = Settings()