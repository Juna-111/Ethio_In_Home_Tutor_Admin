import os
import time
from collections import defaultdict, deque
from typing import Optional
import uuid
import aiofiles
from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

import logging
from app.auth import get_optional_telegram_user
from app.bot.bot_instance import format_schedule, send_tutor_registration_card
from app.config import UPLOAD_DIR
from app.database import get_db
from app.models import Assignment, ParentRequest, RegistrationFunnelEvent, SessionFeedback, Tutor
from app.schemas import (
    FunnelStartRequest,
    FunnelStartResponse,
    TutorAssignmentItem,
    TutorCreate,
    TutorMyAssignmentsResponse,
    TutorResponse,
)

logger = logging.getLogger("mentorlink.routes.tutors")

router = APIRouter(prefix="/tutors", tags=["Tutors"])

ALLOWED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg"}
MAX_UPLOAD_SIZE = 10 * 1024 * 1024  # 10 MB
UPLOAD_RATE_LIMIT = 5
UPLOAD_RATE_WINDOW_SECONDS = 60
_upload_attempts: dict[str, deque[float]] = defaultdict(deque)


def _validate_magic_bytes(header: bytes) -> bool:
    """Validates initial byte header against known magic numbers for PDF, PNG, and JPEG."""
    if header.startswith(b"%PDF"):
        return True
    if header.startswith(b"\x89PNG\r\n\x1a\n"):
        return True
    if header.startswith(b"\xff\xd8\xff"):
        return True
    return False


@router.post(
    "/upload-document",
    status_code=status.HTTP_201_CREATED,
    summary="Upload Tutor Verification Document / CV"
)
async def upload_tutor_document(
    request: Request,
    file: UploadFile = File(...),
    verified_user_id: Optional[int] = Depends(get_optional_telegram_user)
):
    """
    Accepts file upload (ID, Certificate, CV) and saves it to the local uploads directory.
    Validates magic bytes, streams with strict 10 MB ceiling, and generates secure UUID filename.
    """
    rate_key = f"user:{verified_user_id}" if verified_user_id is not None else f"ip:{request.client.host if request.client else 'unknown'}"
    now = time.monotonic()
    attempts = _upload_attempts[rate_key]
    while attempts and now - attempts[0] >= UPLOAD_RATE_WINDOW_SECONDS:
        attempts.popleft()
    if len(attempts) >= UPLOAD_RATE_LIMIT:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many document uploads. Please try again later."
        )
    attempts.append(now)

    _, ext = os.path.splitext(file.filename or "")
    ext_lower = ext.lower()

    if ext_lower not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file format '{ext}'. Allowed types: PDF, PNG, JPG."
        )

    # Generate pure random UUID filename to prevent path traversal and sanitize
    safe_filename = f"{uuid.uuid4().hex}{ext_lower}"
    file_path = os.path.join(UPLOAD_DIR, safe_filename)

    bytes_written = 0
    first_chunk = True

    try:
        async with aiofiles.open(file_path, "wb") as f:
            while chunk := await file.read(64 * 1024):  # 64 KB chunks
                if first_chunk:
                    if not _validate_magic_bytes(chunk[:32]):
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Invalid file signature. File contents do not match allowed formats (PDF, PNG, JPG)."
                        )
                    first_chunk = False

                bytes_written += len(chunk)
                if bytes_written > MAX_UPLOAD_SIZE:
                    raise HTTPException(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        detail="File size exceeds the 10 MB maximum limit."
                    )
                await f.write(chunk)
    except HTTPException:
        if os.path.exists(file_path):
            os.remove(file_path)
        raise
    except Exception:
        if os.path.exists(file_path):
            os.remove(file_path)
        logger.exception("Failed to save tutor upload")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save uploaded file. Please try again."
        )

    if first_chunk or bytes_written == 0:
        if os.path.exists(file_path):
            os.remove(file_path)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty."
        )

    file_url = f"/uploads/{safe_filename}"
    return {
        "filename": safe_filename,
        "file_url": file_url
    }


@router.post(
    "/register",
    response_model=TutorResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register New Tutor Profile"
)
async def register_tutor(
    payload: TutorCreate,
    db: AsyncSession = Depends(get_db),
    verified_user_id: Optional[int] = Depends(get_optional_telegram_user),
):
    """
    Validates and stores a tutor registration in PostgreSQL.
    Status is initialized to 'pending'.
    Checks for duplicate telegram_user_id if provided.
    Forwards a verification card to the Telegram Admin Group.
    """
    # Never trust telegram_user_id from the JSON body; it is client-controlled.
    effective_tg_id = verified_user_id

    if effective_tg_id is not None:
        query = select(Tutor).where(Tutor.telegram_user_id == effective_tg_id)
        result = await db.execute(query)
        existing = result.scalar_one_or_none()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"A tutor with Telegram user ID {effective_tg_id} is already registered."
            )

    tutor = Tutor(
        telegram_user_id=effective_tg_id,
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
        entrance_result=payload.entrance_result,
        status="pending",
    )

    db.add(tutor)
    await db.commit()
    await db.refresh(tutor)

    # Record registration funnel submitted event
    try:
        funnel_event = RegistrationFunnelEvent(
            session_id=f"tutor_{tutor.id}_{tutor.phone_number}",
            stage="submitted",
            tutor_id=tutor.id,
        )
        db.add(funnel_event)
        await db.commit()
    except Exception as exc:
        logger.warning("Could not record tutor registration funnel event: %s", exc)

    # Broadcast verification card to Telegram Admin Group
    await send_tutor_registration_card(tutor)

    return tutor


@router.post(
    "/funnel/start",
    response_model=FunnelStartResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Record Tutor Registration Funnel Start"
)
async def start_funnel_event(
    payload: FunnelStartRequest,
    db: AsyncSession = Depends(get_db),
) -> FunnelStartResponse:
    event = RegistrationFunnelEvent(
        session_id=payload.session_id,
        stage="started",
    )
    db.add(event)
    await db.commit()
    return FunnelStartResponse(ok=True, session_id=payload.session_id)


@router.get(
    "/me/assignments",
    response_model=TutorMyAssignmentsResponse,
    summary="Get authenticated tutor's assignments and fee tracking"
)
async def get_tutor_assignments(
    db: AsyncSession = Depends(get_db),
    verified_user_id: Optional[int] = Depends(get_optional_telegram_user),
) -> TutorMyAssignmentsResponse:
    """Returns active and past assignments with session counts and earnings tracker for the authenticated tutor."""
    if verified_user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Telegram Mini App authentication is required.",
        )

    tutor = await db.scalar(select(Tutor).where(Tutor.telegram_user_id == verified_user_id))
    if not tutor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tutor profile not found for this Telegram account.",
        )

    assignments_res = await db.execute(
        select(Assignment).where(Assignment.tutor_id == tutor.id).order_by(Assignment.assigned_at.desc())
    )
    assignments = assignments_res.scalars().all()

    req_ids = [a.request_id for a in assignments]
    requests_map = {}
    if req_ids:
        req_res = await db.execute(select(ParentRequest).where(ParentRequest.id.in_(req_ids)))
        requests_map = {r.id: r for r in req_res.scalars().all()}

    asmt_ids = [a.id for a in assignments]
    feedback_stats = {}
    if asmt_ids:
        fb_res = await db.execute(
            select(
                SessionFeedback.assignment_id,
                func.count(SessionFeedback.id),
                func.avg(SessionFeedback.rating),
            ).where(SessionFeedback.assignment_id.in_(asmt_ids)).group_by(SessionFeedback.assignment_id)
        )
        for asmt_id, cnt, avg_r in fb_res.all():
            feedback_stats[asmt_id] = (cnt, round(float(avg_r), 2) if avg_r is not None else None)

    assignment_items = []
    total_earnings = 0.0
    active_count = 0

    for a in assignments:
        req = requests_map.get(a.request_id)
        if not req:
            continue

        if a.status == "active":
            active_count += 1

        landmark = f" ({req.location_landmark})" if req.location_landmark else ""
        loc_str = f"{req.location_subcity}{landmark}"
        sched_str = f"{format_schedule(req.schedule_days)} ({req.time_slot}, {req.session_duration})"
        student_ctx = f"{req.parent_name} ({req.student_level})"

        cnt, avg_r = feedback_stats.get(a.id, (0, None))
        # Estimate earnings: if sessions completed > 0, cnt * rate; if active without feedback yet, 1 baseline session
        estimated_asmt_earnings = float(max(1, cnt) * req.budget_etb) if a.status == "active" else float(cnt * req.budget_etb)
        total_earnings += estimated_asmt_earnings

        assignment_items.append(
            TutorAssignmentItem(
                assignment_id=a.id,
                request_id=a.request_id,
                student_name_context=student_ctx,
                student_level=req.student_level,
                subjects=req.subjects if isinstance(req.subjects, list) else [str(req.subjects)],
                location=loc_str,
                schedule=sched_str,
                hourly_rate_etb=req.budget_etb,
                status=a.status,
                assigned_at=a.assigned_at,
                sessions_completed=cnt,
                avg_rating=avg_r,
                estimated_earnings_etb=round(estimated_asmt_earnings, 2),
                parent_phone=req.phone_number,
            )
        )

    return TutorMyAssignmentsResponse(
        tutor_id=tutor.id,
        full_name=tutor.full_name,
        active_count=active_count,
        total_earnings_estimate=round(total_earnings, 2),
        assignments=assignment_items,
    )

