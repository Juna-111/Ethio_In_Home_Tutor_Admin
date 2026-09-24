import logging
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas import HealthResponse

logger = logging.getLogger("mentorlink.health")

router = APIRouter(prefix="/health", tags=["Health"])


@router.get("", response_model=HealthResponse, summary="Database Connectivity Healthcheck")
async def health_check(db: AsyncSession = Depends(get_db)):
    """Verifies that the database engine can execute queries successfully."""
    try:
        result = await db.execute(text("SELECT 1"))
        scalar = result.scalar()
        if scalar != 1:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database service unavailable"
            )
        return HealthResponse(status="healthy", database="connected")
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Database connection failed during healthcheck: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database service unavailable"
        )
