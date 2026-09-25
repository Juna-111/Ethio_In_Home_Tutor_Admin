import os
import time
from collections import defaultdict, deque
from typing import Optional
import uuid
import aiofiles
from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_telegram_user
from app.bot.bot_instance import send_tutor_registration_card
from app.config import UPLOAD_DIR
from app.database import get_db
from app.models import Tutor
from app.schemas import TutorCreate, TutorResponse

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
    verified_user_id: Optional[int] = Depends(get_current_telegram_user)
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
    except Exception as exc:
        if os.path.exists(file_path):
            os.remove(file_path)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save uploaded file: {str(exc)}"
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
    verified_user_id: Optional[int] = Depends(get_current_telegram_user),
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
        status="pending",
    )

    db.add(tutor)
    await db.commit()
    await db.refresh(tutor)

    # Broadcast verification card to Telegram Admin Group
    await send_tutor_registration_card(tutor)

    return tutor
