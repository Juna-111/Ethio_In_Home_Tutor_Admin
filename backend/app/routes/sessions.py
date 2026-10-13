from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_optional_telegram_user
from app.database import get_db
from app.models import Assignment, ParentRequest, Tutor, TutoringSession
from app.schemas import (
    TutoringSessionCreate,
    TutoringSessionListResponse,
    TutoringSessionResponse,
    TutoringSessionUpdate,
)

router = APIRouter(prefix="/sessions", tags=["Tutoring Sessions"])


def _session_response(session: TutoringSession) -> TutoringSessionResponse:
    return TutoringSessionResponse(
        id=session.id,
        assignment_id=session.assignment_id,
        scheduled_at=session.scheduled_at,
        duration_minutes=session.duration_minutes,
        status=session.status,
        attendance=session.attendance,
        lesson_topic=session.lesson_topic,
        lesson_notes=session.lesson_notes,
        homework=session.homework,
        created_at=session.created_at,
        updated_at=session.updated_at,
    )


async def _authenticated_tutor(db: AsyncSession, user_id: Optional[int]) -> Tutor:
    if user_id is None:
        raise HTTPException(status_code=401, detail="Telegram Mini App authentication is required.")
    tutor = await db.scalar(select(Tutor).where(Tutor.telegram_user_id == user_id))
    if tutor is None:
        raise HTTPException(status_code=404, detail="Tutor profile not found for this Telegram account.")
    return tutor


@router.get("/tutor/me", response_model=TutoringSessionListResponse)
async def list_tutor_sessions(
    db: AsyncSession = Depends(get_db),
    verified_user_id: Optional[int] = Depends(get_optional_telegram_user),
) -> TutoringSessionListResponse:
    tutor = await _authenticated_tutor(db, verified_user_id)
    rows = await db.execute(
        select(TutoringSession)
        .join(Assignment, TutoringSession.assignment_id == Assignment.id)
        .where(Assignment.tutor_id == tutor.id)
        .order_by(TutoringSession.scheduled_at.asc(), TutoringSession.id.asc())
    )
    sessions = rows.scalars().all()
    return TutoringSessionListResponse(sessions=[_session_response(s) for s in sessions], total=len(sessions))


@router.post(
    "/tutor/me/assignments/{assignment_id}",
    response_model=TutoringSessionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_tutor_session(
    assignment_id: int,
    payload: TutoringSessionCreate,
    db: AsyncSession = Depends(get_db),
    verified_user_id: Optional[int] = Depends(get_optional_telegram_user),
) -> TutoringSessionResponse:
    tutor = await _authenticated_tutor(db, verified_user_id)
    assignment = await db.scalar(
        select(Assignment).where(
            Assignment.id == assignment_id,
            Assignment.tutor_id == tutor.id,
            Assignment.status == "active",
        )
    )
    if assignment is None:
        raise HTTPException(status_code=404, detail="Active assignment not found for this tutor.")

    session = TutoringSession(
        assignment_id=assignment.id,
        scheduled_at=payload.scheduled_at.astimezone(timezone.utc),
        duration_minutes=payload.duration_minutes,
        lesson_topic=payload.lesson_topic,
        created_by_tutor_id=tutor.id,
    )
    db.add(session)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A session is already scheduled for this assignment at that time.",
        )
    await db.refresh(session)
    return _session_response(session)


@router.patch("/tutor/me/{session_id}", response_model=TutoringSessionResponse)
async def update_tutor_session(
    session_id: int,
    payload: TutoringSessionUpdate,
    db: AsyncSession = Depends(get_db),
    verified_user_id: Optional[int] = Depends(get_optional_telegram_user),
) -> TutoringSessionResponse:
    tutor = await _authenticated_tutor(db, verified_user_id)
    session = await db.scalar(
        select(TutoringSession)
        .join(Assignment, TutoringSession.assignment_id == Assignment.id)
        .where(TutoringSession.id == session_id, Assignment.tutor_id == tutor.id)
    )
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found for this tutor.")

    changes = payload.model_dump(exclude_unset=True)
    if not changes:
        raise HTTPException(status_code=422, detail="Provide at least one field to update.")
    if session.status == "cancelled":
        raise HTTPException(status_code=409, detail="Cancelled sessions cannot be edited.")
    if session.status == "completed" and any(k in changes for k in ("scheduled_at", "duration_minutes")):
        raise HTTPException(status_code=409, detail="Completed sessions cannot be rescheduled.")
    if changes.get("status") == "completed":
        resulting_attendance = changes.get("attendance", session.attendance)
        if resulting_attendance == "pending":
            raise HTTPException(
                status_code=422,
                detail="Record attendance before marking a session completed.",
            )
    if changes.get("status") == "cancelled" and changes.get("attendance") in {"present", "absent"}:
        raise HTTPException(status_code=422, detail="A cancelled session cannot record present or absent attendance.")
    if changes.get("scheduled_at") is not None:
        changes["scheduled_at"] = changes["scheduled_at"].astimezone(timezone.utc)
    for field, value in changes.items():
        setattr(session, field, value)
    session.updated_at = datetime.now(timezone.utc)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A session is already scheduled for this assignment at that time.",
        )
    await db.refresh(session)
    return _session_response(session)


@router.get("/parent/me", response_model=TutoringSessionListResponse)
async def list_parent_sessions(
    db: AsyncSession = Depends(get_db),
    verified_user_id: Optional[int] = Depends(get_optional_telegram_user),
) -> TutoringSessionListResponse:
    if verified_user_id is None:
        raise HTTPException(status_code=401, detail="Telegram Mini App authentication is required.")
    rows = await db.execute(
        select(TutoringSession)
        .join(Assignment, TutoringSession.assignment_id == Assignment.id)
        .join(ParentRequest, Assignment.request_id == ParentRequest.id)
        .where(ParentRequest.telegram_user_id == verified_user_id)
        .order_by(TutoringSession.scheduled_at.asc(), TutoringSession.id.asc())
    )
    sessions = rows.scalars().all()
    return TutoringSessionListResponse(sessions=[_session_response(s) for s in sessions], total=len(sessions))
