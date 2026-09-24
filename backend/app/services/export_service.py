import csv
import io
from typing import Any, List, Tuple
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ParentRequest, Tutor


def _format_list_or_str(val: Any) -> str:
    """Formats a list or object into a clean comma-separated string for CSV cells."""
    if isinstance(val, list):
        return ", ".join(str(item).strip() for item in val if item)
    if isinstance(val, dict):
        return ", ".join(f"{k}: {v}" for k, v in val.items())
    if val is None:
        return ""
    return str(val).strip()


async def generate_tutors_csv(db_session: AsyncSession) -> Tuple[io.BytesIO, int]:
    """
    Fetches all tutor records from the database and serializes them into
    an in-memory CSV buffer encoded with UTF-8-SIG (Excel BOM compatible).
    Returns (BytesIO, record_count).
    """
    result = await db_session.execute(select(Tutor).order_by(Tutor.id.asc()))
    tutors = result.scalars().all()

    output = io.StringIO()
    writer = csv.writer(output, dialect="excel")

    headers = [
        "ID",
        "Full Name",
        "Gender",
        "Phone Number",
        "Telegram User ID",
        "University",
        "Department",
        "Education Level / Year",
        "Subjects",
        "Target Grades",
        "Base Sub-city",
        "Coverage Areas",
        "Expected Fee (ETB/hr)",
        "Years Experience",
        "Status",
        "Registered At"
    ]
    writer.writerow(headers)

    for t in tutors:
        reg_at = t.created_at.strftime("%Y-%m-%d %H:%M:%S") if t.created_at else ""
        writer.writerow([
            t.id,
            t.full_name,
            t.gender,
            t.phone_number,
            t.telegram_user_id if t.telegram_user_id is not None else "",
            t.university,
            t.department,
            t.education_year,
            _format_list_or_str(t.subjects_qualified),
            _format_list_or_str(t.grades_qualified),
            t.base_subcity,
            _format_list_or_str(t.coverage_areas),
            t.expected_fee_etb,
            t.years_of_experience,
            t.status,
            reg_at
        ])

    csv_bytes = output.getvalue().encode("utf-8-sig")
    buffer = io.BytesIO(csv_bytes)
    buffer.seek(0)
    return buffer, len(tutors)


async def generate_parents_csv(db_session: AsyncSession) -> Tuple[io.BytesIO, int]:
    """
    Fetches all parent request records from the database and serializes them into
    an in-memory CSV buffer encoded with UTF-8-SIG (Excel BOM compatible).
    Returns (BytesIO, record_count).
    """
    result = await db_session.execute(select(ParentRequest).order_by(ParentRequest.id.asc()))
    requests = result.scalars().all()

    output = io.StringIO()
    writer = csv.writer(output, dialect="excel")

    headers = [
        "ID",
        "Parent Name",
        "Phone Number",
        "Telegram User ID",
        "Location Sub-city",
        "Landmark",
        "Student Level / Grade",
        "Subjects",
        "Schedule Days",
        "Time Slot",
        "Session Duration",
        "Budget (ETB/hr)",
        "Preferred Tutor Gender",
        "Status",
        "Assigned Tutor ID",
        "Created At"
    ]
    writer.writerow(headers)

    for req in requests:
        created_at = req.created_at.strftime("%Y-%m-%d %H:%M:%S") if req.created_at else ""
        assigned_tutor = getattr(req, "assigned_tutor_id", "N/A")
        writer.writerow([
            req.id,
            req.parent_name,
            req.phone_number,
            req.telegram_user_id if req.telegram_user_id is not None else "",
            req.location_subcity,
            req.location_landmark or "",
            req.student_level,
            _format_list_or_str(req.subjects),
            _format_list_or_str(req.schedule_days),
            req.time_slot,
            req.session_duration,
            req.budget_etb,
            req.preferred_gender,
            req.status,
            assigned_tutor,
            created_at
        ])

    csv_bytes = output.getvalue().encode("utf-8-sig")
    buffer = io.BytesIO(csv_bytes)
    buffer.seek(0)
    return buffer, len(requests)
