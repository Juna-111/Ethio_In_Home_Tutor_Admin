from collections import Counter, defaultdict
from datetime import datetime, time, timedelta, timezone
import hmac
import html
import logging
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy import String, cast, distinct, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode

from app.admin_auth import AdminPrincipal, require_admin, require_role
from app.auth import get_optional_telegram_user
from app.bot import bot_instance
from app.config import settings, UPLOAD_DIR
from app.database import get_db
from app.models import (
    AdminUser,
    Assignment,
    AuditLog,
    MatchInvite,
    NotificationOutbox,
    ParentRequest,
    RegistrationFunnelEvent,
    SessionFeedback,
    Tutor,
    TutorIncident,
    TutorVerification,
)
from app.schemas import (
    AdminActionResponse,
    AdminAssignRequest,
    AdminAvailabilityMismatchItem,
    AdminAvailabilityMismatchResponse,
    AdminCandidateResponse,
    AdminCandidatesResponse,
    AdminCoverageGapResponse,
    AdminCronRunResponse,
    AdminDashboardResponse,
    AdminFlagResponse,
    AdminFunnelResponse,
    AdminIdleTutorResponse,
    AdminIncidentCreate,
    AdminIncidentListResponse,
    AdminIncidentPatch,
    AdminIncidentResponse,
    AdminPingRequest,
    AdminRejectRequest,
    AdminRequestListItem,
    AdminRequestListResponse,
    AdminTutorDetailResponse,
    AdminTutorListItem,
    AdminTutorListResponse,
    AdminTutorScorecardResponse,
    AdminUserCreate,
    AdminUserListResponse,
    AdminUserResponse,
    AdminAuditLogItem,
    AdminAuditLogResponse,
    AdminVerificationPatch,
    AdminVerificationResponse,
    AdminAssignmentPipelineResponse,
    AdminParentCRMItem,
    AdminParentCRMResponse,
    AdminParentRequestHistoryItem,
    AdminPipelineOldestItem,
    ParentRequestResponse,
)
from app.services.audit import log_action
from app.services.export_service import generate_assignments_csv, generate_parents_csv, generate_tutors_csv
from app.services.matcher import get_tiered_matches
from app.services.scheduler import claim_event, run_all_scheduled_tasks

router = APIRouter(prefix="/admin", tags=["Admin"])
logger = logging.getLogger("mentorlink.routes.admin")


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

    # Expanded metrics
    total_requests = await db.scalar(select(func.count(ParentRequest.id))) or 0
    assigned_requests = await db.scalar(select(func.count(Assignment.id))) or 0
    conversion_rate_pct = round((assigned_requests / total_requests) * 100, 2) if total_requests > 0 else 0.0

    # Avg time to assign in days
    time_diffs_stmt = select(Assignment.assigned_at, ParentRequest.created_at).join(
        ParentRequest, Assignment.request_id == ParentRequest.id
    )
    diffs_res = await db.execute(time_diffs_stmt)
    diff_days = []
    for asmt_at, req_at in diffs_res.all():
        if asmt_at and req_at:
            if asmt_at.tzinfo is None:
                asmt_at = asmt_at.replace(tzinfo=timezone.utc)
            if req_at.tzinfo is None:
                req_at = req_at.replace(tzinfo=timezone.utc)
            delta = (asmt_at - req_at).total_seconds() / 86400.0
            if delta >= 0:
                diff_days.append(delta)
    avg_days_to_assign = round(sum(diff_days) / len(diff_days), 2) if diff_days else 0.0

    total_tutors = await db.scalar(select(func.count(Tutor.id))) or 0
    verified_tutors = await db.scalar(select(func.count(Tutor.id)).where(Tutor.status == "verified")) or 0
    tutor_verification_funnel_pct = round((verified_tutors / total_tutors) * 100, 2) if total_tutors > 0 else 0.0

    return AdminDashboardResponse(
        admin_telegram_id=_admin.telegram_id,
        admin_role=_admin.role,
        pending_tutors=pending_tutors or 0,
        pending_requests=pending_requests or 0,
        active_assignments=active_assignments or 0,
        requests_today=requests_today or 0,
        conversion_rate_pct=conversion_rate_pct,
        avg_days_to_assign=avg_days_to_assign,
        tutor_verification_funnel_pct=tutor_verification_funnel_pct,
    )


@router.get("/parents", response_model=AdminParentCRMResponse, summary="Customer CRM: Search parents and view request history")
async def list_admin_parents(
    search: Optional[str] = Query(None, max_length=100),
    request_status: Optional[str] = Query(None, alias="status", max_length=50),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    _admin: AdminPrincipal = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> AdminParentCRMResponse:
    query = select(ParentRequest).order_by(ParentRequest.created_at.desc())
    filters = []
    if request_status and request_status.strip().lower() != "all":
        filters.append(ParentRequest.status == request_status.strip())
    if search and search.strip():
        term = f"%{search.strip().lower()}%"
        filters.append(
            func.lower(ParentRequest.parent_name).like(term)
            | func.lower(ParentRequest.phone_number).like(term)
            | func.lower(ParentRequest.location_subcity).like(term)
        )
    if filters:
        query = query.where(*filters)

    result = await db.execute(query)
    all_matching_requests = result.scalars().all()

    req_ids = [r.id for r in all_matching_requests]
    assignments_map = {}
    tutors_map = {}
    if req_ids:
        asmts_res = await db.execute(select(Assignment).where(Assignment.request_id.in_(req_ids)))
        asmts = asmts_res.scalars().all()
        assignments_map = {a.request_id: a for a in asmts}
        tutor_ids = [a.tutor_id for a in asmts]
        if tutor_ids:
            tutors_res = await db.execute(select(Tutor).where(Tutor.id.in_(tutor_ids)))
            tutors_map = {t.id: t for t in tutors_res.scalars().all()}

    parents_grouped: dict[str, list[ParentRequest]] = defaultdict(list)
    for r in all_matching_requests:
        parents_grouped[r.phone_number].append(r)

    total_parents = len(parents_grouped)
    start_idx = (page - 1) * page_size
    end_idx = start_idx + page_size
    paged_phones = list(parents_grouped.keys())[start_idx:end_idx]

    items = []
    for phone in paged_phones:
        reqs = parents_grouped[phone]
        latest_req = reqs[0]
        active_cnt = sum(1 for r in reqs if r.status in ("pending", "matched", "waitlisted"))
        completed_cnt = sum(1 for r in reqs if assignments_map.get(r.id) and assignments_map[r.id].status == "active")

        history_items = []
        for r in reqs:
            asmt = assignments_map.get(r.id)
            tut = tutors_map.get(asmt.tutor_id) if asmt else None
            history_items.append(
                AdminParentRequestHistoryItem(
                    id=r.id,
                    student_level=r.student_level,
                    subjects=r.subjects if isinstance(r.subjects, list) else [str(r.subjects)],
                    location_subcity=r.location_subcity,
                    location_landmark=r.location_landmark,
                    budget_etb=r.budget_etb,
                    status=r.status,
                    created_at=r.created_at,
                    assignment_id=asmt.id if asmt else None,
                    assigned_tutor_id=tut.id if tut else None,
                    assigned_tutor_name=tut.full_name if tut else None,
                    assigned_at=asmt.assigned_at if asmt else None,
                )
            )

        items.append(
            AdminParentCRMItem(
                phone_number=phone,
                parent_name=latest_req.parent_name,
                telegram_user_id=latest_req.telegram_user_id,
                location_subcity=latest_req.location_subcity,
                total_requests=len(reqs),
                active_requests=active_cnt,
                completed_assignments=completed_cnt,
                latest_request_date=latest_req.created_at,
                requests=history_items,
            )
        )

    return AdminParentCRMResponse(
        items=items,
        total=total_parents,
        page=page,
        page_size=page_size,
    )


@router.get("/assignments/pipeline", response_model=AdminAssignmentPipelineResponse, summary="Assignment pipeline operational overview")
async def get_admin_assignment_pipeline(
    _admin: AdminPrincipal = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> AdminAssignmentPipelineResponse:
    """Return pipeline metrics without loading the entire request table into memory."""
    now = datetime.now(timezone.utc)

    status_result = await db.execute(
        select(
            ParentRequest.status,
            func.count(ParentRequest.id),
        )
        .group_by(ParentRequest.status)
    )
    status_counts = {
        status or "pending": int(count)
        for status, count in status_result.all()
    }

    median_age_days: dict[str, float] = {}
    oldest_per_status: dict[str, list[AdminPipelineOldestItem]] = {}

    for status, count in status_counts.items():
        if count <= 0:
            median_age_days[status] = 0.0
            oldest_per_status[status] = []
            continue

        # Fetch only the rows needed for the median timestamp rather than
        # materializing every request in Python.
        median_offset = (count - 1) // 2
        median_result = await db.execute(
            select(ParentRequest.created_at)
            .where(ParentRequest.status == status)
            .order_by(ParentRequest.created_at.asc(), ParentRequest.id.asc())
            .offset(median_offset)
            .limit(1)
        )
        median_created_at = median_result.scalar_one_or_none()
        if median_created_at is None:
            median_age_days[status] = 0.0
        else:
            if median_created_at.tzinfo is None:
                median_created_at = median_created_at.replace(tzinfo=timezone.utc)
            median_age_days[status] = round(
                max(0.0, (now - median_created_at).total_seconds() / 86400.0),
                2,
            )

        # For even-sized groups, average the two middle timestamps.
        if count % 2 == 0:
            upper_result = await db.execute(
                select(ParentRequest.created_at)
                .where(ParentRequest.status == status)
                .order_by(ParentRequest.created_at.asc(), ParentRequest.id.asc())
                .offset(count // 2)
                .limit(1)
            )
            upper_created_at = upper_result.scalar_one_or_none()
            if upper_created_at is not None:
                if upper_created_at.tzinfo is None:
                    upper_created_at = upper_created_at.replace(tzinfo=timezone.utc)
                median_created_at = median_created_at.replace(tzinfo=timezone.utc) if median_created_at.tzinfo is None else median_created_at
                median_age_days[status] = round(
                    max(
                        0.0,
                        (now - median_created_at).total_seconds() / 86400.0,
                    )
                    + max(
                        0.0,
                        (now - upper_created_at).total_seconds() / 86400.0,
                    )
                    / 2.0,
                    2,
                )

        oldest_result = await db.execute(
            select(ParentRequest)
            .where(ParentRequest.status == status)
            .order_by(ParentRequest.created_at.asc(), ParentRequest.id.asc())
            .limit(10)
        )
        oldest_per_status[status] = [
            AdminPipelineOldestItem(
                id=req.id,
                parent_name=req.parent_name,
                phone_number=req.phone_number,
                student_level=req.student_level,
                location_subcity=req.location_subcity,
                budget_etb=req.budget_etb,
                status=status,
                created_at=req.created_at,
                age_days=round(
                    max(
                        0.0,
                        (
                            now
                            - (
                                req.created_at.replace(tzinfo=timezone.utc)
                                if req.created_at.tzinfo is None
                                else req.created_at
                            )
                        ).total_seconds()
                        / 86400.0,
                    ),
                    2,
                ),
            )
            for req in oldest_result.scalars().all()
        ]

    return AdminAssignmentPipelineResponse(
        status_counts=status_counts,
        median_age_days=median_age_days,
        oldest_per_status=oldest_per_status,
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

    # Record or confirm MatchInvite so relationship is tracked
    invite = await db.scalar(select(MatchInvite).where(
        MatchInvite.request_id == request_id,
        MatchInvite.tutor_id == tutor_id,
    ))
    now_utc = datetime.now(timezone.utc)
    if not invite:
        invite = MatchInvite(
            request_id=request_id,
            tutor_id=tutor_id,
            status="yes",
            sent_at=now_utc,
            responded_at=now_utc,
        )
        db.add(invite)
    elif invite.status != "yes":
        invite.status = "yes"
        invite.responded_at = now_utc

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
        parent_card = bot_instance.format_assignment_card_parent(parent, tutor, assignment.id)
        parent_keyboard = bot_instance.build_parent_assignment_keyboard(request_id)
        if parent.telegram_user_id:
            try:
                await bot.send_message(
                    chat_id=parent.telegram_user_id,
                    text=parent_card,
                    parse_mode=ParseMode.HTML,
                    reply_markup=parent_keyboard,
                )
            except Exception as exc:
                logger.warning(
                    "Failed to DM parent %s on assignment for request #%s (role=parent): %s",
                    parent.telegram_user_id, request_id, exc,
                )
        tutor_card = bot_instance.format_assignment_card_tutor(parent, tutor, assignment.id)
        tutor_keyboard = bot_instance.build_tutor_assignment_keyboard(request_id)
        if tutor.telegram_user_id:
            try:
                await bot.send_message(
                    chat_id=tutor.telegram_user_id,
                    text=tutor_card,
                    parse_mode=ParseMode.HTML,
                    reply_markup=tutor_keyboard,
                )
            except Exception as exc:
                logger.warning(
                    "Failed to DM tutor %s on assignment for request #%s (role=tutor): %s",
                    tutor.telegram_user_id, request_id, exc,
                )

        # Sync assignment to Admin Group forum topic and close topic if open
        if parent.telegram_topic_id and settings.ADMIN_GROUP_ID:
            try:
                await bot.send_message(
                    chat_id=settings.ADMIN_GROUP_ID,
                    text=f"✅ Successfully assigned <b>{html.escape(tutor.full_name)}</b> to Parent Request #{request_id} by admin ({admin.telegram_id}).",
                    parse_mode=ParseMode.HTML,
                    message_thread_id=parent.telegram_topic_id,
                )
            except Exception as exc:
                logger.debug("Failed to post assignment confirmation in forum topic: %s", exc)
            if hasattr(bot, "close_forum_topic"):
                try:
                    await bot.close_forum_topic(
                        chat_id=settings.ADMIN_GROUP_ID,
                        message_thread_id=parent.telegram_topic_id,
                    )
                except Exception as exc:
                    logger.debug("Failed to close forum topic for request #%s: %s", request_id, exc)
    else:
        logger.warning(
            "Bot app not running; assignment notifications skipped for request #%s (tutor #%s).",
            request_id, tutor_id,
        )
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


async def check_waitlist_matches_for_tutor(db: AsyncSession, tutor: Tutor) -> None:
    """Checks waitlisted parent requests for subject matches with a newly approved tutor."""
    result = await db.execute(
        select(ParentRequest).where(ParentRequest.status == "waitlisted")
    )
    waitlisted = result.scalars().all()
    tutor_subjs = {s.lower().strip() for s in (tutor.subjects_qualified or [])}
    matches = [req for req in waitlisted if {s.lower().strip() for s in (req.subjects or [])} & tutor_subjs]
    if matches:
        count = len(matches)
        event_key = f"waitlist_backfill:tutor:{tutor.id}:count_{count}"
        claimed = await claim_event(db, event_key, "waitlist_backfill", "tutor", tutor.id)
        if claimed:
            from app.bot.topics import get_parent_topic_id
            msg = (
                f"🎯 <b>Waitlist Match Found!</b>\n\n"
                f"Newly approved tutor <b>{tutor.full_name}</b> (ID: {tutor.id}) matches "
                f"<b>{count}</b> waitlisted request(s).\n"
                f"Review and assign candidates in the Matching Workbench."
            )
            outbox = NotificationOutbox(
                event_key=event_key,
                target_type="admin_group",
                topic_id=get_parent_topic_id(),
                message_text=msg,
                status="pending",
            )
            db.add(outbox)
            log_action(db, 0, "waitlist_backfill_alert", "tutor", tutor.id, reason=f"Matched {count} waitlisted requests")


@router.patch("/tutors/{tutor_id}/verification", response_model=AdminVerificationResponse, summary="Update tutor verification flags")
async def update_admin_tutor_verification(
    tutor_id: int,
    payload: AdminVerificationPatch,
    admin: AdminPrincipal = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> AdminVerificationResponse:
    tutor = await db.get(Tutor, tutor_id)
    if not tutor:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tutor not found.")

    verification = await db.get(TutorVerification, tutor_id)
    if not verification:
        verification = TutorVerification(tutor_id=tutor_id)
        db.add(verification)

    if payload.id_verified is not None:
        verification.id_verified = payload.id_verified
    if payload.entrance_result_verified is not None:
        verification.entrance_result_verified = payload.entrance_result_verified
    if payload.phone_confirmed is not None:
        verification.phone_confirmed = payload.phone_confirmed
    if payload.claims_plausible is not None:
        verification.claims_plausible = payload.claims_plausible

    verification.last_verified_at = datetime.now(timezone.utc)
    verification.verified_by = admin.telegram_id

    all_complete = bool(
        verification.id_verified and 
        verification.entrance_result_verified and 
        verification.phone_confirmed and 
        verification.claims_plausible
    )

    was_verified = (tutor.status == "verified")
    if all_complete:
        tutor.status = "verified"
        if not was_verified:
            await check_waitlist_matches_for_tutor(db, tutor)
    elif tutor.status == "verified":
        tutor.status = "pending"

    log_action(db, admin.telegram_id, "update_verification", "tutor", tutor_id)
    await db.commit()

    return AdminVerificationResponse(
        tutor_id=tutor_id,
        id_verified=verification.id_verified,
        entrance_result_verified=verification.entrance_result_verified,
        phone_confirmed=verification.phone_confirmed,
        claims_plausible=verification.claims_plausible,
        all_complete=all_complete,
        tutor_status=tutor.status
    )


@router.post("/tutors/{tutor_id}/reject", response_model=AdminActionResponse, summary="Reject a tutor")
async def reject_admin_tutor(
    tutor_id: int,
    payload: AdminRejectRequest,
    admin: AdminPrincipal = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> AdminActionResponse:
    tutor = await db.get(Tutor, tutor_id)
    if not tutor:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tutor not found.")

    tutor.status = "rejected"
    log_action(db, admin.telegram_id, "reject_tutor", "tutor", tutor_id, reason=payload.reason)
    await db.commit()
    return AdminActionResponse(ok=True, message="Tutor rejected.")


import os

@router.get("/tutors/{tutor_id}/document", summary="View tutor ID document")
async def get_admin_tutor_document(
    tutor_id: int,
    _admin: AdminPrincipal = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    tutor = await db.get(Tutor, tutor_id)
    if not tutor or not tutor.id_document_url:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")

    filename = tutor.id_document_url.replace("/uploads/", "")
    file_path = os.path.join(UPLOAD_DIR, filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document file missing.")

    ext = os.path.splitext(filename)[1].lower()
    media_type = "application/octet-stream"
    if ext == ".pdf":
        media_type = "application/pdf"
    elif ext == ".png":
        media_type = "image/png"
    elif ext in [".jpg", ".jpeg"]:
        media_type = "image/jpeg"

    return FileResponse(file_path, media_type=media_type)


@router.get("/tutors/{tutor_id}/scorecard", response_model=AdminTutorScorecardResponse, summary="Get tutor scorecard")
async def get_admin_tutor_scorecard(
    tutor_id: int,
    _admin: AdminPrincipal = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> AdminTutorScorecardResponse:
    stmt = select(func.avg(SessionFeedback.rating), func.count(SessionFeedback.id)).join(Assignment, SessionFeedback.assignment_id == Assignment.id).where(Assignment.tutor_id == tutor_id)
    result = await db.execute(stmt)
    avg_rating, feedback_count = result.first()

    invites_stmt = select(func.count(MatchInvite.id), func.count(MatchInvite.responded_at)).where(MatchInvite.tutor_id == tutor_id)
    invites_res = await db.execute(invites_stmt)
    invite_count, responded_count = invites_res.first()
    
    response_rate = responded_count / invite_count if invite_count and invite_count > 0 else None
    
    return AdminTutorScorecardResponse(
        tutor_id=tutor_id,
        avg_rating=float(avg_rating) if avg_rating else None,
        response_rate=float(response_rate) if response_rate is not None else None,
        feedback_count=feedback_count or 0,
        invite_count=invite_count or 0,
        incident_count=await db.scalar(select(func.count(TutorIncident.id)).where(TutorIncident.tutor_id == tutor_id)) or 0
    )


@router.get("/tutors", response_model=AdminTutorListResponse, summary="List tutors")
async def list_admin_tutors(
    tutor_status: Optional[str] = Query(None, alias="status", max_length=50),
    search: Optional[str] = Query(None, max_length=100, description="Match against tutor name or phone number"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    _admin: AdminPrincipal = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> AdminTutorListResponse:
    query = select(Tutor)
    count_query = select(func.count(Tutor.id))
    filters = []
    if tutor_status:
        filters.append(Tutor.status == tutor_status)
    if search:
        needle = f"%{search.strip()}%"
        filters.append(
            (Tutor.full_name.ilike(needle)) | (Tutor.phone_number.ilike(needle))
        )
    if filters:
        query = query.where(*filters)
        count_query = count_query.where(*filters)

    total = await db.scalar(count_query) or 0
    result = await db.execute(
        query.order_by(Tutor.created_at.desc(), Tutor.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    items = [
        AdminTutorListItem(
            id=item.id,
            full_name=item.full_name,
            gender=item.gender,
            base_subcity=item.base_subcity,
            subjects_qualified=item.subjects_qualified,
            status=item.status,
            created_at=item.created_at,
            entrance_result=item.entrance_result,
            phone_number=item.phone_number
        )
        for item in result.scalars().all()
    ]
    return AdminTutorListResponse(items=items, total=total, page=page, page_size=page_size)


@router.get("/tutors/{tutor_id}", response_model=AdminTutorDetailResponse, summary="Get full tutor profile")
async def get_admin_tutor_detail(
    tutor_id: int,
    _admin: AdminPrincipal = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> AdminTutorDetailResponse:
    tutor = await db.get(Tutor, tutor_id)
    if not tutor:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tutor not found.")

    verification = await db.get(TutorVerification, tutor_id)
    verification_resp = None
    if verification:
        all_complete = bool(
            verification.id_verified and 
            verification.entrance_result_verified and 
            verification.phone_confirmed and 
            verification.claims_plausible
        )
        verification_resp = AdminVerificationResponse(
            tutor_id=tutor_id,
            id_verified=verification.id_verified,
            entrance_result_verified=verification.entrance_result_verified,
            phone_confirmed=verification.phone_confirmed,
            claims_plausible=verification.claims_plausible,
            all_complete=all_complete,
            tutor_status=tutor.status
        )

    resp_dict = tutor.__dict__.copy()
    resp_dict["verification"] = verification_resp
    return AdminTutorDetailResponse(**resp_dict)

# Incidents CRUD
@router.get("/incidents", response_model=AdminIncidentListResponse, summary="List tutor incidents")
async def list_admin_incidents(
    tutor_id: Optional[int] = Query(None),
    incident_status: Optional[str] = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    _admin: AdminPrincipal = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> AdminIncidentListResponse:
    query = select(TutorIncident)
    count_query = select(func.count(TutorIncident.id))
    filters = []
    if tutor_id is not None:
        filters.append(TutorIncident.tutor_id == tutor_id)
    if incident_status:
        filters.append(TutorIncident.status == incident_status)
    if filters:
        query = query.where(*filters)
        count_query = count_query.where(*filters)
    total = await db.scalar(count_query) or 0
    result = await db.execute(
        query.order_by(TutorIncident.created_at.desc(), TutorIncident.id.desc())
        .offset((page - 1) * page_size).limit(page_size)
    )
    items = [AdminIncidentResponse.model_validate(i) for i in result.scalars().all()]
    return AdminIncidentListResponse(items=items, total=total, page=page, page_size=page_size)


@router.post("/incidents", response_model=AdminIncidentResponse, status_code=201, summary="Create a tutor incident")
async def create_admin_incident(
    payload: AdminIncidentCreate,
    admin: AdminPrincipal = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> AdminIncidentResponse:
    tutor = await db.get(Tutor, payload.tutor_id)
    if not tutor:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tutor not found.")
    incident = TutorIncident(
        tutor_id=payload.tutor_id,
        request_id=payload.request_id,
        severity=payload.severity,
        description=payload.description,
        reported_by=admin.telegram_id,
    )
    db.add(incident)
    log_action(db, admin.telegram_id, "create_incident", "tutor", payload.tutor_id, reason=payload.description)
    await db.commit()
    await db.refresh(incident)
    return AdminIncidentResponse.model_validate(incident)


@router.patch("/incidents/{incident_id}", response_model=AdminIncidentResponse, summary="Update a tutor incident")
async def update_admin_incident(
    incident_id: int,
    payload: AdminIncidentPatch,
    admin: AdminPrincipal = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> AdminIncidentResponse:
    incident = await db.get(TutorIncident, incident_id)
    if not incident:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Incident not found.")
    if payload.severity is not None:
        incident.severity = payload.severity
    if payload.description is not None:
        incident.description = payload.description
    if payload.status is not None:
        incident.status = payload.status
        if payload.status == "resolved":
            incident.resolved_at = datetime.now(timezone.utc)
    log_action(db, admin.telegram_id, "update_incident", "tutor_incident", incident_id)
    await db.commit()
    await db.refresh(incident)
    return AdminIncidentResponse.model_validate(incident)


# Red-flag detector
@router.get("/flags", response_model=list[AdminFlagResponse], summary="Detect red flags across tutors")
async def get_admin_flags(
    _admin: AdminPrincipal = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> list[AdminFlagResponse]:
    flags: list[AdminFlagResponse] = []
    # Load configurable thresholds from SystemSetting
    from app.models import SystemSetting
    entrance_threshold_setting = await db.get(SystemSetting, "entrance_score_threshold")
    entrance_threshold = float(entrance_threshold_setting.value) if entrance_threshold_setting else 50.0
    fee_outlier_setting = await db.get(SystemSetting, "fee_outlier_factor")
    fee_outlier_factor = float(fee_outlier_setting.value) if fee_outlier_setting else 2.0

    tutor_result = await db.execute(select(Tutor).where(Tutor.status.in_(["pending", "verified"])))
    tutors = tutor_result.scalars().all()

    # Build phone -> tutor IDs map for duplicate detection
    phone_map: dict[str, list] = {}
    # Build experience-band fee averages
    exp_fees: dict[str, list[float]] = {}
    for t in tutors:
        phone_map.setdefault(t.phone_number, []).append(t)
        band = "0-1" if t.years_of_experience < 1 else ("1-3" if t.years_of_experience < 3 else "3+")
        exp_fees.setdefault(band, []).append(t.expected_fee_etb)
    band_avg = {band: sum(fees) / len(fees) for band, fees in exp_fees.items() if fees}

    for t in tutors:
        # Missing ID document
        if not t.id_document_url:
            flags.append(AdminFlagResponse(
                flag_type="missing_document", tutor_id=t.id, tutor_name=t.full_name,
                detail="No ID document uploaded.", severity="medium",
            ))
        # Low entrance score
        if t.entrance_result is not None and t.entrance_result < entrance_threshold:
            flags.append(AdminFlagResponse(
                flag_type="low_entrance_score", tutor_id=t.id, tutor_name=t.full_name,
                detail=f"Entrance score {t.entrance_result} is below threshold {entrance_threshold}.",
                severity="medium",
            ))
        # Duplicate phone
        if len(phone_map.get(t.phone_number, [])) > 1:
            other_ids = [o.id for o in phone_map[t.phone_number] if o.id != t.id]
            flags.append(AdminFlagResponse(
                flag_type="duplicate_phone", tutor_id=t.id, tutor_name=t.full_name,
                detail=f"Phone {t.phone_number} shared with tutor(s) {other_ids}.",
                severity="high",
            ))
        # Fee outlier
        band = "0-1" if t.years_of_experience < 1 else ("1-3" if t.years_of_experience < 3 else "3+")
        avg = band_avg.get(band)
        if avg and t.expected_fee_etb > avg * fee_outlier_factor:
            flags.append(AdminFlagResponse(
                flag_type="fee_outlier", tutor_id=t.id, tutor_name=t.full_name,
                detail=f"Fee {t.expected_fee_etb:.0f} ETB exceeds {fee_outlier_factor}x band avg ({avg:.0f} ETB).",
                severity="low",
            ))
    return sorted(flags, key=lambda f: {"high": 0, "medium": 1, "low": 2}.get(f.severity, 3))


# Admin user CRUD (super_admin only)
@router.get("/admins", response_model=AdminUserListResponse, summary="List admin users")
async def list_admin_users(
    admin: AdminPrincipal = Depends(require_role("super_admin")),
    db: AsyncSession = Depends(get_db),
) -> AdminUserListResponse:
    result = await db.execute(select(AdminUser).order_by(AdminUser.created_at.desc()))
    items = [AdminUserResponse.model_validate(a) for a in result.scalars().all()]
    return AdminUserListResponse(items=items, total=len(items))


@router.post("/admins", response_model=AdminUserResponse, status_code=201, summary="Add an admin user")
async def create_admin_user(
    payload: AdminUserCreate,
    admin: AdminPrincipal = Depends(require_role("super_admin")),
    db: AsyncSession = Depends(get_db),
) -> AdminUserResponse:
    existing = await db.get(AdminUser, payload.telegram_id)
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Admin user already exists.")
    admin_user = AdminUser(
        telegram_id=payload.telegram_id,
        role=payload.role,
        added_by=admin.telegram_id,
    )
    db.add(admin_user)
    log_action(db, admin.telegram_id, "add_admin", "admin_user", payload.telegram_id, reason=f"Role: {payload.role}")
    await db.commit()
    await db.refresh(admin_user)
    return AdminUserResponse.model_validate(admin_user)


@router.delete("/admins/{telegram_id}", response_model=AdminActionResponse, summary="Remove an admin user")
async def delete_admin_user(
    telegram_id: int,
    admin: AdminPrincipal = Depends(require_role("super_admin")),
    db: AsyncSession = Depends(get_db),
) -> AdminActionResponse:
    admin_user = await db.get(AdminUser, telegram_id)
    if not admin_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Admin user not found.")
    if telegram_id == admin.telegram_id:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Cannot remove yourself.")
    await db.delete(admin_user)
    log_action(db, admin.telegram_id, "remove_admin", "admin_user", telegram_id)
    await db.commit()
    return AdminActionResponse(ok=True, message="Admin user removed.")


# Audit log viewer (super_admin only)
@router.get("/audit", response_model=AdminAuditLogResponse, summary="View audit log")
async def list_admin_audit_log(
    target_type: Optional[str] = Query(None, max_length=30),
    actor: Optional[int] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    admin: AdminPrincipal = Depends(require_role("super_admin")),
    db: AsyncSession = Depends(get_db),
) -> AdminAuditLogResponse:
    query = select(AuditLog)
    count_query = select(func.count(AuditLog.id))
    filters = []
    if target_type:
        filters.append(AuditLog.target_type == target_type)
    if actor is not None:
        filters.append(AuditLog.actor_telegram_id == actor)
    if filters:
        query = query.where(*filters)
        count_query = count_query.where(*filters)
    total = await db.scalar(count_query) or 0
    result = await db.execute(
        query.order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
        .offset((page - 1) * page_size).limit(page_size)
    )
    items = [AdminAuditLogItem.model_validate(a) for a in result.scalars().all()]
    return AdminAuditLogResponse(items=items, total=total, page=page, page_size=page_size)


# ==========================================
# Phase 5 — Strategic Analytics & Ops
# ==========================================

@router.get("/analytics/funnel", response_model=AdminFunnelResponse, summary="Tutor registration funnel analytics")
async def get_admin_funnel_analytics(
    _admin: AdminPrincipal = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> AdminFunnelResponse:
    started_events = await db.scalar(
        select(func.count(distinct(RegistrationFunnelEvent.session_id)))
        .where(RegistrationFunnelEvent.stage == "started")
    ) or 0

    submitted_events = await db.scalar(
        select(func.count(distinct(RegistrationFunnelEvent.session_id)))
        .where(RegistrationFunnelEvent.stage == "submitted")
    ) or 0

    total_tutors = await db.scalar(select(func.count(Tutor.id))) or 0
    submitted = max(submitted_events, total_tutors)
    # Ensure monotonic funnel consistency: submitted <= started
    started = max(started_events, submitted)

    approved = await db.scalar(
        select(func.count(Tutor.id)).where(Tutor.status == "verified")
    ) or 0

    # Ensure monotonic funnel consistency: approved <= submitted
    approved = min(approved, submitted)

    sub_rate = round(submitted / started, 4) if started > 0 else 0.0
    app_rate = round(approved / submitted, 4) if submitted > 0 else 0.0

    return AdminFunnelResponse(
        started=started,
        submitted=submitted,
        approved=approved,
        submission_rate=sub_rate,
        approval_rate=app_rate,
    )


@router.get(
    "/analytics/availability-mismatch",
    response_model=AdminAvailabilityMismatchResponse,
    summary="Schedule availability mismatch cross-tabulation",
)
async def get_admin_availability_mismatch(
    _admin: AdminPrincipal = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> AdminAvailabilityMismatchResponse:
    # Query pending/active parent requests
    req_res = await db.execute(
        select(ParentRequest).where(
            ParentRequest.status.in_(["pending", "waitlisted", "active"])
        )
    )
    requests = req_res.scalars().all()

    # Query verified and pending tutors
    tutor_res = await db.execute(
        select(Tutor).where(Tutor.status.in_(["pending", "verified"]))
    )
    tutors = tutor_res.scalars().all()

    # Standard slot buckets
    slots = ["Morning", "Afternoon", "Evening", "Weekend", "Flexible"]
    demand_counts = {slot: 0 for slot in slots}
    supply_counts = {slot: 0 for slot in slots}

    for req in requests:
        slot_text = (req.time_slot or "").lower()
        matched = False
        for slot in slots:
            if slot.lower() in slot_text:
                demand_counts[slot] += 1
                matched = True
        if not matched:
            demand_counts["Flexible"] += 1

    for t in tutors:
        sched = t.availability_schedule
        sched_text = str(sched).lower() if sched else ""
        matched = False
        for slot in slots:
            if slot.lower() in sched_text:
                supply_counts[slot] += 1
                matched = True
        if not matched:
            supply_counts["Flexible"] += 1

    items: list[AdminAvailabilityMismatchItem] = []
    total_demand = sum(demand_counts.values())
    total_supply = sum(supply_counts.values())

    for slot in slots:
        d = demand_counts[slot]
        s = supply_counts[slot]
        gap = max(0, d - s)
        ratio = round(gap / d, 4) if d > 0 else 0.0
        items.append(
            AdminAvailabilityMismatchItem(
                slot=slot,
                demand=d,
                supply=s,
                gap=gap,
                mismatch_ratio=ratio,
            )
        )

    return AdminAvailabilityMismatchResponse(
        total_demand=total_demand,
        total_supply=total_supply,
        items=items,
    )


@router.get("/export", summary="Export production records as CSV")
async def get_admin_export(
    export_type: str = Query("tutors", alias="type", pattern=r"^(tutors|parents|assignments)$"),
    _admin: AdminPrincipal = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    if export_type == "tutors":
        buffer, _ = await generate_tutors_csv(db)
        filename = "tutors_export.csv"
    elif export_type == "assignments":
        buffer, _ = await generate_assignments_csv(db)
        filename = "assignments_export.csv"
    else:
        buffer, _ = await generate_parents_csv(db)
        filename = "parents_export.csv"

    return StreamingResponse(
        buffer,
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Access-Control-Expose-Headers": "Content-Disposition",
        },
    )


@router.post(
    "/cron/run",
    response_model=AdminCronRunResponse,
    summary="Trigger scheduled background checks and drain outbox",
)
async def run_cron_endpoint(
    request: Request,
    db: AsyncSession = Depends(get_db),
    x_cron_secret: Optional[str] = Header(None, alias="X-Cron-Secret"),
    authorization: Optional[str] = Header(None),
) -> AdminCronRunResponse:
    is_authenticated = False
    expected_secret = settings.CRON_SECRET

    if expected_secret:
        if x_cron_secret and hmac.compare_digest(x_cron_secret, expected_secret):
            is_authenticated = True
        elif authorization:
            parts = authorization.split()
            if (
                len(parts) == 2
                and parts[0].lower() == "bearer"
                and hmac.compare_digest(parts[1], expected_secret)
            ):
                is_authenticated = True

    if not is_authenticated:
        # Fallback to Mini App admin auth if available
        try:
            user_id = await get_optional_telegram_user(authorization)
            if user_id:
                admin_user = await db.get(AdminUser, user_id)
                if (admin_user and admin_user.is_active) or (
                    settings.SUPER_ADMIN_ID and user_id == settings.SUPER_ADMIN_ID
                ):
                    is_authenticated = True
        except Exception as exc:
            logger.debug("Optional telegram user lookup failed in cron: %s", exc)

    if not is_authenticated:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized cron execution. Valid CRON_SECRET or Admin authentication required.",
        )

    bot_app = bot_instance.bot_app.bot if bot_instance.bot_app else None
    result = await run_all_scheduled_tasks(db, bot=bot_app)

    return AdminCronRunResponse(
        ok=True,
        message="Scheduled checks and outbox drained successfully.",
        result=result,
    )
