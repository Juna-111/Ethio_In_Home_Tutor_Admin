import logging
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ParentRequest, Tutor

logger = logging.getLogger("mentorlink.matcher")


def _normalize_str(val: Optional[str]) -> str:
    return val.strip().lower() if val else ""


def _normalize_list(items: Any) -> List[str]:
    if isinstance(items, list):
        return [_normalize_str(str(i)) for i in items if i]
    if isinstance(items, str):
        return [_normalize_str(items)]
    return []


async def find_top_matches(
    parent_request_id: int,
    session: AsyncSession
) -> Tuple[Optional[ParentRequest], List[Dict[str, Any]]]:
    """
    Finds and ranks the top 3 verified tutors matching a parent request.

    Hard Filters:
    - tutor.status == 'verified'
    - Gender: matches preferred_gender if not 'No preference'
    - Location: parent.location_subcity matches tutor.base_subcity OR is in coverage_areas
    - Grade: parent.student_level is in tutor.grades_qualified
    - Subjects: At least one subject overlap between parent.subjects and tutor.subjects_qualified

    Scoring / Ranking:
    - Subject overlap count * 10
    - Bonus (+2) if parent's location is tutor's base_subcity
    - Sorted by: score DESC, years_of_experience DESC, expected_fee_etb ASC
    """
    # 1. Fetch parent request
    query = select(ParentRequest).where(ParentRequest.id == parent_request_id)
    result = await session.execute(query)
    parent = result.scalar_one_or_none()

    if not parent:
        logger.warning("Parent request #%s not found for matching.", parent_request_id)
        return None, []

    # 2. Query all verified tutors
    tutors_query = select(Tutor).where(Tutor.status == "verified")
    tutors_result = await session.execute(tutors_query)
    verified_tutors = tutors_result.scalars().all()

    candidates: List[Dict[str, Any]] = []

    parent_pref_gender = _normalize_str(parent.preferred_gender)
    parent_subcity = _normalize_str(parent.location_subcity)
    parent_level = _normalize_str(parent.student_level)
    parent_subjects_norm = _normalize_list(parent.subjects)

    for tutor in verified_tutors:
        # A. Gender Hard Filter
        if parent_pref_gender and parent_pref_gender != "no preference":
            tutor_gender = _normalize_str(tutor.gender)
            if tutor_gender != parent_pref_gender:
                continue

        # B. Location Hard Filter
        tutor_base = _normalize_str(tutor.base_subcity)
        tutor_coverage = _normalize_list(tutor.coverage_areas)
        is_base_location = tutor_base == parent_subcity
        has_coverage = parent_subcity in tutor_coverage

        if not (is_base_location or has_coverage):
            continue

        # C. Grade Compatibility Hard Filter
        tutor_grades = _normalize_list(tutor.grades_qualified)
        if parent_level not in tutor_grades:
            continue

        # D. Subject Overlap Hard Filter
        tutor_subjects_norm = _normalize_list(tutor.subjects_qualified)
        matched_subjects_norm = set(parent_subjects_norm).intersection(set(tutor_subjects_norm))
        if not matched_subjects_norm:
            continue

        # Find human-readable matched subjects for display
        original_matched = [
            s for s in (parent.subjects if isinstance(parent.subjects, list) else [parent.subjects])
            if _normalize_str(str(s)) in matched_subjects_norm
        ]

        # Scoring
        subject_score = len(matched_subjects_norm) * 10
        location_bonus = 2 if is_base_location else 0
        total_score = subject_score + location_bonus

        candidates.append({
            "tutor": tutor,
            "matched_subjects": original_matched,
            "match_score": total_score,
            "is_base_location": is_base_location,
            "years_of_experience": float(tutor.years_of_experience or 0.0),
            "expected_fee_etb": float(tutor.expected_fee_etb or 0.0)
        })

    # Sort candidates by: total_score DESC, years_of_experience DESC, expected_fee_etb ASC
    candidates.sort(
        key=lambda c: (
            -c["match_score"],
            -c["years_of_experience"],
            c["expected_fee_etb"]
        )
    )

    top_3 = candidates[:3]
    logger.info(
        "Matching completed for Parent Request #%s: %s candidates evaluated, top %s returned.",
        parent_request_id, len(candidates), len(top_3)
    )
    return parent, top_3
