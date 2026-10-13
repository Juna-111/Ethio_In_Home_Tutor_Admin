import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_optional_telegram_user
from app.main import app
from app.models import Assignment, Child, DiagnosticAssessment, ParentRequest, Tutor


def _tutor(user_id: int) -> Tutor:
    return Tutor(
        telegram_user_id=user_id,
        full_name="Sara Tadesse",
        gender="Female",
        phone_number="+251922334455",
        university="Addis Ababa University",
        department="Mathematics",
        education_year="3rd Year",
        subjects_qualified=["Maths"],
        grades_qualified=["High School 9-10"],
        years_of_experience=2,
        expected_fee_etb=300,
        base_subcity="Bole",
        coverage_areas=["Bole"],
        availability_schedule={"weekdays": "evenings"},
        status="verified",
        is_paused=False,
    )


def _parent(user_id: int, child_id=None) -> ParentRequest:
    return ParentRequest(
        telegram_user_id=user_id,
        child_id=child_id,
        parent_name="Abebe Kebede",
        phone_number="+251911223344",
        student_level="High School 9-10",
        subjects=["Maths"],
        preferred_gender="No preference",
        preferred_experience="Any",
        location_subcity="Bole",
        location_landmark=None,
        schedule_days=["Mon", "Wed"],
        time_slot="5:00 PM",
        session_duration="1 hr",
        budget_etb=300,
        status="matched",
    )


@pytest.mark.asyncio
async def test_parent_can_create_update_and_only_read_own_learner_profile(
    async_client: AsyncClient, db_session: AsyncSession
):
    app.dependency_overrides[get_optional_telegram_user] = lambda: 2001
    created = await async_client.post(
        "/api/v1/learning/parent/me/learners",
        json={
            "learner_name": "  Hana Kebede ",
            "current_level": "Grade 8",
            "subjects": ["Maths", "English"],
            "learning_goals": "Build confidence in algebra.",
            "strengths": ["Reading"],
            "focus_areas": ["Fractions"],
            "learning_preferences": "Short examples and practice.",
        },
    )
    assert created.status_code == 201, created.text
    profile = created.json()
    assert profile["learner_name"] == "Hana Kebede"
    assert profile["subjects"] == ["Maths", "English"]

    updated = await async_client.patch(
        f"/api/v1/learning/parent/me/learners/{profile['id']}",
        json={"focus_areas": ["Fractions", "Algebra"]},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["focus_areas"] == ["Fractions", "Algebra"]

    app.dependency_overrides[get_optional_telegram_user] = lambda: 2002
    hidden = await async_client.get("/api/v1/learning/parent/me/learners")
    assert hidden.status_code == 200
    assert hidden.json() == []
    forbidden_update = await async_client.patch(
        f"/api/v1/learning/parent/me/learners/{profile['id']}",
        json={"learning_goals": "A goal that belongs to someone else."},
    )
    assert forbidden_update.status_code == 404
    app.dependency_overrides.pop(get_optional_telegram_user, None)


@pytest.mark.asyncio
async def test_tutor_can_record_diagnostic_and_parent_can_only_read_owned_assessments(
    async_client: AsyncClient, db_session: AsyncSession
):
    tutor = _tutor(3001)
    db_session.add(tutor)
    await db_session.flush()
    child = Child(
        parent_telegram_user_id=4001,
        name="Hana Kebede",
        normalized_name="hana kebede",
        is_active=True,
    )
    db_session.add(child)
    await db_session.flush()
    parent_request = _parent(4001, child_id=child.id)
    other_request = _parent(4002)
    db_session.add_all([parent_request, other_request])
    await db_session.flush()
    assignment = Assignment(request_id=parent_request.id, tutor_id=tutor.id, status="active")
    db_session.add(assignment)
    await db_session.commit()

    app.dependency_overrides[get_optional_telegram_user] = lambda: 3001
    created = await async_client.post(
        f"/api/v1/learning/tutor/me/assignments/{assignment.id}/assessments",
        json={
            "subject": "Mathematics",
            "assessment_type": "baseline",
            "score_percent": 62.5,
            "strengths": ["Mental arithmetic"],
            "focus_areas": ["Fractions", "Word problems"],
            "notes": "Understands examples but needs more independent practice.",
            "next_steps": "Review fraction operations and solve five word problems.",
        },
    )
    assert created.status_code == 201, created.text
    assert created.json()["learner_name"] == "Hana Kebede"

    app.dependency_overrides[get_optional_telegram_user] = lambda: 4001
    visible = await async_client.get("/api/v1/learning/parent/me/assessments")
    assert visible.status_code == 200
    assert visible.json()["total"] == 1
    assert visible.json()["assessments"][0]["score_percent"] == 62.5

    app.dependency_overrides[get_optional_telegram_user] = lambda: 4002
    hidden = await async_client.get("/api/v1/learning/parent/me/assessments")
    assert hidden.status_code == 200
    assert hidden.json()["total"] == 0
    app.dependency_overrides.pop(get_optional_telegram_user, None)


@pytest.mark.asyncio
async def test_assessment_score_is_bounded_and_assignment_is_owner_scoped(
    async_client: AsyncClient, db_session: AsyncSession
):
    tutor = _tutor(5001)
    other_tutor = _tutor(5002)
    parent = _parent(6001)
    db_session.add_all([tutor, other_tutor, parent])
    await db_session.flush()
    assignment = Assignment(request_id=parent.id, tutor_id=tutor.id, status="active")
    db_session.add(assignment)
    await db_session.commit()

    app.dependency_overrides[get_optional_telegram_user] = lambda: 5002
    wrong_owner = await async_client.post(
        f"/api/v1/learning/tutor/me/assignments/{assignment.id}/assessments",
        json={"subject": "Maths", "score_percent": 80},
    )
    assert wrong_owner.status_code == 404

    app.dependency_overrides[get_optional_telegram_user] = lambda: 5001
    invalid_score = await async_client.post(
        f"/api/v1/learning/tutor/me/assignments/{assignment.id}/assessments",
        json={"subject": "Maths", "score_percent": 101},
    )
    assert invalid_score.status_code == 422
    app.dependency_overrides.pop(get_optional_telegram_user, None)
