from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_optional_telegram_user
from app.database import get_db
from app.models import (
    Assignment,
    Child,
    DiagnosticAssessment,
    LearnerProfile,
    ParentRequest,
    Tutor,
)
from app.schemas import (
    DiagnosticAssessmentCreate,
    DiagnosticAssessmentListResponse,
    DiagnosticAssessmentResponse,
    LearnerProfileCreate,
    LearnerProfileResponse,
    LearnerProfileUpdate,
)

router = APIRouter(prefix="/learning", tags=["Learning Profiles and Diagnostics"])


def _profile_response(profile: LearnerProfile, child: Child) -> LearnerProfileResponse:
    return LearnerProfileResponse(
        id=profile.id,
        child_id=child.id,
        learner_name=child.name,
        current_level=profile.current_level,
        subjects=profile.subjects or [],
        learning_goals=profile.learning_goals,
        strengths=profile.strengths or [],
        focus_areas=profile.focus_areas or [],
        learning_preferences=profile.learning_preferences,
        created_at=profile.created_at,
        updated_at=profile.updated_at,
    )


def _assessment_response(
    assessment: DiagnosticAssessment,
    learner_name: str,
) -> DiagnosticAssessmentResponse:
    return DiagnosticAssessmentResponse(
        id=assessment.id,
        assignment_id=assessment.assignment_id,
        request_id=assessment.request_id,
        learner_name=learner_name,
        subject=assessment.subject,
        assessment_type=assessment.assessment_type,
        score_percent=assessment.score_percent,
        strengths=assessment.strengths or [],
        focus_areas=assessment.focus_areas or [],
        notes=assessment.notes,
        next_steps=assessment.next_steps,
        assessed_at=assessment.assessed_at,
    )


async def _require_user(user_id: Optional[int]) -> int:
    if user_id is None:
        raise HTTPException(status_code=401, detail="Telegram Mini App authentication is required.")
    return user_id


@router.get("/parent/me/learners", response_model=list[LearnerProfileResponse])
async def list_learner_profiles(
    db: AsyncSession = Depends(get_db),
    verified_user_id: Optional[int] = Depends(get_optional_telegram_user),
) -> list[LearnerProfileResponse]:
    parent_id = await _require_user(verified_user_id)
    result = await db.execute(
        select(LearnerProfile, Child)
        .join(Child, LearnerProfile.child_id == Child.id)
        .where(LearnerProfile.parent_telegram_user_id == parent_id, Child.is_active.is_(True))
        .order_by(LearnerProfile.updated_at.desc())
    )
    return [_profile_response(profile, child) for profile, child in result.all()]


@router.post(
    "/parent/me/learners",
    response_model=LearnerProfileResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_learner_profile(
    payload: LearnerProfileCreate,
    db: AsyncSession = Depends(get_db),
    verified_user_id: Optional[int] = Depends(get_optional_telegram_user),
) -> LearnerProfileResponse:
    parent_id = await _require_user(verified_user_id)
    normalized_name = " ".join(payload.learner_name.split()).casefold()
    child = await db.scalar(
        select(Child).where(
            Child.parent_telegram_user_id == parent_id,
            Child.normalized_name == normalized_name,
            Child.is_active.is_(True),
        )
    )
    if child is None:
        child = Child(
            parent_telegram_user_id=parent_id,
            name=" ".join(payload.learner_name.split()),
            normalized_name=normalized_name,
            is_active=True,
        )
        db.add(child)
        await db.flush()

    existing = await db.scalar(select(LearnerProfile).where(LearnerProfile.child_id == child.id))
    if existing is not None:
        raise HTTPException(status_code=409, detail="A learning profile already exists for this learner. Update the existing profile instead.")

    profile = LearnerProfile(
        child_id=child.id,
        parent_telegram_user_id=parent_id,
        current_level=payload.current_level,
        subjects=payload.subjects,
        learning_goals=payload.learning_goals,
        strengths=payload.strengths,
        focus_areas=payload.focus_areas,
        learning_preferences=payload.learning_preferences,
    )
    db.add(profile)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=409, detail="A learning profile already exists for this learner.")
    await db.refresh(profile)
    return _profile_response(profile, child)


@router.patch("/parent/me/learners/{profile_id}", response_model=LearnerProfileResponse)
async def update_learner_profile(
    profile_id: int,
    payload: LearnerProfileUpdate,
    db: AsyncSession = Depends(get_db),
    verified_user_id: Optional[int] = Depends(get_optional_telegram_user),
) -> LearnerProfileResponse:
    parent_id = await _require_user(verified_user_id)
    result = await db.execute(
        select(LearnerProfile, Child)
        .join(Child, LearnerProfile.child_id == Child.id)
        .where(
            LearnerProfile.id == profile_id,
            LearnerProfile.parent_telegram_user_id == parent_id,
            Child.parent_telegram_user_id == parent_id,
        )
    )
    row = result.first()
    if row is None:
        raise HTTPException(status_code=404, detail="Learner profile not found.")
    profile, child = row
    changes = payload.model_dump(exclude_unset=True)
    if not changes:
        raise HTTPException(status_code=422, detail="Provide at least one field to update.")
    for field, value in changes.items():
        if isinstance(value, str) and field in {"current_level", "learning_goals", "learning_preferences"}:
            value = value.strip()
        setattr(profile, field, value)
    profile.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(profile)
    return _profile_response(profile, child)


@router.post(
    "/tutor/me/assignments/{assignment_id}/assessments",
    response_model=DiagnosticAssessmentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_diagnostic_assessment(
    assignment_id: int,
    payload: DiagnosticAssessmentCreate,
    db: AsyncSession = Depends(get_db),
    verified_user_id: Optional[int] = Depends(get_optional_telegram_user),
) -> DiagnosticAssessmentResponse:
    tutor_user_id = await _require_user(verified_user_id)
    tutor = await db.scalar(select(Tutor).where(Tutor.telegram_user_id == tutor_user_id))
    if tutor is None:
        raise HTTPException(status_code=404, detail="Tutor profile not found for this Telegram account.")
    assignment = await db.scalar(
        select(Assignment).where(
            Assignment.id == assignment_id,
            Assignment.tutor_id == tutor.id,
            Assignment.status == "active",
        )
    )
    if assignment is None:
        raise HTTPException(status_code=404, detail="Active assignment not found for this tutor.")
    request = await db.get(ParentRequest, assignment.request_id)
    if request is None:
        raise HTTPException(status_code=404, detail="Assigned tutoring request not found.")
    child = await db.get(Child, request.child_id) if request.child_id else None
    assessment = DiagnosticAssessment(
        assignment_id=assignment.id,
        request_id=request.id,
        child_id=child.id if child else None,
        created_by_tutor_id=tutor.id,
        subject=payload.subject,
        assessment_type=payload.assessment_type,
        score_percent=payload.score_percent,
        strengths=payload.strengths,
        focus_areas=payload.focus_areas,
        notes=payload.notes,
        next_steps=payload.next_steps,
    )
    db.add(assessment)
    await db.commit()
    await db.refresh(assessment)
    return _assessment_response(assessment, child.name if child else request.student_level)


@router.get("/parent/me/assessments", response_model=DiagnosticAssessmentListResponse)
async def list_parent_assessments(
    db: AsyncSession = Depends(get_db),
    verified_user_id: Optional[int] = Depends(get_optional_telegram_user),
) -> DiagnosticAssessmentListResponse:
    parent_id = await _require_user(verified_user_id)
    result = await db.execute(
        select(DiagnosticAssessment, ParentRequest, Child)
        .join(ParentRequest, DiagnosticAssessment.request_id == ParentRequest.id)
        .outerjoin(Child, DiagnosticAssessment.child_id == Child.id)
        .where(ParentRequest.telegram_user_id == parent_id)
        .order_by(DiagnosticAssessment.assessed_at.desc(), DiagnosticAssessment.id.desc())
    )
    items = [
        _assessment_response(assessment, child.name if child else request.student_level)
        for assessment, request, child in result.all()
    ]
    return DiagnosticAssessmentListResponse(assessments=items, total=len(items))
