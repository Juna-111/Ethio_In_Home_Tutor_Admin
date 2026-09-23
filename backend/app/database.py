import re
from typing import AsyncGenerator
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.config import settings


def normalize_database_url(raw_url: str) -> tuple[str, dict]:
    """
    Normalizes database URL for asyncpg compatibility:
    - Replaces postgres:// or postgresql:// with postgresql+asyncpg://
    - Strips sslmode query parameters which cause asyncpg driver errors
    - Returns normalized URL and appropriate connect_args (e.g., ssl='require' for Neon)
    """
    url = raw_url.strip()
    connect_args = {}

    # Handle Postgres dialect replacement
    if url.startswith("postgres://"):
        url = "postgresql+asyncpg://" + url[len("postgres://"):]
    elif url.startswith("postgresql://") and not url.startswith("postgresql+asyncpg://"):
        url = "postgresql+asyncpg://" + url[len("postgresql://"):]

    # Parse and handle SSL requirements
    if "postgresql+asyncpg://" in url:
        parsed = urlparse(url)
        query_params = parse_qs(parsed.query)

        # Check if sslmode was requested or if it's a hosted cloud DB like Neon
        needs_ssl = "sslmode" in query_params or (parsed.hostname and parsed.hostname != "localhost" and parsed.hostname != "127.0.0.1")

        if needs_ssl:
            connect_args["ssl"] = "require"

        # Strip sslmode from query parameters to prevent asyncpg errors
        query_params.pop("sslmode", None)
        new_query = urlencode(query_params, doseq=True)
        url = urlunparse(parsed._replace(query=new_query))

    return url, connect_args


DATABASE_URL, engine_connect_args = normalize_database_url(settings.DATABASE_URL)

engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    connect_args=engine_connect_args,
    pool_pre_ping=True,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency that yields an async database session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db() -> None:
    """Creates database tables automatically."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
