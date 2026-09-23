from unittest.mock import AsyncMock, MagicMock
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ParentRequest, Tutor
from app.services.matcher import find_top_matches
from tests.conftest import TestingSessionLocal
import app.bot.handlers as bot_handlers


@pytest.mark.asyncio
async def test_matching_engine_filters_and_ranking(db_session: AsyncSession):
    """
    Verifies that find_top_matches strictly enforces:
    - Status == 'verified'
    - Gender matching
    - Location matching (base or coverage)
    - Grade level compatibility
    - Subject intersection
    - Correct score ranking (base location bonus + subject count)
    """
    # 1. Create a Parent Request
    parent = ParentRequest(
        parent_name="Almaz Ayana",
        phone_number="+251911001122",
        student_level="High School 9-10",
        subjects=["Maths", "Physics"],
        preferred_gender="Male",
        preferred_experience="University Student",
        location_subcity="Bole",
        location_landmark="Near Airport",
        schedule_days=["Mon", "Wed"],
        time_slot="4:00 PM - 6:00 PM",
        session_duration="2 hrs",
        budget_etb=4000.0,
        status="pending"
    )
    db_session.add(parent)
    await db_session.commit()
    await db_session.refresh(parent)

    # 2. Create Candidate Tutors
    # Candidate A: Verified, Male, Base Bole (Bonus), 2 subjects match -> Top 1
    tutor_a = Tutor(
        full_name="Kenenisa Bekele",
        gender="Male",
        phone_number="+251911111111",
        university="AAU",
        department="Physics",
        education_year="4th Year",
        subjects_qualified=["Maths", "Physics", "Chemistry"],
        grades_qualified=["High School 9-10"],
        years_of_experience=3.0,
        expected_fee_etb=400.0,
        base_subcity="Bole",
        coverage_areas=["Bole", "Yeka"],
        availability_schedule="Evenings",
        status="verified"
    )

    # Candidate B: Verified, Male, Base Yeka, Coverage Bole, 1 subject match (Maths) -> Top 2
    tutor_b = Tutor(
        full_name="Haile Gebrselassie",
        gender="Male",
        phone_number="+251922222222",
        university="AAU",
        department="Mathematics",
        education_year="Graduate",
        subjects_qualified=["Maths"],
        grades_qualified=["High School 9-10", "Prep 11-12"],
        years_of_experience=5.0,
        expected_fee_etb=450.0,
        base_subcity="Yeka",
        coverage_areas=["Bole", "Yeka"],
        availability_schedule="Weekends",
        status="verified"
    )

    # Candidate C: Filtered OUT because status is 'pending'
    tutor_c = Tutor(
        full_name="Derartu Tulu",
        gender="Male",
        phone_number="+251933333333",
        university="AAU",
        department="Maths",
        education_year="3rd Year",
        subjects_qualified=["Maths", "Physics"],
        grades_qualified=["High School 9-10"],
        years_of_experience=2.0,
        expected_fee_etb=300.0,
        base_subcity="Bole",
        coverage_areas=["Bole"],
        availability_schedule="Flexible",
        status="pending"  # NOT verified!
    )

    # Candidate D: Filtered OUT because gender is 'Female' (Parent requested 'Male')
    tutor_d = Tutor(
        full_name="Tirunesh Dibaba",
        gender="Female",
        phone_number="+251944444444",
        university="AAU",
        department="Engineering",
        education_year="4th Year",
        subjects_qualified=["Maths", "Physics"],
        grades_qualified=["High School 9-10"],
        years_of_experience=4.0,
        expected_fee_etb=400.0,
        base_subcity="Bole",
        coverage_areas=["Bole"],
        availability_schedule="Weekdays",
        status="verified"
    )

    # Candidate E: Filtered OUT because location has no overlap with Bole
    tutor_e = Tutor(
        full_name="Mamo Wolde",
        gender="Male",
        phone_number="+251955555555",
        university="AAU",
        department="Physics",
        education_year="Graduate",
        subjects_qualified=["Maths", "Physics"],
        grades_qualified=["High School 9-10"],
        years_of_experience=6.0,
        expected_fee_etb=350.0,
        base_subcity="Akaki",
        coverage_areas=["Akaki", "Nifas Silk"],
        availability_schedule="Anytime",
        status="verified"
    )

    # Candidate F: Filtered OUT because grade does not match High School 9-10
    tutor_f = Tutor(
        full_name="Sileshi Sihine",
        gender="Male",
        phone_number="+251966666666",
        university="AAU",
        department="Physics",
        education_year="2nd Year",
        subjects_qualified=["Maths", "Physics"],
        grades_qualified=["Primary 1-4"],  # Does not teach 9-10
        years_of_experience=1.0,
        expected_fee_etb=250.0,
        base_subcity="Bole",
        coverage_areas=["Bole"],
        availability_schedule="Evenings",
        status="verified"
    )

    db_session.add_all([tutor_a, tutor_b, tutor_c, tutor_d, tutor_e, tutor_f])
    await db_session.commit()

    # Run matcher
    found_parent, matches = await find_top_matches(parent.id, db_session)
    assert found_parent is not None
    assert len(matches) == 2

    # Verify rank 1: Kenenisa Bekele (2 subjects * 10 + 2 bonus = 22 score)
    assert matches[0]["tutor"].full_name == "Kenenisa Bekele"
    assert matches[0]["match_score"] == 22
    assert "Maths" in matches[0]["matched_subjects"]
    assert "Physics" in matches[0]["matched_subjects"]

    # Verify rank 2: Haile Gebrselassie (1 subject * 10 = 10 score)
    assert matches[1]["tutor"].full_name == "Haile Gebrselassie"
    assert matches[1]["match_score"] == 10
    assert matches[1]["matched_subjects"] == ["Maths"]


@pytest.mark.asyncio
async def test_matching_no_gender_preference(db_session: AsyncSession):
    """Verifies that 'No preference' allows both male and female verified tutors to match."""
    parent = ParentRequest(
        parent_name="Genzebe Dibaba",
        phone_number="+251911990099",
        student_level="Prep 11-12",
        subjects=["Chemistry"],
        preferred_gender="No preference",
        preferred_experience="Senior Teacher",
        location_subcity="Yeka",
        schedule_days=["Sat", "Sun"],
        time_slot="2:00 PM - 4:00 PM",
        session_duration="2 hrs",
        budget_etb=5000.0,
        status="pending"
    )
    db_session.add(parent)
    await db_session.commit()
    await db_session.refresh(parent)

    female_tutor = Tutor(
        full_name="Meseret Defar",
        gender="Female",
        phone_number="+251977889900",
        university="AAU",
        department="Chemistry",
        education_year="Graduate",
        subjects_qualified=["Chemistry"],
        grades_qualified=["Prep 11-12"],
        years_of_experience=7.0,
        expected_fee_etb=500.0,
        base_subcity="Yeka",
        coverage_areas=["Yeka"],
        availability_schedule="Weekends",
        status="verified"
    )
    db_session.add(female_tutor)
    await db_session.commit()

    _, matches = await find_top_matches(parent.id, db_session)
    assert len(matches) >= 1
    assert any(m["tutor"].full_name == "Meseret Defar" for m in matches)


@pytest.mark.asyncio
async def test_approve_tutor_callback_updates_db_and_notifies(db_session: AsyncSession, monkeypatch):
    """Verifies that approving a tutor updates status to 'verified' and dispatches DM."""
    tutor = Tutor(
        telegram_user_id=777888999,
        full_name="Tesfaye Abera",
        gender="Male",
        phone_number="+251911224466",
        university="AAU",
        department="Economics",
        education_year="Graduate",
        subjects_qualified=["Economics"],
        grades_qualified=["High School 9-10"],
        years_of_experience=2.0,
        expected_fee_etb=300.0,
        base_subcity="Kirkos",
        coverage_areas=["Kirkos"],
        availability_schedule="Flexible",
        status="pending"
    )
    db_session.add(tutor)
    await db_session.commit()
    await db_session.refresh(tutor)

    # Mock AsyncSessionLocal so handler uses our test session
    monkeypatch.setattr(bot_handlers, "AsyncSessionLocal", TestingSessionLocal)

    # Mock Telegram Update & Context
    mock_query = AsyncMock()
    mock_query.message = AsyncMock()
    mock_query.message.text = "🧑‍🏫 NEW TUTOR REGISTRATION #1\n📊 Status: ⏳ Pending"

    mock_update = MagicMock()
    mock_update.callback_query = mock_query
    mock_update.effective_user.username = "test_admin"

    mock_context = MagicMock()
    mock_context.bot = MagicMock()
    mock_context.bot.send_message = AsyncMock()

    await bot_handlers.handle_approve_tutor(mock_update, mock_context, f"approve_tutor:{tutor.id}")

    # Verify status in database
    await db_session.refresh(tutor)
    assert tutor.status == "verified"

    # Verify card edited in Admin Group
    assert mock_query.message.edit_text.called
    edit_args = mock_query.message.edit_text.call_args.kwargs
    assert "✅ Approved by @test_admin" in edit_args["text"]

    # Verify direct message sent to tutor
    assert mock_context.bot.send_message.called
    dm_args = mock_context.bot.send_message.call_args.kwargs
    assert dm_args["chat_id"] == 777888999
    assert "Congratulations, Tesfaye Abera" in dm_args["text"]


@pytest.mark.asyncio
async def test_reject_tutor_callback_updates_db(db_session: AsyncSession, monkeypatch):
    """Verifies that rejecting a tutor updates status to 'rejected'."""
    tutor = Tutor(
        telegram_user_id=111222333,
        full_name="Bizuayehu Worku",
        gender="Male",
        phone_number="+251911000000",
        university="AAU",
        department="History",
        education_year="2nd Year",
        subjects_qualified=["History"],
        grades_qualified=["Primary 5-8"],
        years_of_experience=0.5,
        expected_fee_etb=200.0,
        base_subcity="Lideta",
        coverage_areas=["Lideta"],
        availability_schedule="Weekends",
        status="pending"
    )
    db_session.add(tutor)
    await db_session.commit()
    await db_session.refresh(tutor)

    monkeypatch.setattr(bot_handlers, "AsyncSessionLocal", TestingSessionLocal)

    mock_query = AsyncMock()
    mock_query.message = AsyncMock()
    mock_query.message.text = "🧑‍🏫 NEW TUTOR REGISTRATION #2\n📊 Status: ⏳ Pending"

    mock_update = MagicMock()
    mock_update.callback_query = mock_query
    mock_update.effective_user.username = "lead_admin"

    mock_context = MagicMock()
    mock_context.bot = MagicMock()
    mock_context.bot.send_message = AsyncMock()

    await bot_handlers.handle_reject_tutor(mock_update, mock_context, f"reject_tutor:{tutor.id}")

    await db_session.refresh(tutor)
    assert tutor.status == "rejected"
    assert "❌ Rejected by @lead_admin" in mock_query.message.edit_text.call_args.kwargs["text"]


@pytest.mark.asyncio
async def test_close_parent_callback_updates_db(db_session: AsyncSession, monkeypatch):
    """Verifies that closing a parent request updates status to 'closed'."""
    parent = ParentRequest(
        parent_name="Solomon Desta",
        phone_number="+251911445566",
        student_level="Primary 1-4",
        subjects=["English"],
        preferred_gender="Female",
        preferred_experience="Senior Teacher",
        location_subcity="Gullele",
        schedule_days=["Mon", "Wed"],
        time_slot="3:00 PM - 4:30 PM",
        session_duration="1.5 hrs",
        budget_etb=3000.0,
        status="pending"
    )
    db_session.add(parent)
    await db_session.commit()
    await db_session.refresh(parent)

    monkeypatch.setattr(bot_handlers, "AsyncSessionLocal", TestingSessionLocal)

    mock_query = AsyncMock()
    mock_query.message = AsyncMock()
    mock_query.message.text = f"📋 NEW PARENT TUTORING REQUEST #{parent.id}\n📊 Status: ⏳ Pending"

    mock_update = MagicMock()
    mock_update.callback_query = mock_query
    mock_update.effective_user.username = "support_admin"

    mock_context = MagicMock()

    await bot_handlers.handle_close_parent(mock_update, mock_context, f"close_parent:{parent.id}")

    await db_session.refresh(parent)
    assert parent.status == "closed"
    assert "❌ Closed by @support_admin" in mock_query.message.edit_text.call_args.kwargs["text"]


@pytest.mark.asyncio
async def test_assign_match_callback_updates_db_and_alerts_tutor(db_session: AsyncSession, monkeypatch):
    """Verifies that assigning a tutor updates parent status to 'matched' and sends job alert DM."""
    parent = ParentRequest(
        parent_name="Rahel Tadesse",
        phone_number="+251922330011",
        student_level="Prep 11-12",
        subjects=["Biology"],
        preferred_gender="Female",
        preferred_experience="Fresh Graduate",
        location_subcity="Kolfe",
        location_landmark="Near Total",
        schedule_days=["Tue", "Thu"],
        time_slot="5:00 PM - 7:00 PM",
        session_duration="2 hrs",
        budget_etb=4200.0,
        status="pending"
    )
    tutor = Tutor(
        telegram_user_id=888999000,
        full_name="Selamawit Tefera",
        gender="Female",
        phone_number="+251911887766",
        university="AAU",
        department="Biology",
        education_year="Graduate",
        subjects_qualified=["Biology"],
        grades_qualified=["Prep 11-12"],
        years_of_experience=3.0,
        expected_fee_etb=400.0,
        base_subcity="Kolfe",
        coverage_areas=["Kolfe"],
        availability_schedule="Flexible",
        status="verified"
    )
    db_session.add_all([parent, tutor])
    await db_session.commit()
    await db_session.refresh(parent)
    await db_session.refresh(tutor)

    monkeypatch.setattr(bot_handlers, "AsyncSessionLocal", TestingSessionLocal)

    mock_query = AsyncMock()
    mock_query.message = AsyncMock()
    mock_query.message.reply_text = AsyncMock()
    mock_query.message.edit_reply_markup = AsyncMock()

    mock_update = MagicMock()
    mock_update.callback_query = mock_query
    mock_update.effective_user.username = "coordinator"

    mock_context = MagicMock()
    mock_context.bot = MagicMock()
    mock_context.bot.send_message = AsyncMock()

    await bot_handlers.handle_assign_match(mock_update, mock_context, f"assign_match:{parent.id}:{tutor.id}")

    await db_session.refresh(parent)
    assert parent.status == "matched"

    assert dm_args["chat_id"] == 888999000
    assert "New Tutoring Opportunity Assigned" in dm_args["text"]
    assert "Rahel Tadesse" in dm_args["text"]
    assert "Kolfe" in dm_args["text"]


@pytest.mark.asyncio
async def test_match_and_assign_preserves_topic_thread_id(db_session: AsyncSession, monkeypatch):
    """Verifies that matching engine output and assign confirmations preserve the message_thread_id."""
    parent = ParentRequest(
        parent_name="Topic Parent",
        phone_number="+251911444555",
        student_level="High School 9-10",
        subjects=["Maths"],
        preferred_gender="No preference",
        preferred_experience="Senior Teacher",
        location_subcity="Bole",
        schedule_days=["Mon"],
        time_slot="3:00 PM",
        session_duration="1 hr",
        budget_etb=3000.0,
        status="pending"
    )
    tutor = Tutor(
        full_name="Topic Match Tutor",
        gender="Male",
        phone_number="+251922334411",
        university="AAU",
        department="Mathematics",
        education_year="Graduate",
        subjects_qualified=["Maths"],
        grades_qualified=["High School 9-10"],
        years_of_experience=4.0,
        expected_fee_etb=400.0,
        base_subcity="Bole",
        coverage_areas=["Bole"],
        availability_schedule="Daily",
        status="verified"
    )
    db_session.add_all([parent, tutor])
    await db_session.commit()
    await db_session.refresh(parent)
    await db_session.refresh(tutor)

    monkeypatch.setattr(bot_handlers, "AsyncSessionLocal", TestingSessionLocal)

    # 1. Test handle_match_parent preserves message_thread_id
    mock_query = AsyncMock()
    mock_message = AsyncMock()
    mock_message.message_id = 5555
    mock_message.message_thread_id = 99999  # Topic ID in Supergroup
    mock_query.message = mock_message

    mock_update = MagicMock()
    mock_update.callback_query = mock_query
    mock_context = MagicMock()

    await bot_handlers.handle_match_parent(mock_update, mock_context, f"match_parent:{parent.id}")

    assert mock_message.reply_text.called
    match_reply_kwargs = mock_message.reply_text.call_args.kwargs
    assert match_reply_kwargs.get("message_thread_id") == 99999
    assert match_reply_kwargs.get("reply_to_message_id") == 5555

    # 2. Test handle_assign_match preserves message_thread_id
    mock_message.reply_text.reset_mock()
    await bot_handlers.handle_assign_match(mock_update, mock_context, f"assign_match:{parent.id}:{tutor.id}")

    assert mock_message.reply_text.called
    assign_reply_kwargs = mock_message.reply_text.call_args.kwargs
    assert assign_reply_kwargs.get("message_thread_id") == 99999
    assert assign_reply_kwargs.get("reply_to_message_id") == 5555

