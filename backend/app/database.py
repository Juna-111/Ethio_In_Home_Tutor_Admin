from typing import AsyncGenerator
from urllib.parse import parse_qs, urlencode, urlsplit, urlunsplit

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
    - Sets scheme to postgresql+asyncpg
    - Strips unsupported asyncpg query params (e.g. channel_binding, sslmode)
    - Returns sanitized clean URL and connect_args with ssl='require' when applicable
    """
    url_str = raw_url.strip()

    # If not a postgresql URL (e.g. sqlite), return as is
    if not (url_str.startswith("postgres://") or url_str.startswith("postgresql://") or url_str.startswith("postgresql+asyncpg://")):
        return url_str, {}

    url = urlsplit(url_str)
    scheme = "postgresql+asyncpg"
    query_params = parse_qs(url.query)

    # Check if SSL is required (Neon cloud DB, sslmode present, or remote host)
    needs_ssl = (
        "neon.tech" in url_str
        or "sslmode" in query_params
        or "ssl" in query_params
        or (url.hostname and url.hostname not in ("localhost", "127.0.0.1"))
    )
    connect_args = {"ssl": "require"} if needs_ssl else {}

    # Remove query parameters that asyncpg does not support in connect()
    unsupported_params = ["channel_binding", "sslmode", "ssl"]
    for param in unsupported_params:
        query_params.pop(param, None)

    clean_query = urlencode(query_params, doseq=True)
    clean_url = urlunsplit((scheme, url.netloc, url.path, clean_query, url.fragment))

    return clean_url, connect_args


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
