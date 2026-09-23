from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.bot.bot_instance import init_bot_app, shutdown_bot_app
from app.database import engine, Base
import app.models  # noqa: F401
from app.routes.health import router as health_router
from app.routes.parents import router as parents_router
from app.routes.tutors import router as tutors_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Auto-provision database schema on startup (works seamlessly on Render, Neon, etc.)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    # Initialize Telegram Bot Application & background listeners
    await init_bot_app()

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

# Enable CORS for Telegram WebApp frontend and local dev
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
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
