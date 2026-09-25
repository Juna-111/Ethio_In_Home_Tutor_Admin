from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.bot.bot_instance import init_bot_app, shutdown_bot_app, bot_app
from app.bot.topics import ensure_forum_topics
from app.config import settings, UPLOAD_DIR
from app.database import engine, Base, AsyncSessionLocal
import app.models  # noqa: F401
from app.routes.health import router as health_router
from app.routes.parents import router as parents_router
from app.routes.tutors import router as tutors_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Auto-provision database schema on startup (works seamlessly on Render, Neon, etc.)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        try:
            from sqlalchemy import text
            await conn.execute(text("ALTER TABLE parent_requests ADD COLUMN IF NOT EXISTS telegram_topic_id BIGINT;"))
        except Exception:
            try:
                await conn.execute(text("ALTER TABLE parent_requests ADD COLUMN telegram_topic_id BIGINT;"))
            except Exception:
                pass
        try:
            from sqlalchemy import text
            await conn.execute(text("ALTER TABLE system_settings ALTER COLUMN value TYPE TEXT;"))
        except Exception:
            pass
    
    # Initialize Telegram Bot Application & background listeners
    await init_bot_app()

    # Automatically verify, create, and cache dedicated forum topics if enabled
    from app.bot.bot_instance import bot_app
    if bot_app and bot_app.bot:
        await ensure_forum_topics(bot_app.bot, AsyncSessionLocal)

    yield

    # Clean up Telegram Bot
    await shutdown_bot_app()

    # Clean up engine connection pools on shutdown
    await engine.dispose()


app = FastAPI(
    title="MentorLink API",
    description="Ethiopian In-Home Tutor & Mentor Matching Platform Backend",
    version="1.0.0",
    lifespan=lifespan,
)

# Restrict CORS to Telegram WebApp domains, configured frontend URL, and local dev
cors_origins = [
    "https://web.telegram.org",
    "https://telegram.org",
]
if settings.WEBAPP_URL:
    clean_webapp_url = settings.WEBAPP_URL.rstrip("/")
    if clean_webapp_url not in cors_origins:
        cors_origins.append(clean_webapp_url)

if settings.MINI_APP_URL and not settings.MINI_APP_URL.startswith("https://t.me/"):
    clean_mini_app_url = settings.MINI_APP_URL.rstrip("/")
    if clean_mini_app_url not in cors_origins:
        cors_origins.append(clean_mini_app_url)

if settings.ENVIRONMENT == "development":
    cors_origins.extend([
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ])

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

# Mount API v1 Routers
app.include_router(health_router, prefix="/api/v1")
app.include_router(parents_router, prefix="/api/v1")
app.include_router(tutors_router, prefix="/api/v1")


@app.get("/", tags=["Root"])
async def root():
    return {
        "service": "MentorLink Backend API",
        "version": "1.0.0",
        "docs_url": "/docs",
        "health_check": "/api/v1/health"
    }
