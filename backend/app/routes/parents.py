from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_optional_telegram_user
from app.bot.bot_instance import send_parent_request_card
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
    db: AsyncSession = Depends(get_db),
    verified_user_id: Optional[int] = Depends(get_optional_telegram_user),
):
    """
    Validates and stores a parent intake request in PostgreSQL.
    Status is initialized to 'pending'.
    Forwards a notification card to the Telegram Admin Group.
    """
    # Never trust telegram_user_id from the JSON body; it is client-controlled.
    effective_tg_id = verified_user_id

    parent_req = ParentRequest(
        telegram_user_id=effective_tg_id,
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

    # Broadcast intake card to Telegram Admin Group (creates dedicated ticket topic and index directory card)
    await send_parent_request_card(parent_req, db_session=db)

    return parent_req
