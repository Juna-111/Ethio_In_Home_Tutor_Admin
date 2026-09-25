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


GRADE_STAGE_MAP = {
    # Primary Lower (Grades 1-4)
    "grade 1": {"primary_lower"},
    "grade 2": {"primary_lower"},
    "grade 3": {"primary_lower"},
    "grade 4": {"primary_lower"},
    "primary 1-4": {"primary_lower"},
    "primary (1-4)": {"primary_lower"},
    "1-4": {"primary_lower"},
    "primary 1": {"primary_lower"},
    "primary 2": {"primary_lower"},
    "primary 3": {"primary_lower"},
    "primary 4": {"primary_lower"},

    # Primary Upper (Grades 5-8)
    "grade 5": {"primary_upper"},
    "grade 6": {"primary_upper"},
    "grade 7": {"primary_upper"},
    "grade 8": {"primary_upper"},
    "primary 5-8": {"primary_upper"},
    "primary (5-8)": {"primary_upper"},
    "5-8": {"primary_upper"},
    "middle school": {"primary_upper"},
    "primary 5": {"primary_upper"},
    "primary 6": {"primary_upper"},
    "primary 7": {"primary_upper"},
    "primary 8": {"primary_upper"},

    # High School (Grades 9-10)
    "grade 9": {"high_school"},
    "grade 10": {"high_school"},
    "high school 9-10": {"high_school"},
    "high school (9-10)": {"high_school"},
    "9-10": {"high_school"},
    "high school": {"high_school"},
    "secondary school": {"high_school"},

    # Preparatory (Grades 11-12)
    "grade 11": {"prep"},
    "grade 12": {"prep"},
    "prep 11-12": {"prep"},
    "prep (11-12)": {"prep"},
    "11-12": {"prep"},
    "prep": {"prep"},
    "preparatory": {"prep"},
    "preparatory (11-12)": {"prep"},

    # Higher Education
    "freshman": {"higher_ed"},
    "remediation": {"higher_ed"},
    "college": {"higher_ed"},
    "university": {"higher_ed"},
    "higher education": {"higher_ed"},
}


def _get_canonical_stages(val: str) -> set:
    import re
    if not val:
        return set()
    v = val.strip().lower()

    if v in GRADE_STAGE_MAP:
        return set(GRADE_STAGE_MAP[v])

    stages = set()
    if any(k in v for k in ["freshman", "remediation", "university", "college"]):
        stages.add("higher_ed")
    if re.search(r"\b(11|12|prep|preparatory)\b", v):
        stages.add("prep")
    if re.search(r"\b(9|10|high\s*school)\b", v):
        stages.add("high_school")
    if re.search(r"\b(5|6|7|8)\b", v) or "primary 5-8" in v or "primary (5-8)" in v or "5-8" in v:
        stages.add("primary_upper")
    if re.search(r"\b(1|2|3|4)\b", v) or "primary 1-4" in v or "primary (1-4)" in v or "1-4" in v:
        stages.add("primary_lower")

    return stages


def _are_grades_compatible(parent_level_norm: str, tutor_grades_norm: List[str]) -> bool:
    """
    Checks if a tutor is qualified for a parent's student level,
    either through exact match or shared educational stage.
    Never uses raw substring matching to avoid Grade 1 matching Grade 10-12.
    """
    if not parent_level_norm:
        return True

    # 1. Direct exact match
    if parent_level_norm in tutor_grades_norm:
        return True

    parent_stages = _get_canonical_stages(parent_level_norm)
    if not parent_stages:
        return False

    tutor_stages = set()
    for tg in tutor_grades_norm:
        if tg == parent_level_norm:
            return True
        tutor_stages.update(_get_canonical_stages(tg))

    return bool(parent_stages & tutor_stages)


async def get_tiered_matches(
    parent_request_id: int,
    session: AsyncSession
) -> Tuple[Optional[ParentRequest], Dict[str, List[Dict[str, Any]]]]:
    """
    Categorizes verified tutors for a parent request into three intuitive radar tiers:
    - Tier 1 (Perfect Fit): Direct base sub-city, gender preference match, fee <= budget.
    - Tier 2 (Commute / Proximity Match): Sub-city in coverage areas, subject match, fee <= budget * 1.20.
    - Tier 3 (Flexible Alternatives): Subject match, grade compatible, differs on gender or fee exceeds up to budget * 1.35.

    Candidates within each tier are sorted by:
    years_of_experience DESC, expected_fee_etb ASC.
    Each tier is capped at the top 2 candidates.
    """
    query = select(ParentRequest).where(ParentRequest.id == parent_request_id)
    result = await session.execute(query)
    parent = result.scalar_one_or_none()

    empty_result: Dict[str, List[Dict[str, Any]]] = {
        "tier1": [],
        "tier2": [],
        "tier3": []
    }

    if not parent:
        logger.warning("Parent request #%s not found for tiered matching.", parent_request_id)
        return None, empty_result

    tutors_query = select(Tutor).where(
        Tutor.status == "verified",
        Tutor.is_paused.is_(False),
    ).order_by(Tutor.id.asc())
    tutors_result = await session.execute(tutors_query)
    verified_tutors = tutors_result.scalars().all()

    parent_pref_gender = _normalize_str(parent.preferred_gender)
    gender_strict = parent_pref_gender and parent_pref_gender not in ("no preference", "none")
    parent_subcity = _normalize_str(parent.location_subcity)
    parent_level = _normalize_str(parent.student_level)
    parent_subjects_norm = _normalize_list(parent.subjects)
    budget = float(parent.budget_etb or 0.0)

    tier1_candidates: List[Dict[str, Any]] = []
    tier2_candidates: List[Dict[str, Any]] = []
    tier3_candidates: List[Dict[str, Any]] = []

    for tutor in verified_tutors:
        # Mandatory Baseline: Grade level compatibility check
        tutor_grades_norm = _normalize_list(tutor.grades_qualified)
        if not _are_grades_compatible(parent_level, tutor_grades_norm):
            continue

        # Mandatory Baseline: At least one subject overlap
        tutor_subjects_norm = _normalize_list(tutor.subjects_qualified)
        matched_subjects_norm = set(parent_subjects_norm).intersection(set(tutor_subjects_norm))
        if not matched_subjects_norm:
            continue

        original_matched = [
            s for s in (parent.subjects if isinstance(parent.subjects, list) else [parent.subjects])
            if _normalize_str(str(s)) in matched_subjects_norm
        ]

        tutor_gender = _normalize_str(tutor.gender)
        gender_matches = (not gender_strict) or (tutor_gender == parent_pref_gender)

        tutor_base = _normalize_str(tutor.base_subcity)
        tutor_coverage = _normalize_list(tutor.coverage_areas)
        is_base_subcity = (tutor_base == parent_subcity)
        is_in_coverage = (parent_subcity in tutor_coverage)
        fee = float(tutor.expected_fee_etb or 0.0)
        exp = float(tutor.years_of_experience or 0.0)
        match_reasons = [f"Subject overlap: {len(matched_subjects_norm)}"]
        if is_base_subcity:
            match_reasons.append("Tutor is based in the requested subcity")
        elif is_in_coverage:
            match_reasons.append("Tutor covers the requested subcity")
        if gender_matches:
            match_reasons.append("Gender preference matched")
        if budget == 0.0 or fee <= budget:
            match_reasons.append("Fee is within budget")
        else:
            match_reasons.append(f"Fee is {((fee - budget) / budget * 100):.0f}% over budget")

        candidate_data = {
            "tutor": tutor,
            "matched_subjects": original_matched,
            "years_of_experience": exp,
            "expected_fee_etb": fee,
            "is_base_location": is_base_subcity,
            "match_score": len(matched_subjects_norm) * 10 + (2 if is_base_subcity else 0),
            "match_reasons": match_reasons,
        }

        # Check Tier 1: Perfect Fit
        # Sub-city matches directly, gender matches, fee <= budget
        if is_base_subcity and gender_matches and (fee <= budget or budget == 0.0):
            tier1_candidates.append(candidate_data)
            continue

        # Check Tier 2: Commute / Proximity
        # Sub-city in coverage, gender matches, fee <= budget * 1.20
        max_budget_tier2 = budget * 1.20 if budget > 0.0 else fee
        if (is_in_coverage or is_base_subcity) and gender_matches and (fee <= max_budget_tier2):
            tier2_candidates.append(candidate_data)
            continue

        # Check Tier 3: Flexible Alternatives
        # Must have location overlap (base or coverage), but differs on gender OR exceeds budget up to +35%
        max_budget_tier3 = budget * 1.35 if budget > 0.0 else fee
        if (is_base_subcity or is_in_coverage) and (fee <= max_budget_tier3):
            notes = []
            if not gender_matches:
                notes.append("Gender flex")
            if budget > 0.0 and fee > budget:
                notes.append(f"+{((fee - budget) / budget * 100):.0f}% budget")
            candidate_data["flex_note"] = ", ".join(notes) if notes else "Flex match"
            tier3_candidates.append(candidate_data)

    # Sort each tier by years_of_experience DESC, expected_fee_etb ASC, tutor ID.
    sort_key = lambda c: (-c["years_of_experience"], c["expected_fee_etb"], c["tutor"].id)
    tier1_candidates.sort(key=sort_key)
    tier2_candidates.sort(key=sort_key)
    tier3_candidates.sort(key=sort_key)

    tiered_matches = {
        "tier1": tier1_candidates[:2],
        "tier2": tier2_candidates[:2],
        "tier3": tier3_candidates[:2],
    }

    total_count = sum(len(v) for v in tiered_matches.values())
    logger.info(
        "Tiered matching for Parent Request #%s completed: T1=%s, T2=%s, T3=%s (total=%s).",
        parent_request_id, len(tiered_matches["tier1"]), len(tiered_matches["tier2"]), len(tiered_matches["tier3"]), total_count
    )

    return parent, tiered_matches


async def find_top_matches(
    parent_request_id: int,
    session: AsyncSession
) -> Tuple[Optional[ParentRequest], List[Dict[str, Any]]]:
    """
    Backward-compatible wrapper: returns a flattened list of the top 3 matches
    derived from tiered matching. Strictly respects preferred_gender when specified.
    """
    parent, tiered = await get_tiered_matches(parent_request_id, session)
    if not parent:
        return None, []

    combined = tiered["tier1"] + tiered["tier2"] + tiered["tier3"]

    # In strict mode (find_top_matches), enforce gender preference if parent requested one
    parent_pref_gender = _normalize_str(parent.preferred_gender)
    if parent_pref_gender and parent_pref_gender not in ("no preference", "none"):
        combined = [c for c in combined if _normalize_str(c["tutor"].gender) == parent_pref_gender]

    # Re-sort combined by match_score DESC, exp DESC, fee ASC for backward compatibility
    combined.sort(key=lambda c: (-c.get("match_score", 0), -c["years_of_experience"], c["expected_fee_etb"]))
    return parent, combined[:3]
