import html
import logging
from typing import Optional
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_optional_telegram_user
from app.bot import bot_instance
from app.bot.bot_instance import send_parent_request_card
from app.config import settings
from app.services.matcher import _are_grades_compatible, _normalize_list, _schedule_days
from app.database import get_db
from app.models import Assignment, Child, MarketplaceFavorite, MatchInvite, ParentRequest, SessionFeedback, Tutor, TutorVerification
from app.schemas import (
    ParentContactAdminCreate,
    ParentFeedbackCreate,
    ParentMyRequestsResponse,
    ParentRequestCreate,
    ParentRequestItem,
    ParentRequestResponse,
    MarketplaceApplicationCreate,
    ChildCreate,
    ChildResponse,
    ParentChildrenResponse,
    MarketplaceApplicationResponse,
    MarketplaceFavoriteResponse,
    MarketplaceTutorDetailResponse,
    MarketplaceTutorItem,
    MarketplaceTutorListResponse,
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
    response: Response = None,
):
    effective_tg_id = verified_user_id
    if effective_tg_id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Telegram Mini App authentication is required.")

    child = await _get_or_create_child(db, effective_tg_id, payload.child_id, payload.child_name)
    preferred_tutor = await _get_verified_marketplace_tutor(db, payload.preferred_tutor_id) if payload.preferred_tutor_id else None
    if preferred_tutor:
        if payload.preferred_gender not in {"No preference", "", None} and payload.preferred_gender.lower() != str(preferred_tutor.gender).lower():
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="The selected tutor does not match the requested gender preference.")
        if not set(_normalize_list(payload.subjects)).intersection(set(_normalize_list(preferred_tutor.subjects_qualified))):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="The selected tutor does not teach a requested subject.")
        if not _are_grades_compatible(payload.student_level.strip().lower(), _normalize_list(preferred_tutor.grades_qualified)):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="The selected tutor does not match the requested grade level.")
        requested_area = payload.location_subcity.strip().lower()
        if requested_area != str(preferred_tutor.base_subcity or "").strip().lower() and requested_area not in {str(v).strip().lower() for v in _json_list(preferred_tutor.coverage_areas)}:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="The selected tutor does not cover the requested area.")
        budget = float(payload.budget_etb or 0)
        fee = float(preferred_tutor.expected_fee_etb or 0)
        if budget > 0 and fee > budget * 1.35:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="The selected tutor is outside the flexible budget range.")
        requested_days = _schedule_days(payload.schedule_days)
        tutor_days = _schedule_days(preferred_tutor.availability_schedule)
        if requested_days and (not tutor_days or not requested_days.intersection(tutor_days)):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="The selected tutor has no availability overlap.")

    cutoff = datetime.now(timezone.utc) - timedelta(minutes=10)
    recent = (await db.execute(
        select(ParentRequest).where(
            ParentRequest.created_at >= cutoff,
            ParentRequest.telegram_user_id == effective_tg_id,
        ).order_by(ParentRequest.created_at.desc()).limit(25)
    )).scalars().all()

    normalized_phone = payload.phone_number.strip()
    for existing in recent:
        if (
            existing.phone_number == normalized_phone
            and existing.child_id == (child.id if child else None)
            and existing.student_level == payload.student_level
            and existing.subjects == payload.subjects
            and existing.location_subcity == payload.location_subcity
            and existing.schedule_days == payload.schedule_days
            and existing.time_slot == payload.time_slot
            and existing.session_duration == payload.session_duration
            and float(existing.budget_etb or 0) == float(payload.budget_etb or 0)
            and existing.preferred_tutor_id == payload.preferred_tutor_id
        ):
            if response is not None:
                response.status_code = status.HTTP_200_OK
            return existing

    parent_req = ParentRequest(
        telegram_user_id=effective_tg_id,
        child_id=child.id if child else None,
        preferred_tutor_id=preferred_tutor.id if preferred_tutor else None,
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
    await db.flush()

    if preferred_tutor:
        db.add(MatchInvite(request_id=parent_req.id, tutor_id=preferred_tutor.id, status="sent"))

    await db.commit()
    await db.refresh(parent_req)
    await send_parent_request_card(parent_req, db_session=db)

    if preferred_tutor and preferred_tutor.telegram_user_id and bot_instance.bot_app:
        try:
            await bot_instance.bot_app.bot.send_message(
                chat_id=preferred_tutor.telegram_user_id,
                text=(
                    "📚 <b>Direct Tutor Request</b>\n\n"
                    f"A parent specifically requested you for <b>{html.escape(parent_req.student_level)}</b> "
                    f"in <b>{html.escape(parent_req.location_subcity)}</b>.\n"
                    f"<b>Subjects:</b> {html.escape(', '.join(str(v) for v in _json_list(parent_req.subjects)))}\n"
                    f"<b>Schedule:</b> {html.escape(_availability_text(parent_req.schedule_days))}\n"
                    f"<b>Budget:</b> {parent_req.budget_etb:,.0f} ETB/hr\n\n"
                    "Open your Tutor Portal to accept or decline this opportunity."
                ),
                parse_mode="HTML",
            )
        except Exception as exc:
            logger.warning("Direct tutor request notification failed for tutor #%s: %s", preferred_tutor.id, exc)

    return parent_req


@router.get("/me/children", response_model=ParentChildrenResponse, summary="List the authenticated parent's children")
async def get_parent_children(
    db: AsyncSession = Depends(get_db),
    verified_user_id: Optional[int] = Depends(get_optional_telegram_user),
):
    if verified_user_id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Telegram Mini App authentication is required.")
    rows = await db.execute(select(Child).where(
        Child.parent_telegram_user_id == verified_user_id,
        Child.is_active.is_(True),
    ).order_by(Child.created_at.asc(), Child.id.asc()))
    return ParentChildrenResponse(children=[ChildResponse.model_validate(c) for c in rows.scalars().all()])


@router.post("/me/children", response_model=ChildResponse, status_code=status.HTTP_201_CREATED, summary="Create a child profile")
async def create_parent_child(
    payload: ChildCreate,
    db: AsyncSession = Depends(get_db),
    verified_user_id: Optional[int] = Depends(get_optional_telegram_user),
):
    if verified_user_id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Telegram Mini App authentication is required.")
    child = await _get_or_create_child(db, verified_user_id, None, payload.name)
    await db.commit()
    await db.refresh(child)
    return child

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

    child_ids = [r.child_id for r in parent_requests if r.child_id]
    children_map = {}
    if child_ids:
        child_rows = await db.execute(select(Child).where(
            Child.id.in_(child_ids),
            Child.parent_telegram_user_id == verified_user_id,
        ))
        children_map = {c.id: c for c in child_rows.scalars().all()}

    req_ids = [r.id for r in parent_requests]
    assignments_map = {}
    tutors_map = {}
    feedbacks_map = {}
    applications_map = {}

    if req_ids:
        asmts_res = await db.execute(select(Assignment).where(Assignment.request_id.in_(req_ids)))
        asmts = asmts_res.scalars().all()
        assignments_map = {a.request_id: a for a in asmts}

        tutor_ids = [a.tutor_id for a in asmts]
        if tutor_ids:
            tutors_res = await db.execute(select(Tutor).where(Tutor.id.in_(tutor_ids)))
            tutors_map = {t.id: t for t in tutors_res.scalars().all()}

        invite_res = await db.execute(
            select(MatchInvite).where(MatchInvite.request_id.in_(req_ids)).order_by(MatchInvite.sent_at.desc())
        )
        invites = invite_res.scalars().all()
        invite_tutor_ids = [i.tutor_id for i in invites]
        if invite_tutor_ids:
            invite_tutors_res = await db.execute(select(Tutor).where(Tutor.id.in_(invite_tutor_ids)))
            tutors_map.update({t.id: t for t in invite_tutors_res.scalars().all()})
        for invite in invites:
            applications_map.setdefault(invite.request_id, []).append(invite)

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
                child_id=r.child_id,
                child_name=children_map.get(r.child_id).name if r.child_id in children_map else None,
                preferred_tutor_id=r.preferred_tutor_id,
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
                applications=[
                    {
                        "invite_id": invite.id,
                        "tutor_id": invite.tutor_id,
                        "tutor_name": tutors_map.get(invite.tutor_id).full_name if tutors_map.get(invite.tutor_id) else None,
                        "status": invite.status,
                        "sent_at": invite.sent_at,
                        "responded_at": invite.responded_at,
                    }
                    for invite in applications_map.get(r.id, [])
                ],
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




async def _get_or_create_child(db: AsyncSession, parent_telegram_user_id: int, child_id: Optional[int], child_name: Optional[str]) -> Optional[Child]:
    if child_id is not None:
        child = await db.scalar(select(Child).where(
            Child.id == child_id,
            Child.parent_telegram_user_id == parent_telegram_user_id,
            Child.is_active.is_(True),
        ))
        if not child:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Child profile not found.")
        return child
    if not child_name:
        return None
    normalized = " ".join(child_name.strip().lower().split())
    if not normalized:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Child name cannot be empty.")
    child = await db.scalar(select(Child).where(
        Child.parent_telegram_user_id == parent_telegram_user_id,
        Child.normalized_name == normalized,
        Child.is_active.is_(True),
    ))
    if child:
        return child
    child = Child(parent_telegram_user_id=parent_telegram_user_id, name=child_name.strip(), normalized_name=normalized)
    db.add(child)
    await db.flush()
    return child


async def _get_verified_marketplace_tutor(db: AsyncSession, tutor_id: int) -> Tutor:
    tutor = await db.scalar(select(Tutor).where(
        Tutor.id == tutor_id,
        Tutor.status.in_({"verified", "probation"}),
        Tutor.is_paused.is_(False),
    ))
    if not tutor:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tutor is not currently available in the marketplace.")
    verification = await db.scalar(select(TutorVerification).where(TutorVerification.tutor_id == tutor.id))
    if not verification or not all([verification.id_verified, verification.entrance_result_verified, verification.phone_confirmed, verification.claims_plausible]):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This tutor is not fully verified yet.")
    return tutor

def _json_list(value):
    if isinstance(value, list):
        return value
    if value is None:
        return []
    return [str(value)]


def _availability_text(value) -> str:
    if isinstance(value, dict):
        return " ".join(f"{k} {v}" for k, v in value.items()).lower()
    if isinstance(value, list):
        return " ".join(str(v) for v in value).lower()
    return str(value or "").lower()


def _match_tutor(tutor: Tutor, request: Optional[ParentRequest]):
    if not request:
        return 0.0, []

    tutor_subjects = {str(v).strip().lower() for v in _json_list(tutor.subjects_qualified)}
    requested_subjects = {str(v).strip().lower() for v in _json_list(request.subjects)}
    subject_hits = tutor_subjects & requested_subjects

    tutor_grades = {str(v).strip().lower() for v in _json_list(tutor.grades_qualified)}
    grade_match = request.student_level.strip().lower() in tutor_grades
    location_match = (
        request.location_subcity.strip().lower() == str(tutor.base_subcity).strip().lower()
        or request.location_subcity.strip().lower() in {str(v).strip().lower() for v in _json_list(tutor.coverage_areas)}
    )
    budget_match = float(tutor.expected_fee_etb or 0) <= float(request.budget_etb or 0)
    availability = _availability_text(tutor.availability_schedule)
    requested_days = [str(v).strip().lower() for v in _json_list(request.schedule_days)]
    availability_match = bool(requested_days) and any(day in availability for day in requested_days)
    gender_match = request.preferred_gender in {"No preference", "", None} or request.preferred_gender.lower() == str(tutor.gender).lower()

    score = 0.0
    reasons = []
    if subject_hits:
        score += 35.0 * min(1.0, len(subject_hits) / max(1, len(requested_subjects)))
        reasons.append(f"Teaches {', '.join(sorted(subject_hits))}")
    if grade_match:
        score += 20.0
        reasons.append("Matches the requested grade")
    if location_match:
        score += 15.0
        reasons.append("Covers the requested area")
    if budget_match:
        score += 10.0
        reasons.append("Within the requested budget")
    if availability_match:
        score += 10.0
        reasons.append("Availability overlaps")
    if gender_match:
        score += 5.0
        reasons.append("Matches gender preference")
    return round(score, 1), reasons[:3]


def _marketplace_item(tutor, verification, avg_rating, review_count, is_favorite, score, reasons):
    return MarketplaceTutorItem(
        id=tutor.id,
        full_name=tutor.full_name,
        gender=tutor.gender,
        university=tutor.university,
        department=tutor.department,
        education_year=tutor.education_year,
        subjects_qualified=_json_list(tutor.subjects_qualified),
        grades_qualified=_json_list(tutor.grades_qualified),
        years_of_experience=float(tutor.years_of_experience or 0),
        expected_fee_etb=float(tutor.expected_fee_etb or 0),
        base_subcity=tutor.base_subcity,
        coverage_areas=_json_list(tutor.coverage_areas),
        availability_schedule=tutor.availability_schedule,
        status=tutor.status,
        verification_complete=bool(verification and verification.id_verified and verification.entrance_result_verified and verification.phone_confirmed and verification.claims_plausible),
        avg_rating=round(float(avg_rating), 1) if avg_rating is not None else None,
        review_count=int(review_count or 0),
        is_favorite=is_favorite,
        match_score=score,
        match_reasons=reasons,
    )


async def _marketplace_context(db, tutor_ids):
    if not tutor_ids:
        return {}, {}
    verification_rows = await db.execute(
        select(TutorVerification).where(TutorVerification.tutor_id.in_(tutor_ids))
    )
    verifications = {row.tutor_id: row for row in verification_rows.scalars().all()}

    rating_rows = await db.execute(
        select(Assignment.tutor_id, func.avg(SessionFeedback.rating), func.count(SessionFeedback.id))
        .join(SessionFeedback, SessionFeedback.assignment_id == Assignment.id)
        .where(Assignment.tutor_id.in_(tutor_ids))
        .group_by(Assignment.tutor_id)
    )
    ratings = {row[0]: (row[1], row[2]) for row in rating_rows.all()}
    return verifications, ratings


@router.get(
    "/tutors",
    response_model=MarketplaceTutorListResponse,
    summary="Discover verified tutors for the parent marketplace",
)
async def discover_tutors(
    subject: Optional[str] = Query(None),
    grade: Optional[str] = Query(None),
    subcity: Optional[str] = Query(None),
    max_fee: Optional[float] = Query(None, gt=0),
    min_rating: Optional[float] = Query(None, ge=1, le=5),
    verified_only: bool = Query(True),
    available_day: Optional[str] = Query(None),
    favorite_only: bool = Query(False),
    request_id: Optional[int] = Query(None, gt=0),
    db: AsyncSession = Depends(get_db),
    verified_user_id: Optional[int] = Depends(get_optional_telegram_user),
) -> MarketplaceTutorListResponse:
    if verified_user_id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Telegram Mini App authentication is required.")

    request = None
    if request_id:
        request = await db.scalar(
            select(ParentRequest).where(
                ParentRequest.id == request_id,
                ParentRequest.telegram_user_id == verified_user_id,
            )
        )
        if not request:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tutoring request not found.")
    else:
        request = await db.scalar(
            select(ParentRequest)
            .where(
                ParentRequest.telegram_user_id == verified_user_id,
                ParentRequest.status.in_({"pending", "reviewing"}),
            )
            .order_by(ParentRequest.created_at.desc())
        )

    query = select(Tutor).where(Tutor.status.in_({"verified", "probation"}), Tutor.is_paused.is_(False))
    if max_fee is not None:
        query = query.where(Tutor.expected_fee_etb <= max_fee)

    tutors = (await db.execute(query.order_by(Tutor.created_at.desc()))).scalars().all()
    tutor_ids = [t.id for t in tutors]
    verifications, ratings = await _marketplace_context(db, tutor_ids)
    favorite_rows = await db.execute(
        select(MarketplaceFavorite.tutor_id).where(
            MarketplaceFavorite.parent_telegram_user_id == verified_user_id,
            MarketplaceFavorite.tutor_id.in_(tutor_ids or [-1]),
        )
    )
    favorite_ids = set(favorite_rows.scalars().all())

    items = []
    for tutor in tutors:
        subjects = {str(v).strip().lower() for v in _json_list(tutor.subjects_qualified)}
        grades = {str(v).strip().lower() for v in _json_list(tutor.grades_qualified)}
        if subject and subject.strip().lower() not in subjects:
            continue
        if grade and not _are_grades_compatible(grade.strip().lower(), list(grades)):
            continue
        if subcity:
            requested_area = subcity.strip().lower()
            if requested_area != str(tutor.base_subcity or "").strip().lower() and requested_area not in {
                str(v).strip().lower() for v in _json_list(tutor.coverage_areas)
            }:
                continue
        if available_day:
            requested_days = _schedule_days([available_day])
            tutor_days = _schedule_days(tutor.availability_schedule)
            if requested_days and (not tutor_days or not requested_days.intersection(tutor_days)):
                continue

        verification = verifications.get(tutor.id)
        is_verified = bool(verification and verification.id_verified and verification.entrance_result_verified and verification.phone_confirmed and verification.claims_plausible)
        if verified_only and not is_verified:
            continue
        if favorite_only and tutor.id not in favorite_ids:
            continue

        avg_rating, review_count = ratings.get(tutor.id, (None, 0))
        if min_rating is not None and (avg_rating is None or float(avg_rating) < min_rating):
            continue

        score, reasons = _match_tutor(tutor, request)
        items.append(_marketplace_item(tutor, verification, avg_rating, review_count, tutor.id in favorite_ids, score, reasons))

    items.sort(key=lambda item: (item.match_score, item.avg_rating or 0, item.review_count, item.years_of_experience), reverse=True)
    return MarketplaceTutorListResponse(tutors=items, total=len(items), request_id=request.id if request else None)


@router.get(
    "/tutors/{tutor_id}",
    response_model=MarketplaceTutorDetailResponse,
    summary="View a tutor marketplace profile",
)
async def get_marketplace_tutor(
    tutor_id: int,
    db: AsyncSession = Depends(get_db),
    verified_user_id: Optional[int] = Depends(get_optional_telegram_user),
) -> MarketplaceTutorDetailResponse:
    if verified_user_id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Telegram Mini App authentication is required.")
    tutor = await db.scalar(
        select(Tutor).where(Tutor.id == tutor_id, Tutor.status.in_({"verified", "probation"}), Tutor.is_paused.is_(False))
    )
    if not tutor:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tutor not found.")

    request = await db.scalar(
        select(ParentRequest)
        .where(ParentRequest.telegram_user_id == verified_user_id, ParentRequest.status.in_({"pending", "reviewing"}))
        .order_by(ParentRequest.created_at.desc())
    )
    verifications, ratings = await _marketplace_context(db, [tutor.id])
    favorite = await db.scalar(
        select(MarketplaceFavorite).where(
            MarketplaceFavorite.parent_telegram_user_id == verified_user_id,
            MarketplaceFavorite.tutor_id == tutor.id,
        )
    )
    avg_rating, review_count = ratings.get(tutor.id, (None, 0))
    score, reasons = _match_tutor(tutor, request)
    return _marketplace_item(tutor, verifications.get(tutor.id), avg_rating, review_count, favorite is not None, score, reasons)


@router.post(
    "/tutors/{tutor_id}/apply",
    response_model=MarketplaceApplicationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Apply to a tutor from the marketplace",
)
async def apply_to_tutor(
    tutor_id: int,
    payload: MarketplaceApplicationCreate,
    db: AsyncSession = Depends(get_db),
    verified_user_id: Optional[int] = Depends(get_optional_telegram_user),
) -> MarketplaceApplicationResponse:
    if verified_user_id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Telegram Mini App authentication is required.")

    request = await db.scalar(
        select(ParentRequest).where(
            ParentRequest.id == payload.request_id,
            ParentRequest.telegram_user_id == verified_user_id,
        )
    )
    if not request:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tutoring request not found.")
    if request.status not in {"pending", "reviewing"}:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Only an active tutoring request can receive applications.")

    tutor = await _get_verified_marketplace_tutor(db, tutor_id)

    if request.preferred_gender not in {"No preference", "", None} and request.preferred_gender.lower() != str(tutor.gender).lower():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This tutor does not match the gender preference on your request.")

    requested_subjects = set(_normalize_list(request.subjects))
    tutor_subjects = set(_normalize_list(tutor.subjects_qualified))
    if not requested_subjects.intersection(tutor_subjects):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This tutor does not teach a requested subject.")

    if not _are_grades_compatible(request.student_level.strip().lower(), _normalize_list(tutor.grades_qualified)):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This tutor does not match the requested grade level.")

    requested_area = request.location_subcity.strip().lower()
    if requested_area != str(tutor.base_subcity or "").strip().lower() and requested_area not in {
        str(v).strip().lower() for v in _json_list(tutor.coverage_areas)
    }:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This tutor does not cover the requested area.")

    budget = float(request.budget_etb or 0)
    fee = float(tutor.expected_fee_etb or 0)
    if budget > 0 and fee > budget * 1.35:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This tutor is outside the request's flexible budget range.")

    requested_days = _schedule_days(request.schedule_days)
    tutor_days = _schedule_days(tutor.availability_schedule)
    if requested_days and (not tutor_days or not requested_days.intersection(tutor_days)):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This tutor has no availability overlap with the request.")

    if request.preferred_tutor_id is not None and request.preferred_tutor_id != tutor.id:
        current_target_invite = await db.scalar(select(MatchInvite).where(
            MatchInvite.request_id == request.id,
            MatchInvite.tutor_id == request.preferred_tutor_id,
        ))
        if current_target_invite and current_target_invite.status == "yes":
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This request already has a tutor who accepted the direct request.")

    request.preferred_tutor_id = tutor.id

    existing = await db.scalar(
        select(MatchInvite).where(MatchInvite.request_id == request.id, MatchInvite.tutor_id == tutor.id)
    )
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"You already applied to this tutor ({existing.status}).")

    invite = MatchInvite(request_id=request.id, tutor_id=tutor.id, status="sent")
    db.add(invite)
    await db.commit()
    await db.refresh(invite)

    # Notify the tutor only after the invite is durable, eliminating the
    # Telegram-before-DB race that could produce a false "opportunity not found".
    if bot_instance.bot_app and tutor.telegram_user_id:
        try:
            await bot_instance.bot_app.bot.send_message(
                chat_id=tutor.telegram_user_id,
                text=(
                    "📚 <b>New Tutor Application</b>\n\n"
                    f"A parent requested a tutor for <b>{html.escape(request.student_level)}</b> "
                    f"in <b>{html.escape(request.location_subcity)}</b>.\n"
                    f"<b>Subjects:</b> {html.escape(', '.join(str(v) for v in _json_list(request.subjects)))}\n"
                    f"<b>Schedule:</b> {html.escape(_availability_text(request.schedule_days))}\n"
                    f"<b>Budget:</b> {request.budget_etb:,.0f} ETB/hr\n\n"
                    "Open your Tutor Portal to accept or decline this opportunity."
                ),
                parse_mode="HTML",
            )
        except Exception as exc:
            logger.warning("Marketplace application notification failed for tutor #%s: %s", tutor.id, exc)

    return MarketplaceApplicationResponse(ok=True, invite_id=invite.id, request_id=request.id, tutor_id=tutor.id, status=invite.status)


@router.post(
    "/tutors/{tutor_id}/favorite",
    response_model=MarketplaceFavoriteResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Favorite a tutor",
)
async def favorite_tutor(
    tutor_id: int,
    db: AsyncSession = Depends(get_db),
    verified_user_id: Optional[int] = Depends(get_optional_telegram_user),
) -> MarketplaceFavoriteResponse:
    if verified_user_id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Telegram Mini App authentication is required.")
    tutor = await db.scalar(select(Tutor).where(Tutor.id == tutor_id, Tutor.status.in_({"verified", "probation"}), Tutor.is_paused.is_(False)))
    if not tutor:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tutor not found.")
    existing = await db.scalar(select(MarketplaceFavorite).where(MarketplaceFavorite.parent_telegram_user_id == verified_user_id, MarketplaceFavorite.tutor_id == tutor_id))
    if not existing:
        db.add(MarketplaceFavorite(parent_telegram_user_id=verified_user_id, tutor_id=tutor_id))
        await db.commit()
    return MarketplaceFavoriteResponse(ok=True, tutor_id=tutor_id, is_favorite=True)


@router.delete(
    "/tutors/{tutor_id}/favorite",
    response_model=MarketplaceFavoriteResponse,
    summary="Remove a tutor from favorites",
)
async def unfavorite_tutor(
    tutor_id: int,
    db: AsyncSession = Depends(get_db),
    verified_user_id: Optional[int] = Depends(get_optional_telegram_user),
) -> MarketplaceFavoriteResponse:
    if verified_user_id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Telegram Mini App authentication is required.")
    favorite = await db.scalar(select(MarketplaceFavorite).where(MarketplaceFavorite.parent_telegram_user_id == verified_user_id, MarketplaceFavorite.tutor_id == tutor_id))
    if not favorite:
        return MarketplaceFavoriteResponse(ok=True, tutor_id=tutor_id, is_favorite=False)
    await db.delete(favorite)
    await db.commit()
    return MarketplaceFavoriteResponse(ok=True, tutor_id=tutor_id, is_favorite=False)