from typing import Optional, Union
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    DATABASE_URL: str = "sqlite+aiosqlite:///./mentorlink.db"
    BOT_TOKEN: Optional[str] = None
    ADMIN_GROUP_ID: Optional[Union[int, str]] = None
    PARENT_REQUESTS_TOPIC_ID: Optional[int] = None
    TUTOR_REGISTRATION_TOPIC_ID: Optional[int] = None
    WEBAPP_URL: Optional[str] = None
    ENVIRONMENT: str = "development"

    @field_validator("PARENT_REQUESTS_TOPIC_ID", "TUTOR_REGISTRATION_TOPIC_ID", mode="before")
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
