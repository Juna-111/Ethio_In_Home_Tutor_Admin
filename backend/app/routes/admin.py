from collections import Counter, defaultdict
from datetime import datetime, time, timedelta, timezone
import html
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import String, cast, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode

from app.admin_auth import AdminPrincipal, require_admin
from app.bot import bot_instance
from app.database import get_db
from app.models import Assignment, MatchInvite, ParentRequest, Tutor
from app.schemas import (
    AdminActionResponse,
    AdminAssignRequest,
    AdminCandidateResponse,
    AdminCandidatesResponse,
    AdminCoverageGapResponse,
    AdminDashboardResponse,
    AdminIdleTutorResponse,
    AdminPingRequest,
    AdminRequestListItem,
    AdminRequestListResponse,
    ParentRequestResponse,
)
from app.services.audit import log_action
from app.services.matcher import get_tiered_matches

router = APIRouter(prefix="/admin", tags=["Admin"])


@router.get("/dashboard", response_model=AdminDashboardResponse, summary="Admin dashboard counts")
async def get_admin_dashboard(
    _admin: AdminPrincipal = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> AdminDashboardResponse:
    today_start = datetime.combine(datetime.now(timezone.utc).date(), time.min, tzinfo=timezone.utc)
    pending_tutors = await db.scalar(
        select(func.count(Tutor.id)).where(Tutor.status == "pending")
    )
    pending_requests = await db.scalar(
        select(func.count(ParentRequest.id)).where(ParentRequest.status == "pending")
    )
    active_assignments = await db.scalar(
        select(func.count(Assignment.id)).where(Assignment.status == "active")
    )
    requests_today = await db.scalar(
        select(func.count(ParentRequest.id)).where(ParentRequest.created_at >= today_start)
    )

    return AdminDashboardResponse(
        admin_telegram_id=_admin.telegram_id,
        admin_role=_admin.role,
        pending_tutors=pending_tutors or 0,
        pending_requests=pending_requests or 0,
        active_assignments=active_assignments or 0,
        requests_today=requests_today or 0,
    )


@router.get("/requests", response_model=AdminRequestListResponse, summary="List parent requests")
async def list_admin_requests(
    request_status: Optional[str] = Query(None, alias="status", max_length=50),
    subcity: Optional[str] = Query(None, max_length=100),
    subject: Optional[str] = Query(None, max_length=100),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    _admin: AdminPrincipal = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> AdminRequestListResponse:
    query = select(ParentRequest)
    count_query = select(func.count(ParentRequest.id))
    filters = []
    if request_status:
        filters.append(ParentRequest.status == request_status)
    if subcity:
        filters.append(func.lower(ParentRequest.location_subcity) == subcity.strip().lower())
    if subject:
        subject_token = f'"{subject.strip().lower()}"'
        filters.append(func.lower(cast(ParentRequest.subjects, String)).contains(subject_token, autoescape=True))
    if filters:
        query = query.where(*filters)
        count_query = count_query.where(*filters)

    total = await db.scalar(count_query) or 0
    result = await db.execute(
        query.order_by(ParentRequest.created_at.desc(), ParentRequest.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    items = [
        AdminRequestListItem(
            id=item.id,
            parent_name=item.parent_name,
            location_subcity=item.location_subcity,
            student_level=item.student_level,
            subjects=item.subjects,
            preferred_gender=item.preferred_gender,
            budget_etb=item.budget_etb,
            status=item.status,
            created_at=item.created_at,
        )
        for item in result.scalars().all()
    ]
    return AdminRequestListResponse(items=items, total=total, page=page, page_size=page_size)


@router.get("/requests/{request_id}", response_model=ParentRequestResponse, summary="Get parent request")
async def get_admin_request(
    request_id: int,
    _admin: AdminPrincipal = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> ParentRequest:
    parent = await db.get(ParentRequest, request_id)
    if not parent:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request not found.")
    return parent


@router.get("/requests/{request_id}/candidates", response_model=AdminCandidatesResponse, summary="Get ranked tutor candidates")
async def get_admin_request_candidates(
    request_id: int,
    _admin: AdminPrincipal = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> AdminCandidatesResponse:
    parent, tiered = await get_tiered_matches(request_id, db)
    if not parent:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request not found.")

    candidate_rows = [
        (tier_name, candidate)
        for tier_name in ("tier1", "tier2", "tier3")
        for candidate in tiered[tier_name]
    ]
    tutor_ids = [candidate["tutor"].id for _, candidate in candidate_rows]
    invite_result = await db.execute(
        select(MatchInvite).where(
            MatchInvite.request_id == request_id,
            MatchInvite.tutor_id.in_(tutor_ids) if tutor_ids else False,
        )
    ) if tutor_ids else None
    invites = {invite.tutor_id: invite.status for invite in invite_result.scalars().all()} if invite_result else {}

    candidates = []
    for tier_name, candidate in candidate_rows:
        tutor = candidate["tutor"]
        candidates.append(AdminCandidateResponse(
            tutor_id=tutor.id,
            full_name=tutor.full_name,
            gender=tutor.gender,
            university=tutor.university,
            department=tutor.department,
            education_year=tutor.education_year,
            subjects_qualified=tutor.subjects_qualified,
            grades_qualified=tutor.grades_qualified,
            years_of_experience=tutor.years_of_experience,
            expected_fee_etb=tutor.expected_fee_etb,
            base_subcity=tutor.base_subcity,
            coverage_areas=tutor.coverage_areas,
            availability_schedule=tutor.availability_schedule,
            tier=tier_name,
            matched_subjects=candidate["matched_subjects"],
            match_reasons=candidate["match_reasons"],
            overall_score=candidate["overall_score"],
            score_breakdown=candidate["score_breakdown"],
            invite_status=invites.get(tutor.id),
            telegram_available=tutor.telegram_user_id is not None,
        ))
    candidates.sort(key=lambda item: (-item.overall_score, item.expected_fee_etb, item.tutor_id))
    return AdminCandidatesResponse(request_id=request_id, candidates=candidates)


@router.post("/requests/{request_id}/ping", response_model=AdminActionResponse, summary="Ping selected tutor candidates")
async def ping_admin_request_candidates(
    request_id: int,
    payload: AdminPingRequest,
    admin: AdminPrincipal = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> AdminActionResponse:
    parent, tiered = await get_tiered_matches(request_id, db)
    if not parent:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request not found.")
    if parent.status != "pending":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Only pending requests can be pinged.")
    if not bot_instance.bot_app:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Telegram bot is unavailable.")

    candidates = {
        candidate["tutor"].id: candidate["tutor"]
        for tier_name in ("tier1", "tier2", "tier3")
        for candidate in tiered[tier_name]
    }
    if any(tutor_id not in candidates for tutor_id in payload.tutor_ids):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Select only tutors in the current candidate list.")
    tutors = [candidates[tutor_id] for tutor_id in dict.fromkeys(payload.tutor_ids)]
    if any(not tutor.telegram_user_id for tutor in tutors):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Every selected tutor must have a Telegram account.")

    existing_result = await db.execute(
        select(MatchInvite).where(
            MatchInvite.request_id == request_id,
            MatchInvite.tutor_id.in_([tutor.id for tutor in tutors]),
        )
    )
    existing = {invite.tutor_id: invite for invite in existing_result.scalars().all()}
    claim_map: dict[int, MatchInvite] = {}
    claimed_tutors = []
    for tutor in tutors:
        invitation = existing.get(tutor.id)
        if invitation:
            if invitation.status != "expired":
                continue
            invitation.status = "sent"
            invitation.sent_at = datetime.now(timezone.utc)
            invitation.responded_at = None
            claim_map[tutor.id] = invitation
            claimed_tutors.append(tutor)
            continue
        try:
            async with db.begin_nested():
                invitation = MatchInvite(request_id=request_id, tutor_id=tutor.id, status="sent")
                db.add(invitation)
                await db.flush()
            claim_map[tutor.id] = invitation
            claimed_tutors.append(tutor)
        except IntegrityError:
            continue

    if not claimed_tutors:
        return AdminActionResponse(ok=True, message="All selected candidates have already been contacted.")
    await db.commit()

    subjects = ", ".join(html.escape(str(value)) for value in (parent.subjects or []))
    schedule = ", ".join(html.escape(str(value)) for value in parent.schedule_days) if isinstance(parent.schedule_days, list) else html.escape(str(parent.schedule_days))
    ping_text = (
        "<b>NEW TUTORING OPPORTUNITY</b>\n\n"
        f"<b>Area:</b> {html.escape(parent.location_subcity)}\n"
        f"<b>Level:</b> {html.escape(parent.student_level)} | <b>Subjects:</b> {subjects}\n"
        f"<b>Schedule:</b> {schedule} ({html.escape(parent.time_slot)})\n"
        f"<b>Rate:</b> {parent.budget_etb:,.2f} ETB/hr\n\n"
        "Are you available to take this student?"
    )
    sent = 0
    for tutor in claimed_tutors:
        keyboard = InlineKeyboardMarkup([[
            InlineKeyboardButton("✅ Yes, I'm Available", callback_data=f"tutor_avail_yes:{request_id}:{tutor.id}"),
            InlineKeyboardButton("❌ Not Available", callback_data=f"tutor_avail_no:{request_id}:{tutor.id}"),
        ]])
        try:
            await bot_instance.bot_app.bot.send_message(
                chat_id=tutor.telegram_user_id,
                text=ping_text,
                parse_mode=ParseMode.HTML,
                reply_markup=keyboard,
            )
            sent += 1
        except Exception:
            claim_map[tutor.id].status = "expired"
            claim_map[tutor.id].responded_at = None

    if sent:
        log_action(
            db,
            actor_id=admin.telegram_id,
            action="ping_candidates",
            target_type="parent_request",
            target_id=request_id,
            reason=f"Pinged tutor IDs: {', '.join(str(tutor.id) for tutor in claimed_tutors if claim_map[tutor.id].status == 'sent')}",
        )
    await db.commit()
    return AdminActionResponse(ok=sent > 0, message=f"Availability ping sent to {sent} tutor(s).")


@router.post("/requests/{request_id}/assign", response_model=AdminActionResponse, summary="Assign a tutor to a request")
async def assign_admin_request(
    request_id: int,
    payload: AdminAssignRequest,
    admin: AdminPrincipal = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> AdminActionResponse:
    tutor_id = payload.tutor_id

    parent = await db.get(ParentRequest, request_id)
    tutor = await db.get(Tutor, tutor_id)
    if not parent or not tutor:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request or tutor not found.")
    if tutor.status != "verified" or tutor.is_paused:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Only verified, active tutors can be assigned.")
    invite = await db.scalar(select(MatchInvite).where(
        MatchInvite.request_id == request_id,
        MatchInvite.tutor_id == tutor_id,
        MatchInvite.status == "yes",
    ))
    if not invite:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Tutor must confirm availability before assignment.")

    result = await db.execute(
        update(ParentRequest)
        .where(ParentRequest.id == request_id, ParentRequest.status == "pending")
        .values(status="matched")
    )
    if result.rowcount != 1:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Request is no longer pending.")

    assignment = Assignment(request_id=request_id, tutor_id=tutor_id, assigned_by=str(admin.telegram_id))
    db.add(assignment)
    log_action(db, admin.telegram_id, "assign_tutor", "parent_request", request_id, reason=f"Tutor ID {tutor_id}")
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This request already has an assignment.")

    if bot_instance.bot_app:
        bot = bot_instance.bot_app.bot
        if parent.telegram_user_id:
            try:
                await bot.send_message(
                    chat_id=parent.telegram_user_id,
                    text=(f"A verified mentor has been assigned to your request: {html.escape(tutor.full_name)}. "
                          f"Contact: {html.escape(tutor.phone_number)}"),
                    parse_mode=ParseMode.HTML,
                )
            except Exception:
                pass
        if tutor.telegram_user_id:
            try:
                await bot.send_message(
                    chat_id=tutor.telegram_user_id,
                    text=(f"You have been assigned to a tutoring request from {html.escape(parent.parent_name)}. "
                          f"Contact: {html.escape(parent.phone_number)}"),
                    parse_mode=ParseMode.HTML,
                )
            except Exception:
                pass
    return AdminActionResponse(ok=True, message="Tutor assigned successfully.")


@router.post("/requests/{request_id}/close", response_model=AdminActionResponse, summary="Close a parent request")
async def close_admin_request(
    request_id: int,
    admin: AdminPrincipal = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> AdminActionResponse:
    result = await db.execute(
        update(ParentRequest).where(ParentRequest.id == request_id, ParentRequest.status == "pending")
        .values(status="closed")
    )
    if result.rowcount != 1:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pending request not found.")
    log_action(db, admin.telegram_id, "close_request", "parent_request", request_id)
    await db.commit()
    return AdminActionResponse(ok=True, message="Request closed.")


@router.post("/requests/{request_id}/waitlist", response_model=AdminActionResponse, summary="Waitlist a parent request")
async def waitlist_admin_request(
    request_id: int,
    admin: AdminPrincipal = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> AdminActionResponse:
    result = await db.execute(
        update(ParentRequest).where(ParentRequest.id == request_id, ParentRequest.status == "pending")
        .values(status="waitlisted")
    )
    if result.rowcount != 1:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pending request not found.")
    log_action(db, admin.telegram_id, "waitlist_request", "parent_request", request_id)
    await db.commit()
    return AdminActionResponse(ok=True, message="Request added to the waitlist.")


@router.get("/analytics/coverage-gaps", response_model=list[AdminCoverageGapResponse], summary="Tutor coverage gaps")
async def get_admin_coverage_gaps(
    _admin: AdminPrincipal = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> list[AdminCoverageGapResponse]:
    request_result = await db.execute(select(ParentRequest).where(ParentRequest.status == "pending"))
    demand: Counter[tuple[str, str]] = Counter()
    subcity_names: dict[str, str] = {}
    subject_names: dict[str, str] = {}
    for parent in request_result.scalars().all():
        subcity_key = parent.location_subcity.strip().casefold()
        subcity_names[subcity_key] = parent.location_subcity
        for subject in set(parent.subjects or []):
            subject_key = str(subject).strip().casefold()
            subject_names[subject_key] = str(subject)
            demand[(subcity_key, subject_key)] += 1

    tutor_result = await db.execute(select(Tutor).where(Tutor.status == "verified", Tutor.is_paused.is_(False)))
    supply: dict[tuple[str, str], set[int]] = defaultdict(set)
    for tutor in tutor_result.scalars().all():
        tutor_subjects = {str(subject).strip().casefold() for subject in (tutor.subjects_qualified or [])}
        areas = {str(area).strip().casefold() for area in (tutor.coverage_areas or [])}
        areas.add(tutor.base_subcity.strip().casefold())
        for area in areas:
            for subject in tutor_subjects:
                supply[(area, subject)].add(tutor.id)

    gaps = []
    for (subcity_key, subject_key), pending_count in demand.items():
        tutor_count = len(supply[(subcity_key, subject_key)])
        gap_ratio = max(0.0, (pending_count - tutor_count) / pending_count)
        gaps.append(AdminCoverageGapResponse(
            subcity=subcity_names[subcity_key],
            subject=subject_names[subject_key],
            pending_requests=pending_count,
            approved_tutors=tutor_count,
            gap_ratio=round(gap_ratio, 3),
        ))
    return sorted(gaps, key=lambda gap: (-gap.gap_ratio, -gap.pending_requests, gap.subcity, gap.subject))


@router.get("/tutors/idle", response_model=list[AdminIdleTutorResponse], summary="List idle active tutors")
async def get_idle_admin_tutors(
    days: int = Query(14, ge=1, le=365),
    _admin: AdminPrincipal = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> list[AdminIdleTutorResponse]:
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    assignment_result = await db.execute(
        select(Assignment.tutor_id, func.max(Assignment.assigned_at))
        .where(Assignment.status == "active")
        .group_by(Assignment.tutor_id)
    )
    last_assigned = {tutor_id: assigned_at for tutor_id, assigned_at in assignment_result.all()}
    tutor_result = await db.execute(
        select(Tutor).where(Tutor.status == "verified", Tutor.is_paused.is_(False)).order_by(Tutor.id)
    )
    idle = []
    for tutor in tutor_result.scalars().all():
        assigned_at = last_assigned.get(tutor.id)
        if assigned_at is not None and assigned_at.tzinfo is None:
            assigned_at = assigned_at.replace(tzinfo=timezone.utc)
        if assigned_at is not None and assigned_at >= cutoff:
            continue
        idle.append(AdminIdleTutorResponse(
            id=tutor.id,
            full_name=tutor.full_name,
            phone_number=tutor.phone_number,
            telegram_user_id=tutor.telegram_user_id,
            base_subcity=tutor.base_subcity,
            subjects_qualified=tutor.subjects_qualified,
            last_assigned_at=assigned_at,
        ))
    return idle


@router.post("/tutors/{tutor_id}/reactivate-nudge", response_model=AdminActionResponse, summary="Nudge an idle tutor")
async def nudge_idle_admin_tutor(
    tutor_id: int,
    admin: AdminPrincipal = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> AdminActionResponse:
    tutor = await db.get(Tutor, tutor_id)
    if not tutor or tutor.status != "verified" or tutor.is_paused:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Active verified tutor not found.")
    if not tutor.telegram_user_id:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Tutor has no Telegram account for a nudge.")
    if not bot_instance.bot_app:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Telegram bot is unavailable.")
    try:
        await bot_instance.bot_app.bot.send_message(
            chat_id=tutor.telegram_user_id,
            text=f"Hello {html.escape(tutor.full_name)}, we have new tutoring opportunities. Update your availability with MentorLink to be considered for a match.",
            parse_mode=ParseMode.HTML,
        )
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Could not deliver tutor nudge.") from exc
    log_action(db, admin.telegram_id, "reactivate_nudge", "tutor", tutor_id)
    await db.commit()
    return AdminActionResponse(ok=True, message="Tutor nudge sent.")