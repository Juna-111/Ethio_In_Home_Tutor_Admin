from contextlib import asynccontextmanager
import hmac
import logging
from urllib.parse import urlsplit
from uuid import uuid4
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from telegram import Update

from app.bot import bot_instance
from app.bot.topics import ensure_forum_topics
from app.config import settings, UPLOAD_DIR
from app.database import engine, Base, AsyncSessionLocal
import app.models  # noqa: F401
from app.routes.health import router as health_router
from app.routes.admin import router as admin_router
from app.routes.parents import router as parents_router
from app.routes.tutors import router as tutors_router
from app.services.schema_check import get_schema_status


@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.ENVIRONMENT.lower() == "development":
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    
    # Surface "code is newer than the database" at boot instead of letting it show up
    # later as opaque 500s (which browsers report as a generic network error).
    try:
        async with AsyncSessionLocal() as session:
            schema = await get_schema_status(session)
        if schema["state"] == "behind":
            logger.error(
                "DATABASE SCHEMA IS BEHIND THE DEPLOYED CODE (db=%s, code=%s). "
                "Run `alembic upgrade head` from backend/ - admin actions that touch new "
                "tables will fail until you do.",
                schema["current"], schema["head"],
            )
        else:
            logger.info("Database schema state: %s (revision=%s)", schema["state"], schema["current"])
    except Exception:
        logger.exception("Startup schema check failed (continuing)")

    # Initialize Telegram Bot Application & background listeners
    await bot_instance.init_bot_app()
    bot_instance.check_review_link_config()

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

if settings.CORS_EXTRA_ORIGINS:
    for raw_origin in settings.CORS_EXTRA_ORIGINS.split(","):
        raw_origin = raw_origin.strip()
        if not raw_origin:
            continue
        parsed_extra = urlsplit(raw_origin)
        if parsed_extra.scheme and parsed_extra.netloc:
            clean_extra = f"{parsed_extra.scheme}://{parsed_extra.netloc}"
            if clean_extra not in cors_origins:
                cors_origins.append(clean_extra)

if settings.ENVIRONMENT == "development":
    cors_origins.extend([
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ])

if not settings.WEBAPP_URL and not settings.CORS_EXTRA_ORIGINS and settings.ENVIRONMENT != "development":
    logging.getLogger("mentorlink.api").warning(
        "Neither WEBAPP_URL nor CORS_EXTRA_ORIGINS is set: browsers will block every request "
        "from your Mini App frontend (CORS). Set WEBAPP_URL to your frontend's https origin."
    )
logging.getLogger("mentorlink.api").info("CORS allowed origins: %s", cors_origins)

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    # The admin Mini App uses PATCH (verification checklist, resolving incidents)
    # and DELETE (removing admins). Browsers preflight those cross-origin calls and
    # refuse to send them unless they are listed here, which surfaces to the user as a
    # generic "network connection error".
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """Return unexpected failures as JSON *with* CORS headers.

    Starlette runs this handler outside CORSMiddleware, so without adding the headers
    here the browser sees a CORS failure and reports a generic network error instead of
    the real 500. The client can now show a reference id that matches the server log.
    """
    request_id = getattr(request.state, "request_id", None) or uuid4().hex
    logger.exception(
        "unhandled_exception method=%s path=%s request_id=%s",
        request.method, request.url.path, request_id,
    )
    headers = {"X-Request-ID": request_id}
    origin = request.headers.get("origin")
    if origin and origin in cors_origins:
        headers["Access-Control-Allow-Origin"] = origin
        headers["Access-Control-Allow-Credentials"] = "true"
        headers["Vary"] = "Origin"
    return JSONResponse(
        status_code=500,
        content={"detail": f"Internal server error. Reference: {request_id}"},
        headers=headers,
    )

# Mount API v1 Routers
app.include_router(health_router, prefix="/api/v1")
app.include_router(admin_router, prefix="/api/v1")
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
