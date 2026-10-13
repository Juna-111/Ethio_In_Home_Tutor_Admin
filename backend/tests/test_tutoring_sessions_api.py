import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_optional_telegram_user
from app.main import app
from app.models import Assignment, ParentRequest, Tutor, TutoringSession


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


def _parent(user_id: int) -> ParentRequest:
    return ParentRequest(
        telegram_user_id=user_id,
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
async def test_tutor_can_schedule_session_and_parent_can_read_lesson_log(
    async_client: AsyncClient, db_session: AsyncSession
):
    tutor_user_id, parent_user_id = 987654321, 812345
    tutor = _tutor(tutor_user_id)
    parent = _parent(parent_user_id)
    db_session.add_all([tutor, parent])
    await db_session.flush()
    assignment = Assignment(request_id=parent.id, tutor_id=tutor.id, status="active")
    db_session.add(assignment)
    await db_session.commit()
    await db_session.refresh(assignment)

    app.dependency_overrides[get_optional_telegram_user] = lambda: tutor_user_id
    created = await async_client.post(
        f"/api/v1/sessions/tutor/me/assignments/{assignment.id}",
        json={
            "scheduled_at": "2026-10-20T17:00:00+03:00",
            "duration_minutes": 60,
            "lesson_topic": "Linear equations",
        },
    )
    assert created.status_code == 201, created.text
    session_id = created.json()["id"]

    updated = await async_client.patch(
        f"/api/v1/sessions/tutor/me/{session_id}",
        json={
            "status": "completed",
            "attendance": "present",
            "lesson_notes": "Practised solving two-step equations.",
            "homework": "Complete questions 1-8.",
        },
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["attendance"] == "present"
    assert updated.json()["lesson_notes"] == "Practised solving two-step equations."

    app.dependency_overrides[get_optional_telegram_user] = lambda: parent_user_id
    parent_list = await async_client.get("/api/v1/sessions/parent/me")
    assert parent_list.status_code == 200, parent_list.text
    assert parent_list.json()["total"] == 1
    assert parent_list.json()["sessions"][0]["homework"] == "Complete questions 1-8."

    stored = await db_session.get(TutoringSession, session_id)
    assert stored is not None
    assert stored.status == "completed"
    assert stored.attendance == "present"
    app.dependency_overrides.pop(get_optional_telegram_user, None)


@pytest.mark.asyncio
async def test_tutor_cannot_schedule_for_another_tutors_assignment(
    async_client: AsyncClient, db_session: AsyncSession
):
    owner = _tutor(1001)
    other_tutor = _tutor(1002)
    parent = _parent(2001)
    db_session.add_all([owner, other_tutor, parent])
    await db_session.flush()
    assignment = Assignment(request_id=parent.id, tutor_id=owner.id, status="active")
    db_session.add(assignment)
    await db_session.commit()

    app.dependency_overrides[get_optional_telegram_user] = lambda: 1002
    response = await async_client.post(
        f"/api/v1/sessions/tutor/me/assignments/{assignment.id}",
        json={
            "scheduled_at": "2026-10-20T17:00:00+03:00",
            "duration_minutes": 60,
            "lesson_topic": "Linear equations",
        },
    )
    assert response.status_code == 404
    app.dependency_overrides.pop(get_optional_telegram_user, None)


@pytest.mark.asyncio
async def test_completed_session_requires_attendance(async_client: AsyncClient, db_session: AsyncSession):
    tutor = _tutor(1003)
    parent = _parent(2002)
    db_session.add_all([tutor, parent])
    await db_session.flush()
    assignment = Assignment(request_id=parent.id, tutor_id=tutor.id, status="active")
    db_session.add(assignment)
    await db_session.flush()
    session = TutoringSession(
        assignment_id=assignment.id,
        scheduled_at=__import__("datetime").datetime.fromisoformat("2026-10-20T17:00:00+03:00"),
        duration_minutes=60,
        lesson_topic="Fractions",
        created_by_tutor_id=tutor.id,
    )
    db_session.add(session)
    await db_session.commit()

    app.dependency_overrides[get_optional_telegram_user] = lambda: 1003
    response = await async_client.patch(
        f"/api/v1/sessions/tutor/me/{session.id}",
        json={"status": "completed"},
    )
    assert response.status_code == 422
    app.dependency_overrides.pop(get_optional_telegram_user, None)
