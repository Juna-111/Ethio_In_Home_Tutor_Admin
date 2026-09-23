import os
import uuid
import aiofiles
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.bot_instance import send_tutor_registration_card
from app.database import get_db
from app.models import Tutor
from app.schemas import TutorCreate, TutorResponse

router = APIRouter(prefix="/tutors", tags=["Tutors"])

UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".doc", ".png", ".jpg", ".jpeg"}


@router.post(
    "/upload-document",
    status_code=status.HTTP_201_CREATED,
    summary="Upload Tutor Verification Document / CV"
)
async def upload_tutor_document(file: UploadFile = File(...)):
    """
    Accepts file upload (ID, Certificate, CV) and saves it to the local uploads directory.
    Returns the file URL to be stored in the tutor profile.
    """
    _, ext = os.path.splitext(file.filename or "")
    ext_lower = ext.lower()

    if ext_lower not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file format '{ext}'. Allowed types: PDF, DOCX, PNG, JPG."
        )

    # Generate unique filename to prevent collisions and sanitize
    safe_filename = f"{uuid.uuid4().hex[:12]}_{file.filename}"
    file_path = os.path.join(UPLOAD_DIR, safe_filename)

    try:
        content = await file.read()
        async with aiofiles.open(file_path, "wb") as f:
            await f.write(content)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save uploaded file: {str(exc)}"
        )

    file_url = f"/uploads/{safe_filename}"
    return {
        "filename": file.filename,
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
    db: AsyncSession = Depends(get_db)
):
    """
    Validates and stores a tutor registration in PostgreSQL.
    Status is initialized to 'pending'.
    Checks for duplicate telegram_user_id if provided.
    Forwards a verification card to the Telegram Admin Group.
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

    # Broadcast verification card to Telegram Admin Group
    await send_tutor_registration_card(tutor)

    return tutor
