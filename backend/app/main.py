from contextlib import asynccontextmanager
import hmac
import logging
from urllib.parse import urlsplit
from uuid import uuid4
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from telegram import Update

from app.bot import bot_instance
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
    await bot_instance.init_bot_app()

    # Automatically verify, create, and cache dedicated forum topics if enabled
    if bot_instance.bot_app and bot_instance.bot_app.bot:
        await ensure_forum_topics(bot_instance.bot_app.bot, AsyncSessionLocal)

    yield

    # Clean up Telegram Bot
    await bot_instance.shutdown_bot_app()

    # Clean up engine connection pools on shutdown
    await engine.dispose()


app = FastAPI(
    title="MentorLink API",
    description="Ethiopian In-Home Tutor & Mentor Matching Platform Backend",
    version="1.0.0",
    lifespan=lifespan,
)

logger = logging.getLogger("mentorlink.api")


@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID") or uuid4().hex
    request.state.request_id = request_id
    logger.info("request_started method=%s path=%s request_id=%s", request.method, request.url.path, request_id)
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    logger.info(
        "request_finished method=%s path=%s status=%s request_id=%s",
        request.method,
        request.url.path,
        response.status_code,
        request_id,
    )
    return response


@app.post("/telegram/webhook/{webhook_secret}", include_in_schema=False)
async def telegram_webhook(webhook_secret: str, request: Request):
    """Accept Telegram updates only through the configured secret path and header."""
    configured_secret = settings.WEBHOOK_SECRET
    header_secret = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
    if (
        settings.BOT_MODE != "webhook"
        or not configured_secret
        or not hmac.compare_digest(webhook_secret, configured_secret)
        or not hmac.compare_digest(header_secret, configured_secret)
    ):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")

    application = bot_instance.bot_app
    if not application:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Telegram bot unavailable")

    try:
        payload = await request.json()
        update = Update.de_json(payload, application.bot)
        await application.update_queue.put(update)
    except Exception:
        logger.exception("Failed to enqueue Telegram webhook update")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid Telegram update")

    return {"ok": True}

# Restrict CORS to Telegram WebApp domains, configured frontend URL, and local dev
cors_origins = [
    "https://web.telegram.org",
    "https://telegram.org",
]
if settings.WEBAPP_URL:
    parsed_webapp_url = urlsplit(settings.WEBAPP_URL)
    clean_webapp_url = f"{parsed_webapp_url.scheme}://{parsed_webapp_url.netloc}"
    if clean_webapp_url not in cors_origins:
        cors_origins.append(clean_webapp_url)

if settings.MINI_APP_URL and not settings.MINI_APP_URL.startswith("https://t.me/"):
    parsed_mini_app_url = urlsplit(settings.MINI_APP_URL)
    clean_mini_app_url = f"{parsed_mini_app_url.scheme}://{parsed_mini_app_url.netloc}"
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
