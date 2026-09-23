from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Tutor
from app.schemas import TutorCreate, TutorResponse

router = APIRouter(prefix="/tutors", tags=["Tutors"])


@router.post(
    "/register",
    response_model=TutorResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register New Tutor Profile"
)
async def register_tutor(
    payload: TutorCreate,
    db: AsyncSession = Depends(get_db)
):
    """
    Validates and stores a tutor registration in PostgreSQL.
    Status is initialized to 'pending'.
    Checks for duplicate telegram_user_id if provided.
    """
    if payload.telegram_user_id is not None:
        query = select(Tutor).where(Tutor.telegram_user_id == payload.telegram_user_id)
        result = await db.execute(query)
        existing = result.scalar_one_or_none()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"A tutor with Telegram user ID {payload.telegram_user_id} is already registered."
            )

    tutor = Tutor(
        telegram_user_id=payload.telegram_user_id,
        full_name=payload.full_name,
        gender=payload.gender,
        phone_number=payload.phone_number,
        university=payload.university,
        department=payload.department,
        education_year=payload.education_year,
        subjects_qualified=payload.subjects_qualified,
        grades_qualified=payload.grades_qualified,
        years_of_experience=payload.years_of_experience,
        expected_fee_etb=payload.expected_fee_etb,
        base_subcity=payload.base_subcity,
        coverage_areas=payload.coverage_areas,
        availability_schedule=payload.availability_schedule,
        id_document_url=payload.id_document_url,
        status="pending",
    )

    db.add(tutor)
    await db.commit()
    await db.refresh(tutor)

    # In Phase 2: Telegram Bot notification to ADMIN_GROUP_ID will be dispatched here.

    return tutor
