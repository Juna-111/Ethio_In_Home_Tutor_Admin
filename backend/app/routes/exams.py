from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.admin_auth import AdminPrincipal, require_admin
from app.auth import get_optional_telegram_user
from app.database import get_db
from app.models import MockExamAttempt, PracticeQuestion
from app.schemas import (
    MockExamAnswersUpdate,
    MockExamQuestionResult,
    MockExamResultResponse,
    MockExamStartRequest,
    MockExamStartResponse,
    PracticeQuestionAdminResponse,
    PracticeQuestionCreate,
    PracticeQuestionListResponse,
    PracticeQuestionResponse,
)

router = APIRouter(prefix="/exams", tags=["Exam Preparation"])


def _question_for_student(question: PracticeQuestion) -> PracticeQuestionResponse:
    # Deliberately excludes the correct option and explanation until submission.
    return PracticeQuestionResponse(
        id=question.id,
        subject=question.subject,
        grade_level=question.grade_level,
        topic=question.topic,
        difficulty=question.difficulty,
        prompt=question.prompt,
        options=question.options,
    )


def _admin_question(question: PracticeQuestion) -> PracticeQuestionAdminResponse:
    return PracticeQuestionAdminResponse(
        id=question.id,
        subject=question.subject,
        grade_level=question.grade_level,
        topic=question.topic,
        difficulty=question.difficulty,
        prompt=question.prompt,
        options=question.options,
        correct_option_index=question.correct_option_index,
        explanation=question.explanation,
        is_active=question.is_active,
    )


def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def _attempt_result(attempt: MockExamAttempt) -> MockExamResultResponse:
    details = attempt.result_details or []
    return MockExamResultResponse(
        attempt_id=attempt.id,
        subject=attempt.subject,
        topic=attempt.topic,
        score_percent=float(attempt.score_percent or 0),
        correct_count=sum(1 for item in details if item.get("is_correct")),
        question_count=len(attempt.question_ids or []),
        submitted_at=attempt.submitted_at or datetime.now(timezone.utc),
        expired=_utc(attempt.expires_at) <= _utc(attempt.submitted_at or datetime.now(timezone.utc)),
        results=[MockExamQuestionResult(**item) for item in details],
    )


@router.post(
    "/admin/questions",
    response_model=PracticeQuestionAdminResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_practice_question(
    payload: PracticeQuestionCreate,
    admin: AdminPrincipal = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> PracticeQuestionAdminResponse:
    if payload.correct_option_index >= len(payload.options):
        raise HTTPException(status_code=422, detail="Correct option index must refer to an existing option.")
    question = PracticeQuestion(
        subject=payload.subject,
        grade_level=payload.grade_level,
        topic=payload.topic,
        difficulty=payload.difficulty,
        prompt=payload.prompt,
        options=payload.options,
        correct_option_index=payload.correct_option_index,
        explanation=payload.explanation,
        is_active=True,
        created_by_admin_id=admin.telegram_id,
    )
    db.add(question)
    await db.commit()
    await db.refresh(question)
    return _admin_question(question)


@router.get("/admin/questions", response_model=PracticeQuestionListResponse)
async def list_admin_questions(
    subject: Optional[str] = Query(default=None, max_length=120),
    topic: Optional[str] = Query(default=None, max_length=200),
    db: AsyncSession = Depends(get_db),
    _admin: AdminPrincipal = Depends(require_admin),
) -> PracticeQuestionListResponse:
    query = select(PracticeQuestion)
    if subject and subject.strip():
        query = query.where(func.lower(PracticeQuestion.subject) == subject.strip().lower())
    if topic and topic.strip():
        query = query.where(func.lower(PracticeQuestion.topic) == topic.strip().lower())
    rows = await db.execute(query.order_by(PracticeQuestion.created_at.desc(), PracticeQuestion.id.desc()))
    questions = rows.scalars().all()
    return PracticeQuestionListResponse(questions=[_question_for_student(q) for q in questions], total=len(questions))


@router.patch("/admin/questions/{question_id}/active")
async def set_question_active(
    question_id: int,
    active: bool,
    db: AsyncSession = Depends(get_db),
    _admin: AdminPrincipal = Depends(require_admin),
) -> dict:
    question = await db.get(PracticeQuestion, question_id)
    if question is None:
        raise HTTPException(status_code=404, detail="Question not found.")
    question.is_active = active
    await db.commit()
    return {"ok": True, "question_id": question.id, "is_active": question.is_active}


@router.get("/questions", response_model=PracticeQuestionListResponse)
async def list_practice_questions(
    subject: Optional[str] = Query(default=None, max_length=120),
    topic: Optional[str] = Query(default=None, max_length=200),
    grade_level: Optional[str] = Query(default=None, max_length=100),
    limit: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    verified_user_id: Optional[int] = Depends(get_optional_telegram_user),
) -> PracticeQuestionListResponse:
    if verified_user_id is None:
        raise HTTPException(status_code=401, detail="Telegram Mini App authentication is required.")
    query = select(PracticeQuestion).where(PracticeQuestion.is_active.is_(True))
    if subject and subject.strip():
        query = query.where(func.lower(PracticeQuestion.subject) == subject.strip().lower())
    if topic and topic.strip():
        query = query.where(func.lower(PracticeQuestion.topic) == topic.strip().lower())
    if grade_level and grade_level.strip():
        query = query.where(func.lower(PracticeQuestion.grade_level) == grade_level.strip().lower())
    rows = await db.execute(query.order_by(PracticeQuestion.subject, PracticeQuestion.topic, PracticeQuestion.id).limit(limit))
    questions = rows.scalars().all()
    return PracticeQuestionListResponse(questions=[_question_for_student(q) for q in questions], total=len(questions))


@router.post("/attempts", response_model=MockExamStartResponse, status_code=status.HTTP_201_CREATED)
async def start_mock_exam(
    payload: MockExamStartRequest,
    db: AsyncSession = Depends(get_db),
    verified_user_id: Optional[int] = Depends(get_optional_telegram_user),
) -> MockExamStartResponse:
    if verified_user_id is None:
        raise HTTPException(status_code=401, detail="Telegram Mini App authentication is required.")
    query = select(PracticeQuestion).where(
        PracticeQuestion.is_active.is_(True),
        func.lower(PracticeQuestion.subject) == payload.subject.strip().lower(),
    )
    if payload.topic and payload.topic.strip():
        query = query.where(func.lower(PracticeQuestion.topic) == payload.topic.strip().lower())
    if payload.grade_level and payload.grade_level.strip():
        query = query.where(func.lower(PracticeQuestion.grade_level) == payload.grade_level.strip().lower())
    rows = await db.execute(query.order_by(func.random()).limit(payload.question_count))
    questions = rows.scalars().all()
    if len(questions) < payload.question_count:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Only {len(questions)} matching questions are available; {payload.question_count} requested.",
        )

    now = datetime.now(timezone.utc)
    duration = payload.time_limit_minutes * 60
    attempt = MockExamAttempt(
        telegram_user_id=verified_user_id,
        subject=payload.subject.strip(),
        topic=payload.topic.strip() if payload.topic and payload.topic.strip() else None,
        question_ids=[q.id for q in questions],
        answers={},
        time_limit_seconds=duration,
        started_at=now,
        expires_at=now + timedelta(seconds=duration),
    )
    db.add(attempt)
    await db.commit()
    await db.refresh(attempt)
    return MockExamStartResponse(
        attempt_id=attempt.id,
        subject=attempt.subject,
        topic=attempt.topic,
        started_at=attempt.started_at,
        expires_at=attempt.expires_at,
        time_limit_seconds=attempt.time_limit_seconds,
        questions=[_question_for_student(q) for q in questions],
    )


@router.patch("/attempts/{attempt_id}/answers")
async def save_mock_exam_answers(
    attempt_id: int,
    payload: MockExamAnswersUpdate,
    db: AsyncSession = Depends(get_db),
    verified_user_id: Optional[int] = Depends(get_optional_telegram_user),
) -> dict:
    if verified_user_id is None:
        raise HTTPException(status_code=401, detail="Telegram Mini App authentication is required.")
    attempt = await db.scalar(
        select(MockExamAttempt).where(
            MockExamAttempt.id == attempt_id,
            MockExamAttempt.telegram_user_id == verified_user_id,
        )
    )
    if attempt is None:
        raise HTTPException(status_code=404, detail="Mock exam attempt not found.")
    if attempt.submitted_at is not None:
        raise HTTPException(status_code=409, detail="This mock exam has already been submitted.")
    if _utc(attempt.expires_at) <= datetime.now(timezone.utc):
        raise HTTPException(status_code=409, detail="The exam time has expired. Submit the attempt to see your result.")

    question_ids = {str(qid) for qid in attempt.question_ids}
    if any(key not in question_ids for key in payload.answers):
        raise HTTPException(status_code=422, detail="Answers may only reference questions in this attempt.")
    questions_result = await db.execute(
        select(PracticeQuestion).where(PracticeQuestion.id.in_(attempt.question_ids))
    )
    questions = {str(q.id): q for q in questions_result.scalars().all()}
    for key, option_index in payload.answers.items():
        question = questions.get(key)
        if question is None or option_index >= len(question.options):
            raise HTTPException(status_code=422, detail=f"Invalid answer option for question {key}.")
    answers = dict(attempt.answers or {})
    answers.update(payload.answers)
    attempt.answers = answers
    await db.commit()
    return {"ok": True, "saved_answers": len(answers)}


@router.post("/attempts/{attempt_id}/submit", response_model=MockExamResultResponse)
async def submit_mock_exam(
    attempt_id: int,
    db: AsyncSession = Depends(get_db),
    verified_user_id: Optional[int] = Depends(get_optional_telegram_user),
) -> MockExamResultResponse:
    if verified_user_id is None:
        raise HTTPException(status_code=401, detail="Telegram Mini App authentication is required.")
    attempt = await db.scalar(
        select(MockExamAttempt).where(
            MockExamAttempt.id == attempt_id,
            MockExamAttempt.telegram_user_id == verified_user_id,
        )
    )
    if attempt is None:
        raise HTTPException(status_code=404, detail="Mock exam attempt not found.")
    if attempt.submitted_at is not None:
        return _attempt_result(attempt)

    question_result = await db.execute(select(PracticeQuestion).where(PracticeQuestion.id.in_(attempt.question_ids)))
    question_map = {q.id: q for q in question_result.scalars().all()}
    saved_answers = attempt.answers or {}
    results = []
    correct = 0
    for question_id in attempt.question_ids:
        question = question_map.get(question_id)
        if question is None:
            continue
        selected = saved_answers.get(str(question_id), saved_answers.get(question_id))
        is_correct = selected is not None and selected == question.correct_option_index
        correct += int(is_correct)
        results.append({
            "question_id": question.id,
            "prompt": question.prompt,
            "options": question.options,
            "selected_option_index": selected,
            "correct_option_index": question.correct_option_index,
            "is_correct": is_correct,
            "explanation": question.explanation,
        })
    total = len(results)
    attempt.score_percent = round((correct / total) * 100, 2) if total else 0.0
    attempt.result_details = results
    attempt.submitted_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(attempt)
    return _attempt_result(attempt)
