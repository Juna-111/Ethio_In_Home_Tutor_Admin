import logging
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas import HealthResponse
from app.services.schema_check import get_schema_status

logger = logging.getLogger("mentorlink.health")

router = APIRouter(prefix="/health", tags=["Health"])


async def _check_database(db: AsyncSession) -> HealthResponse:
    """Build a database/schema health response without hiding migration drift."""
    result = await db.execute(text("SELECT 1"))
    if result.scalar() != 1:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database service unavailable")

    schema = await get_schema_status(db)
    if schema["state"] == "behind":
        return HealthResponse(
            status="degraded", database="connected", schema_state="behind",
            migration_current=schema["current"], migration_head=schema["head"],
            detail="Database schema is behind the deployed code. Run: alembic upgrade head",
        )
    return HealthResponse(
        status="healthy", database="connected", schema_state=schema["state"],
        migration_current=schema["current"], migration_head=schema["head"],
    )

@router.get("", response_model=HealthResponse, summary="Database Connectivity Healthcheck")
async def health_check(db: AsyncSession = Depends(get_db)):
    """Verifies that the database engine can execute queries successfully."""
    try:
        return await _check_database(db)
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Database connection failed during healthcheck: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database service unavailable",
        )


@router.get("/ready", response_model=HealthResponse, summary="Production Readiness Check")
async def readiness_check(db: AsyncSession = Depends(get_db)):
    """Fail readiness when the database is unavailable or migrations are behind."""
    try:
        health = await _check_database(db)
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Readiness database check failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database service unavailable")

    if health.schema_state != "current":
        detail = health.detail or "Database schema is not at the deployed migration head."
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=detail)
    return health
