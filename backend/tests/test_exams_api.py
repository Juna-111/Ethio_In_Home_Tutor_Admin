from datetime import datetime, timedelta, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.admin_auth import AdminPrincipal, require_admin
from app.auth import get_optional_telegram_user
from app.main import app
from app.models import MockExamAttempt, PracticeQuestion


@pytest.mark.asyncio
async def test_admin_can_add_question_but_student_list_never_exposes_answer_key(
    async_client: AsyncClient, db_session: AsyncSession
):
    app.dependency_overrides[require_admin] = lambda: AdminPrincipal(telegram_id=9001, role="admin")
    created = await async_client.post(
        "/api/v1/exams/admin/questions",
        json={
            "subject": "Mathematics",
            "grade_level": "Grade 8",
            "topic": "Fractions",
            "difficulty": 2,
            "prompt": "Which fraction is equal to one half?",
            "options": ["2/4", "2/3", "3/4", "4/5"],
            "correct_option_index": 0,
            "explanation": "Two quarters simplify to one half.",
        },
    )
    assert created.status_code == 201, created.text
    assert created.json()["correct_option_index"] == 0

    app.dependency_overrides[get_optional_telegram_user] = lambda: 9002
    listing = await async_client.get("/api/v1/exams/questions?subject=Mathematics")
    assert listing.status_code == 200, listing.text
    assert listing.json()["total"] == 1
    question = listing.json()["questions"][0]
    assert question["prompt"] == "Which fraction is equal to one half?"
    assert "correct_option_index" not in question
    assert "explanation" not in question
    app.dependency_overrides.pop(require_admin, None)
    app.dependency_overrides.pop(get_optional_telegram_user, None)


@pytest.mark.asyncio
async def test_mock_exam_saves_answers_scores_server_side_and_submit_is_idempotent(
    async_client: AsyncClient, db_session: AsyncSession
):
    questions = [
        PracticeQuestion(
            subject="Mathematics", grade_level="Grade 8", topic="Fractions", difficulty=2,
            prompt="Question one?", options=["Correct", "Wrong"], correct_option_index=0,
            explanation="First option is correct.", is_active=True, created_by_admin_id=9001,
        ),
        PracticeQuestion(
            subject="Mathematics", grade_level="Grade 8", topic="Fractions", difficulty=3,
            prompt="Question two?", options=["Wrong", "Correct"], correct_option_index=1,
            explanation="Second option is correct.", is_active=True, created_by_admin_id=9001,
        ),
    ]
    db_session.add_all(questions)
    await db_session.commit()
    for question in questions:
        await db_session.refresh(question)

    app.dependency_overrides[get_optional_telegram_user] = lambda: 9010
    started = await async_client.post(
        "/api/v1/exams/attempts",
        json={"subject": "Mathematics", "topic": "Fractions", "grade_level": "Grade 8", "question_count": 2, "time_limit_minutes": 5},
    )
    assert started.status_code == 201, started.text
    data = started.json()
    assert len(data["questions"]) == 2
    assert all("correct_option_index" not in question for question in data["questions"])
    correct_indexes = {str(q.id): q.correct_option_index for q in questions}
    answers = {str(question["id"]): correct_indexes[str(question["id"])] for question in data["questions"]}

    saved = await async_client.patch(
        f"/api/v1/exams/attempts/{data['attempt_id']}/answers",
        json={"answers": answers},
    )
    assert saved.status_code == 200, saved.text
    result = await async_client.post(f"/api/v1/exams/attempts/{data['attempt_id']}/submit")
    assert result.status_code == 200, result.text
    assert result.json()["score_percent"] == 100
    assert result.json()["correct_count"] == 2
    assert all(item["is_correct"] for item in result.json()["results"])

    repeated = await async_client.post(f"/api/v1/exams/attempts/{data['attempt_id']}/submit")
    assert repeated.status_code == 200
    assert repeated.json()["score_percent"] == 100
    app.dependency_overrides.pop(get_optional_telegram_user, None)


@pytest.mark.asyncio
async def test_exam_attempt_is_private_and_expired_attempt_cannot_save_more_answers(
    async_client: AsyncClient, db_session: AsyncSession
):
    question = PracticeQuestion(
        subject="English", grade_level="Grade 7", topic="Grammar", difficulty=1,
        prompt="Choose the verb.", options=["run", "blue"], correct_option_index=0,
        explanation=None, is_active=True, created_by_admin_id=9001,
    )
    db_session.add(question)
    await db_session.commit()
    await db_session.refresh(question)

    app.dependency_overrides[get_optional_telegram_user] = lambda: 9020
    started = await async_client.post(
        "/api/v1/exams/attempts",
        json={"subject": "English", "topic": "Grammar", "question_count": 1, "time_limit_minutes": 1},
    )
    assert started.status_code == 201, started.text
    attempt_id = started.json()["attempt_id"]
    attempt = await db_session.get(MockExamAttempt, attempt_id)
    attempt.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    await db_session.commit()

    expired_save = await async_client.patch(
        f"/api/v1/exams/attempts/{attempt_id}/answers",
        json={"answers": {str(question.id): 0}},
    )
    assert expired_save.status_code == 409

    app.dependency_overrides[get_optional_telegram_user] = lambda: 9021
    hidden = await async_client.post(f"/api/v1/exams/attempts/{attempt_id}/submit")
    assert hidden.status_code == 404
    app.dependency_overrides[get_optional_telegram_user] = lambda: 9020
    submitted = await async_client.post(f"/api/v1/exams/attempts/{attempt_id}/submit")
    assert submitted.status_code == 200
    assert submitted.json()["expired"] is True
    app.dependency_overrides.pop(get_optional_telegram_user, None)
