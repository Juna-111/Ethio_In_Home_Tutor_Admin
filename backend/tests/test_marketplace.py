import pytest
from app.auth import get_optional_telegram_user
from app.models import MarketplaceFavorite, MatchInvite, ParentRequest, Tutor, TutorVerification


@pytest.mark.asyncio
async def test_marketplace_requires_telegram_identity(async_client):
    response = await async_client.get("/api/v1/parents/tutors")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_marketplace_discovery_ranks_and_filters_verified_tutors(async_client, db_session):
    db_session.add_all([
        ParentRequest(
            telegram_user_id=9001,
            parent_name="Parent One",
            phone_number="+251911111111",
            student_level="High School 9-10",
            subjects=["Math"],
            preferred_gender="No preference",
            preferred_experience="Any",
            location_subcity="Bole",
            location_landmark=None,
            schedule_days=["Mon"],
            time_slot="5 PM - 7 PM",
            session_duration="2 hrs",
            budget_etb=500,
            status="pending",
        ),
        Tutor(
            telegram_user_id=7001,
            full_name="Verified Match",
            gender="Female",
            phone_number="+251922222222",
            university="AAU",
            department="Mathematics",
            education_year="4th Year",
            subjects_qualified=["Math", "Physics"],
            grades_qualified=["High School 9-10"],
            years_of_experience=2,
            expected_fee_etb=400,
            base_subcity="Bole",
            coverage_areas=["Bole"],
            availability_schedule={"Mon": "5 PM - 8 PM"},
            id_document_url="id.pdf",
            entrance_result=90,
            status="verified",
            is_paused=False,
        ),
        Tutor(
            telegram_user_id=7002,
            full_name="Unverified Tutor",
            gender="Female",
            phone_number="+251933333333",
            university="AAU",
            department="Physics",
            education_year="3rd Year",
            subjects_qualified=["Math"],
            grades_qualified=["High School 9-10"],
            years_of_experience=4,
            expected_fee_etb=300,
            base_subcity="Bole",
            coverage_areas=["Bole"],
            availability_schedule={"Mon": "5 PM - 8 PM"},
            id_document_url=None,
            entrance_result=88,
            status="verified",
            is_paused=False,
        ),
    ])
    await db_session.flush()
    tutors = (await db_session.execute(__import__("sqlalchemy").select(Tutor))).scalars().all()
    verified_tutor = next(t for t in tutors if t.full_name == "Verified Match")
    unverified_tutor = next(t for t in tutors if t.full_name == "Unverified Tutor")
    db_session.add(TutorVerification(tutor_id=verified_tutor.id, id_verified=True, entrance_result_verified=True, phone_confirmed=True, claims_plausible=True))
    db_session.add(TutorVerification(tutor_id=unverified_tutor.id, id_verified=False, entrance_result_verified=False, phone_confirmed=False, claims_plausible=False))
    await db_session.commit()

    async def identity():
        return 9001
    from app.main import app
    app.dependency_overrides[get_optional_telegram_user] = identity
    try:
        response = await async_client.get("/api/v1/parents/tutors")
    finally:
        app.dependency_overrides.pop(get_optional_telegram_user, None)

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["tutors"][0]["full_name"] == "Verified Match"
    assert body["tutors"][0]["match_score"] > 0
    assert "Teaches Math" in body["tutors"][0]["match_reasons"]


@pytest.mark.asyncio
async def test_marketplace_favorite_and_application_are_parent_scoped(async_client, db_session):
    parent = ParentRequest(
        telegram_user_id=9002,
        parent_name="Parent Two",
        phone_number="+251944444444",
        student_level="Primary 5-8",
        subjects=["English"],
        preferred_gender="No preference",
        preferred_experience="Any",
        location_subcity="Kirkos",
        location_landmark=None,
        schedule_days=["Tue"],
        time_slot="4 PM - 6 PM",
        session_duration="2 hrs",
        budget_etb=450,
        status="pending",
    )
    tutor = Tutor(
        telegram_user_id=7003,
        full_name="Good Tutor",
        gender="Male",
        phone_number="+251955555555",
        university="AAU",
        department="Education",
        education_year="Graduate",
        subjects_qualified=["English"],
        grades_qualified=["Primary 5-8"],
        years_of_experience=5,
        expected_fee_etb=400,
        base_subcity="Kirkos",
        coverage_areas=["Kirkos"],
        availability_schedule={"Tue": "4 PM - 7 PM"},
        id_document_url="id.pdf",
        entrance_result=92,
        status="verified",
        is_paused=False,
    )
    db_session.add_all([parent, tutor])
    await db_session.flush()
    db_session.add(TutorVerification(tutor_id=tutor.id, id_verified=True, entrance_result_verified=True, phone_confirmed=True, claims_plausible=True))
    await db_session.commit()

    async def identity():
        return 9002
    from app.main import app
    app.dependency_overrides[get_optional_telegram_user] = identity
    try:
        fav = await async_client.post(f"/api/v1/parents/tutors/{tutor.id}/favorite")
        assert fav.status_code == 201
        apply = await async_client.post(f"/api/v1/parents/tutors/{tutor.id}/apply", json={"request_id": parent.id})
        assert apply.status_code == 201
        duplicate = await async_client.post(f"/api/v1/parents/tutors/{tutor.id}/apply", json={"request_id": parent.id})
        assert duplicate.status_code == 409
    finally:
        app.dependency_overrides.pop(get_optional_telegram_user, None)

    assert await db_session.scalar(
        __import__("sqlalchemy").select(MarketplaceFavorite).where(MarketplaceFavorite.parent_telegram_user_id == 9002, MarketplaceFavorite.tutor_id == tutor.id)
    )
    assert await db_session.scalar(
        __import__("sqlalchemy").select(MatchInvite).where(MatchInvite.request_id == parent.id, MatchInvite.tutor_id == tutor.id)
    )
