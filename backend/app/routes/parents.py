import html
import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_optional_telegram_user
from app.bot import bot_instance
from app.bot.bot_instance import send_parent_request_card
from app.config import settings
from app.database import get_db
from app.models import Assignment, ParentRequest, SessionFeedback, Tutor
from app.schemas import (
    ParentContactAdminCreate,
    ParentFeedbackCreate,
    ParentMyRequestsResponse,
    ParentRequestCreate,
    ParentRequestItem,
    ParentRequestResponse,
)

logger = logging.getLogger("mentorlink.routes.parents")

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


@router.post(
    "/me/requests/{request_id}/cancel",
    status_code=status.HTTP_200_OK,
    summary="Cancel an authenticated parent's unassigned request"
)
async def cancel_parent_request(
    request_id: int,
    db: AsyncSession = Depends(get_db),
    verified_user_id: Optional[int] = Depends(get_optional_telegram_user),
):
    """Cancel only a pending/reviewing request owned by the authenticated parent."""
    if verified_user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Telegram Mini App authentication is required.",
        )

    parent_req = await db.scalar(
        select(ParentRequest).where(
            ParentRequest.id == request_id,
            ParentRequest.telegram_user_id == verified_user_id,
        )
    )
    if not parent_req:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request not found.")

    if parent_req.status not in {"pending", "reviewing"}:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only pending or reviewing requests can be cancelled.",
        )

    parent_req.status = "cancelled"
    await db.commit()

    return {
        "ok": True,
        "request_id": parent_req.id,
        "status": parent_req.status,
        "message": "Your tutoring request has been cancelled.",
    }


@router.get(
    "/me/requests",
    response_model=ParentMyRequestsResponse,
    summary="Get authenticated parent's requests and assigned mentors"
)
async def get_parent_requests(
    db: AsyncSession = Depends(get_db),
    verified_user_id: Optional[int] = Depends(get_optional_telegram_user),
) -> ParentMyRequestsResponse:
    """Returns requests submitted by the authenticated parent, including assigned mentor details and feedback status."""
    if verified_user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Telegram Mini App authentication is required.",
        )

    requests_res = await db.execute(
        select(ParentRequest)
        .where(ParentRequest.telegram_user_id == verified_user_id)
        .order_by(ParentRequest.created_at.desc())
    )
    parent_requests = requests_res.scalars().all()

    req_ids = [r.id for r in parent_requests]
    assignments_map = {}
    tutors_map = {}
    feedbacks_map = {}

    if req_ids:
        asmts_res = await db.execute(select(Assignment).where(Assignment.request_id.in_(req_ids)))
        asmts = asmts_res.scalars().all()
        assignments_map = {a.request_id: a for a in asmts}

        tutor_ids = [a.tutor_id for a in asmts]
        if tutor_ids:
            tutors_res = await db.execute(select(Tutor).where(Tutor.id.in_(tutor_ids)))
            tutors_map = {t.id: t for t in tutors_res.scalars().all()}

        asmt_ids = [a.id for a in asmts]
        if asmt_ids:
            fb_res = await db.execute(select(SessionFeedback).where(SessionFeedback.assignment_id.in_(asmt_ids)))
            for fb in fb_res.scalars().all():
                feedbacks_map[fb.assignment_id] = fb

    items = []
    for r in parent_requests:
        asmt = assignments_map.get(r.id)
        tut = tutors_map.get(asmt.tutor_id) if asmt else None
        fb = feedbacks_map.get(asmt.id) if asmt else None

        items.append(
            ParentRequestItem(
                id=r.id,
                student_level=r.student_level,
                subjects=r.subjects if isinstance(r.subjects, list) else [str(r.subjects)],
                location_subcity=r.location_subcity,
                location_landmark=r.location_landmark,
                schedule_days=r.schedule_days,
                time_slot=r.time_slot,
                session_duration=r.session_duration,
                budget_etb=r.budget_etb,
                status=r.status,
                created_at=r.created_at,
                assignment_id=asmt.id if asmt else None,
                tutor_id=tut.id if tut else None,
                tutor_name=tut.full_name if tut else None,
                tutor_phone=tut.phone_number if tut else None,
                tutor_university=tut.university if tut else None,
                tutor_department=tut.department if tut else None,
                tutor_experience_years=tut.years_of_experience if tut else None,
                sessions_completed=1 if fb else 0,
                has_feedback=fb is not None,
                feedback_rating=fb.rating if fb else None,
            )
        )

    return ParentMyRequestsResponse(requests=items)


@router.post(
    "/me/feedback",
    status_code=status.HTTP_201_CREATED,
    summary="Submit session feedback for an assignment"
)
async def submit_parent_feedback(
    payload: ParentFeedbackCreate,
    db: AsyncSession = Depends(get_db),
    verified_user_id: Optional[int] = Depends(get_optional_telegram_user),
):
    """Submits 1-5 star review and comments for an assigned mentor."""
    if verified_user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Telegram Mini App authentication is required.",
        )

    assignment = None
    if payload.assignment_id:
        assignment = await db.get(Assignment, payload.assignment_id)
    elif payload.request_id:
        res = await db.execute(select(Assignment).where(Assignment.request_id == payload.request_id))
        assignment = res.scalars().first()

    if not assignment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assignment not found.")

    parent_req = await db.get(ParentRequest, assignment.request_id)
    if not parent_req or parent_req.telegram_user_id != verified_user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not authorized to submit feedback for this assignment.",
        )

    feedback_comment = payload.comment or payload.review_notes
    feedback = SessionFeedback(
        assignment_id=assignment.id,
        rating=payload.rating,
        comment=feedback_comment,
        submitted_by="parent",
    )
    db.add(feedback)
    await db.commit()

    return {"ok": True, "success": True, "message": "Feedback submitted successfully."}


@router.post(
    "/me/contact-admin",
    summary="Contact admin support regarding a tutoring request"
)
async def contact_admin_support(
    payload: ParentContactAdminCreate,
    db: AsyncSession = Depends(get_db),
    verified_user_id: Optional[int] = Depends(get_optional_telegram_user),
):
    """Forwards parent question or update request directly to the admin operations topic."""
    if verified_user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Telegram Mini App authentication is required.",
        )

    parent_req = await db.get(ParentRequest, payload.request_id)
    if not parent_req or parent_req.telegram_user_id != verified_user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request not found.")

    if bot_instance.bot_app and settings.ADMIN_GROUP_ID:
        try:
            bot = bot_instance.bot_app.bot
            text = (
                f"💬 <b>Support Inquiry from Parent {html.escape(parent_req.parent_name)}</b>\n"
                f"<b>Request:</b> <code>REQ-{parent_req.id:04d}</code> ({html.escape(parent_req.student_level)})\n"
                f"<b>Phone:</b> <code>{html.escape(parent_req.phone_number)}</code>\n\n"
                f"<b>Message:</b>\n<blockquote>{html.escape(payload.message)}</blockquote>"
            )
            send_kwargs = {
                "chat_id": settings.ADMIN_GROUP_ID,
                "text": text,
                "parse_mode": "HTML",
            }
            if parent_req.telegram_topic_id:
                send_kwargs["message_thread_id"] = parent_req.telegram_topic_id
            await bot.send_message(**send_kwargs)
        except Exception as exc:
            logger.warning("Failed to forward parent inquiry to admin group: %s", exc)

    return {"ok": True, "success": True, "message": "Your message has been delivered to our administrative team."}

