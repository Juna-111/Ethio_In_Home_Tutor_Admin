"""Canonical assignment workflow for every operator-facing assignment path.

The Admin Mini App and Telegram Admin Group must use the same business rules.
Keeping the checks here prevents one surface from silently bypassing another.
"""

from typing import Optional

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Assignment, MatchInvite, ParentRequest, Tutor, TutorVerification
from app.services.matcher import _are_grades_compatible, _normalize_list, _schedule_days


class AssignmentWorkflowError(Exception):
    def __init__(self, message: str, status_code: int = 409):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


async def assign_tutor_to_request(
    db: AsyncSession,
    *,
    request_id: int,
    tutor_id: int,
    assigned_by: str,
    require_accepted_invite: bool = True,
    commit: bool = True,
):
    """Validate and create the single authoritative assignment for a request."""

    parent = await db.get(ParentRequest, request_id)
    tutor = await db.get(Tutor, tutor_id)

    if not parent or not tutor:
        raise AssignmentWorkflowError("Request or tutor not found.", 404)

    if parent.status != "pending":
        raise AssignmentWorkflowError(f"Request is no longer pending (current status: {parent.status}).")

    if tutor.status != "verified" or tutor.is_paused:
        raise AssignmentWorkflowError("Only verified, active tutors can be assigned.")

    verification = await db.scalar(
        select(TutorVerification).where(TutorVerification.tutor_id == tutor.id)
    )
    if not verification or not all(
        (
            verification.id_verified,
            verification.entrance_result_verified,
            verification.phone_confirmed,
            verification.claims_plausible,
        )
    ):
        raise AssignmentWorkflowError("Tutor verification is incomplete.")

    invite = await db.scalar(
        select(MatchInvite).where(
            MatchInvite.request_id == request_id,
            MatchInvite.tutor_id == tutor_id,
        )
    )
    if require_accepted_invite and (not invite or invite.status != "yes"):
        raise AssignmentWorkflowError(
            "The tutor must accept the opportunity before an assignment can be finalized."
        )

    requested_subjects = set(_normalize_list(parent.subjects))
    tutor_subjects = set(_normalize_list(tutor.subjects_qualified))
    if not requested_subjects.intersection(tutor_subjects):
        raise AssignmentWorkflowError("Tutor no longer matches any requested subject.")

    tutor_grades = _normalize_list(tutor.grades_qualified)
    if not _are_grades_compatible(parent.student_level.strip().lower(), tutor_grades):
        raise AssignmentWorkflowError("Tutor no longer matches the requested grade level.")

    requested_area = (parent.location_subcity or "").strip().lower()
    tutor_base = (tutor.base_subcity or "").strip().lower()
    tutor_coverage = {v.strip().lower() for v in _normalize_list(tutor.coverage_areas)}
    if requested_area and requested_area != tutor_base and requested_area not in tutor_coverage:
        raise AssignmentWorkflowError("Tutor no longer covers the requested area.")

    preferred_gender = (parent.preferred_gender or "").strip().lower()
    if preferred_gender and preferred_gender not in {"no preference", "none"}:
        if preferred_gender != (tutor.gender or "").strip().lower():
            raise AssignmentWorkflowError("Tutor no longer matches the gender preference.")

    requested_days = _schedule_days(parent.schedule_days)
    available_days = _schedule_days(tutor.availability_schedule)
    if requested_days and available_days and not requested_days.intersection(available_days):
        raise AssignmentWorkflowError("Tutor availability no longer overlaps the requested days.")

    # Atomic request transition prevents two admins from creating competing assignments.
    result = await db.execute(
        update(ParentRequest)
        .where(ParentRequest.id == request_id, ParentRequest.status == "pending")
        .values(status="matched")
    )
    if result.rowcount != 1:
        await db.rollback()
        raise AssignmentWorkflowError("Request was changed by another operator. Refresh and try again.")

    assignment = Assignment(
        request_id=request_id,
        tutor_id=tutor_id,
        assigned_by=assigned_by,
    )
    db.add(assignment)

    if commit:
        try:
            await db.commit()
        except Exception:
            await db.rollback()
            raise
        await db.refresh(parent)
        await db.refresh(tutor)
        await db.refresh(assignment)
    else:
        await db.flush()

    return parent, tutor, assignment
