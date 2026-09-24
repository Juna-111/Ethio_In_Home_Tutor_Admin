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
    PARENT_REQUESTS_TOPIC_ID: Optional[int] = None
    TUTOR_REGISTRATION_TOPIC_ID: Optional[int] = None
    WEBAPP_URL: Optional[str] = None
    MINI_APP_URL: Optional[str] = None
    ENVIRONMENT: str = "development"

    @field_validator(
        "PARENT_REQUESTS_TOPIC_ID",
        "TUTOR_REGISTRATION_TOPIC_ID",
        "SUPER_ADMIN_ID",
        mode="before",
    )
    @classmethod
    def empty_str_to_none(cls, v):
        if v == "" or v is None:
            return None
        return int(v)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )


settings = Settings()