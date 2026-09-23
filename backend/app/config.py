from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    DATABASE_URL: str = "sqlite+aiosqlite:///./mentorlink.db"
    BOT_TOKEN: Optional[str] = None
    ADMIN_GROUP_ID: Optional[int] = None
    WEBAPP_URL: Optional[str] = None
    ENVIRONMENT: str = "development"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )


settings = Settings()
