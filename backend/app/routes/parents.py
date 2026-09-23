from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import ParentRequest
from app.schemas import ParentRequestCreate, ParentRequestResponse

router = APIRouter(prefix="/parents", tags=["Parents"])


@router.post(
    "/request",
    response_model=ParentRequestResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit Parent Tutoring Request"
)
async def create_parent_request(
    payload: ParentRequestCreate,
    db: AsyncSession = Depends(get_db)
):
    """
    Validates and stores a parent intake request in PostgreSQL.
    Status is initialized to 'pending'.
    """
    parent_req = ParentRequest(
        telegram_user_id=payload.telegram_user_id,
        parent_name=payload.parent_name,
        phone_number=payload.phone_number,
        student_level=payload.student_level,
        subjects=payload.subjects,
        preferred_gender=payload.preferred_gender,
        preferred_experience=payload.preferred_experience,
        location_subcity=payload.location_subcity,
        location_landmark=payload.location_landmark,
        schedule_days=payload.schedule_days,
        time_slot=payload.time_slot,
        session_duration=payload.session_duration,
        budget_etb=payload.budget_etb,
        status="pending",
    )

    db.add(parent_req)
    await db.commit()
    await db.refresh(parent_req)

    # In Phase 2: Telegram Bot notification to ADMIN_GROUP_ID will be dispatched here.

    return parent_req
