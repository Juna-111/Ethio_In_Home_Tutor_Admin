import csv
import io
from typing import Any, List, Tuple
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Assignment, ParentRequest, Tutor


def _sanitize_cell(val: Any) -> Any:
    """Neutralizes formula injection in CSV cells for Excel compatibility."""
    if val is None:
        return ""
    if isinstance(val, (int, float)):
        return val
    s = str(val)
    if s and s[0] in ("=", "+", "-", "@", "\t", "\r"):
        return f"'{s}"
    return s


def _format_list_or_str(val: Any) -> str:
    """Formats a list or object into a clean comma-separated string for CSV cells."""
    if isinstance(val, list):
        formatted = ", ".join(str(item).strip() for item in val if item)
    elif isinstance(val, dict):
        formatted = ", ".join(f"{k}: {v}" for k, v in val.items())
    elif val is None:
        formatted = ""
    else:
        formatted = str(val).strip()
    return _sanitize_cell(formatted)


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
            _sanitize_cell(t.full_name),
            _sanitize_cell(t.gender),
            _sanitize_cell(t.phone_number),
            t.telegram_user_id if t.telegram_user_id is not None else "",
            _sanitize_cell(t.university),
            _sanitize_cell(t.department),
            _sanitize_cell(t.education_year),
            _format_list_or_str(t.subjects_qualified),
            _format_list_or_str(t.grades_qualified),
            _sanitize_cell(t.base_subcity),
            _format_list_or_str(t.coverage_areas),
            t.expected_fee_etb,
            t.years_of_experience,
            _sanitize_cell(t.status),
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

    # Query all assignments and tutors to display real assigned mentor info
    assignments_res = await db_session.execute(select(Assignment))
    assignments_map = {a.request_id: a for a in assignments_res.scalars().all()}
    tutors_res = await db_session.execute(select(Tutor))
    tutors_map = {t.id: t for t in tutors_res.scalars().all()}

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
        assignment = assignments_map.get(req.id)
        if assignment:
            t = tutors_map.get(assignment.tutor_id)
            assigned_tutor = f"{assignment.tutor_id} ({t.full_name})" if t else str(assignment.tutor_id)
        else:
            assigned_tutor = "N/A"
        writer.writerow([
            req.id,
            _sanitize_cell(req.parent_name),
            _sanitize_cell(req.phone_number),
            req.telegram_user_id if req.telegram_user_id is not None else "",
            _sanitize_cell(req.location_subcity),
            _sanitize_cell(req.location_landmark or ""),
            _sanitize_cell(req.student_level),
            _format_list_or_str(req.subjects),
            _format_list_or_str(req.schedule_days),
            _sanitize_cell(req.time_slot),
            _sanitize_cell(req.session_duration),
            req.budget_etb,
            _sanitize_cell(req.preferred_gender),
            _sanitize_cell(req.status),
            _sanitize_cell(assigned_tutor),
            created_at
        ])

    csv_bytes = output.getvalue().encode("utf-8-sig")
    buffer = io.BytesIO(csv_bytes)
    buffer.seek(0)
    return buffer, len(requests)


async def generate_assignments_csv(db_session: AsyncSession) -> Tuple[io.BytesIO, int]:
    """
    Fetches all assignment records joined with parent and tutor info
    and serializes them into an in-memory CSV buffer encoded with UTF-8-SIG.
    Returns (BytesIO, record_count).
    """
    from app.models import AuditLog

    result = await db_session.execute(select(Assignment).order_by(Assignment.id.asc()))
    assignments = result.scalars().all()

    requests_res = await db_session.execute(select(ParentRequest))
    requests_map = {r.id: r for r in requests_res.scalars().all()}

    tutors_res = await db_session.execute(select(Tutor))
    tutors_map = {t.id: t for t in tutors_res.scalars().all()}

    # Query audit logs for close events to find closed_date
    audit_res = await db_session.execute(
        select(AuditLog).where(
            AuditLog.action.in_(["close_request", "close_assignment"]),
            AuditLog.target_type.in_(["parent_request", "assignment"])
        ).order_by(AuditLog.id.desc())
    )
    closed_audit_map = {}
    for a in audit_res.scalars().all():
        if a.target_id not in closed_audit_map:
            closed_audit_map[a.target_id] = a.created_at

    output = io.StringIO()
    writer = csv.writer(output, dialect="excel")

    headers = [
        "Assignment ID",
        "Parent",
        "Tutor",
        "Subjects",
        "Status",
        "Created At",
        "Assigned Date",
        "Closed Date",
    ]
    writer.writerow(headers)

    for asmt in assignments:
        req = requests_map.get(asmt.request_id)
        tutor = tutors_map.get(asmt.tutor_id)

        parent_name = req.parent_name if req else f"Req #{asmt.request_id}"
        tutor_name = tutor.full_name if tutor else f"Tutor #{asmt.tutor_id}"
        subjects = _format_list_or_str(req.subjects) if req else ""
        status_val = asmt.status
        if req and req.status == "closed":
            status_val = "closed"

        created_str = req.created_at.strftime("%Y-%m-%d %H:%M:%S") if req and req.created_at else ""
        assigned_str = asmt.assigned_at.strftime("%Y-%m-%d %H:%M:%S") if asmt.assigned_at else ""

        closed_dt = closed_audit_map.get(asmt.request_id) or closed_audit_map.get(asmt.id)
        if not closed_dt and status_val == "closed":
            closed_dt = asmt.assigned_at
        closed_str = closed_dt.strftime("%Y-%m-%d %H:%M:%S") if (closed_dt and status_val == "closed") else ""

        writer.writerow([
            asmt.id,
            _sanitize_cell(parent_name),
            _sanitize_cell(tutor_name),
            subjects,
            _sanitize_cell(status_val),
            created_str,
            assigned_str,
            closed_str,
        ])

    csv_bytes = output.getvalue().encode("utf-8-sig")
    buffer = io.BytesIO(csv_bytes)
    buffer.seek(0)
    return buffer, len(assignments)

