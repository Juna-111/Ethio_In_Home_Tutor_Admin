from unittest.mock import AsyncMock, MagicMock
import pytest
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Assignment, MatchInvite, ParentRequest, Tutor
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
    await db_session.execute(delete(Tutor))
    await db_session.execute(delete(ParentRequest))
    await db_session.commit()

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
    await db_session.execute(delete(Tutor))
    await db_session.execute(delete(ParentRequest))
    await db_session.commit()

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
async def test_approve_tutor_callback_graceful_stub(db_session: AsyncSession, monkeypatch):
    """Phase 3: approving via chat button shows a 'use the app' message without changing tutor status."""
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

    monkeypatch.setattr(bot_handlers, "AsyncSessionLocal", TestingSessionLocal)

    mock_query = AsyncMock()
    mock_update = MagicMock()
    mock_update.callback_query = mock_query
    mock_update.effective_user.username = "test_admin"

    mock_context = MagicMock()

    await bot_handlers.handle_approve_tutor(mock_update, mock_context, f"approve_tutor:{tutor.id}")

    # Status must remain pending — approval now requires the miniapp checklist
    await db_session.refresh(tutor)
    assert tutor.status == "pending"

    # Graceful answer shown to the admin
    mock_query.answer.assert_called_once()
    answer_text = mock_query.answer.call_args.args[0] if mock_query.answer.call_args.args else mock_query.answer.call_args.kwargs.get("text", "")
    assert "Admin App" in answer_text or "verification checklist" in answer_text


@pytest.mark.asyncio
async def test_reject_tutor_callback_graceful_stub(db_session: AsyncSession, monkeypatch):
    """Phase 3: rejecting via chat button shows a 'use the app' message without changing tutor status."""
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
    mock_update = MagicMock()
    mock_update.callback_query = mock_query
    mock_update.effective_user.username = "lead_admin"

    mock_context = MagicMock()

    await bot_handlers.handle_reject_tutor(mock_update, mock_context, f"reject_tutor:{tutor.id}")

    # Status must remain pending — rejection now requires the miniapp
    await db_session.refresh(tutor)
    assert tutor.status == "pending"

    # Graceful answer shown to the admin
    mock_query.answer.assert_called_once()
    answer_text = mock_query.answer.call_args.args[0] if mock_query.answer.call_args.args else mock_query.answer.call_args.kwargs.get("text", "")
    assert "Admin App" in answer_text or "verification checklist" in answer_text


@pytest.mark.asyncio
async def test_close_parent_callback_updates_db(db_session: AsyncSession, monkeypatch):
    """Verifies that closing a parent request updates status to 'closed' and auto-closes dedicated forum topic."""
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
        status="pending",
        telegram_topic_id=88991
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
    mock_context.bot = MagicMock()
    mock_context.bot.close_forum_topic = AsyncMock()

    await bot_handlers.handle_close_parent(mock_update, mock_context, f"close_parent:{parent.id}")

    await db_session.refresh(parent)
    assert parent.status == "closed"
    assert "Closed by @support_admin" in mock_query.message.edit_text.call_args.kwargs["text"]
    assert "<blockquote>" in mock_query.message.edit_text.call_args.kwargs["text"]

    # Verify dedicated forum topic was closed
    assert mock_context.bot.close_forum_topic.called
    assert mock_context.bot.close_forum_topic.call_args.kwargs["message_thread_id"] == 88991


@pytest.mark.asyncio
async def test_assign_match_callback_updates_db_and_alerts_tutor(db_session: AsyncSession, monkeypatch):
    """Verifies that assigning a tutor updates parent status to 'matched', closes dedicated topic, and alerts both tutor and parent."""
    parent = ParentRequest(
        telegram_user_id=777666555,
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
        status="pending",
        telegram_topic_id=88992
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
    db_session.add(MatchInvite(request_id=parent.id, tutor_id=tutor.id, status="yes"))
    await db_session.commit()

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
    mock_context.bot.close_forum_topic = AsyncMock()

    await bot_handlers.handle_assign_match(mock_update, mock_context, f"assign_match:{parent.id}:{tutor.id}")

    await db_session.refresh(parent)
    assert parent.status == "matched"

    # Verify Assignment record created
    from app.models import Assignment
    assignment_res = await db_session.execute(select(Assignment).where(Assignment.request_id == parent.id))
    assignment = assignment_res.scalar_one_or_none()
    assert assignment is not None
    assert assignment.tutor_id == tutor.id
    assert assignment.status == "active"

    # Verify dedicated topic was auto-closed
    assert mock_context.bot.close_forum_topic.called
    assert mock_context.bot.close_forum_topic.call_args.kwargs["message_thread_id"] == 88992

    # Verify 2 DMs sent: one to parent, one to tutor
    assert mock_context.bot.send_message.call_count == 2
    sent_calls = mock_context.bot.send_message.call_args_list

    # Parent DM verification
    parent_dm_call = next(c for c in sent_calls if c.kwargs["chat_id"] == 777666555)
    assert "Great news, Rahel Tadesse!" in parent_dm_call.kwargs["text"]
    assert "Selamawit Tefera" in parent_dm_call.kwargs["text"]
    assert "AAU" in parent_dm_call.kwargs["text"]
    assert "+251911887766" in parent_dm_call.kwargs["text"]
    assert "Thank you for trusting Us." in parent_dm_call.kwargs["text"]

    # Tutor DM verification
    tutor_dm_call = next(c for c in sent_calls if c.kwargs["chat_id"] == 888999000)
    assert "New Tutoring Opportunity Assigned" in tutor_dm_call.kwargs["text"]
    assert "Rahel Tadesse" in tutor_dm_call.kwargs["text"]
    assert "Kolfe" in tutor_dm_call.kwargs["text"]


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
    db_session.add(MatchInvite(request_id=parent.id, tutor_id=tutor.id, status="yes"))
    await db_session.commit()

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


@pytest.mark.asyncio
async def test_get_tiered_matches_categorization(db_session: AsyncSession):
    """
    Verifies that get_tiered_matches categorizes candidates into:
    - Tier 1: Perfect Fit (Subcity + Subject + Gender + Budget)
    - Tier 2: Commute / Proximity (Coverage area + Subject + Budget within 20%)
    - Tier 3: Flex Alternatives (Subject + Gender flex or Budget within 35%)
    And strictly excludes pending status, no subject overlap, or fee > 35%.
    """
    from app.services.matcher import get_tiered_matches

    await db_session.execute(delete(Tutor))
    await db_session.execute(delete(ParentRequest))
    await db_session.commit()

    parent = ParentRequest(
        parent_name="Radar Parent",
        phone_number="+251911777888",
        student_level="High School 9-10",
        subjects=["Maths", "Physics"],
        preferred_gender="Male",
        preferred_experience="University Student",
        location_subcity="Bole",
        schedule_days=["Mon", "Wed"],
        time_slot="4:00 PM - 6:00 PM",
        session_duration="2 hrs",
        budget_etb=400.0,
        status="pending"
    )
    db_session.add(parent)
    await db_session.commit()
    await db_session.refresh(parent)

    # Tutor 1: Verified, Male, Base Bole, Maths, 350 ETB (<= 400) -> Tier 1 (Perfect Fit)
    t1 = Tutor(
        full_name="Sara Perfect",
        gender="Male",
        phone_number="+251911111001",
        university="AAU",
        department="CS",
        education_year="4th Year",
        subjects_qualified=["Maths", "Physics"],
        grades_qualified=["High School 9-10"],
        years_of_experience=2.5,
        expected_fee_etb=350.0,
        base_subcity="Bole",
        coverage_areas=["Bole"],
        availability_schedule="Evenings",
        status="verified"
    )

    # Tutor 2: Verified, Male, Base Yeka, Coverage Bole, Maths, 450 ETB (<= 400 * 1.20 = 480) -> Tier 2 (Commute/Proximity)
    t2 = Tutor(
        full_name="Dawit Commute",
        gender="Male",
        phone_number="+251911111002",
        university="AAU",
        department="Engineering",
        education_year="Graduate",
        subjects_qualified=["Maths"],
        grades_qualified=["High School 9-10"],
        years_of_experience=3.0,
        expected_fee_etb=450.0,
        base_subcity="Yeka",
        coverage_areas=["Bole", "Yeka"],
        availability_schedule="Weekends",
        status="verified"
    )

    # Tutor 3: Verified, Female (gender flex), Base Bole, Physics, 500 ETB (<= 400 * 1.35 = 540) -> Tier 3 (Flex)
    t3 = Tutor(
        full_name="Martha Flex",
        gender="Female",
        phone_number="+251911111003",
        university="AAU",
        department="Physics",
        education_year="Graduate",
        subjects_qualified=["Physics"],
        grades_qualified=["High School 9-10"],
        years_of_experience=4.0,
        expected_fee_etb=500.0,
        base_subcity="Bole",
        coverage_areas=["Bole"],
        availability_schedule="Flexible",
        status="verified"
    )

    # Tutor 4: Pending -> Excluded from all tiers
    t4 = Tutor(
        full_name="Pending Tutor",
        gender="Male",
        phone_number="+251911111004",
        university="AAU",
        department="Maths",
        education_year="1st Year",
        subjects_qualified=["Maths"],
        grades_qualified=["High School 9-10"],
        years_of_experience=1.0,
        expected_fee_etb=300.0,
        base_subcity="Bole",
        coverage_areas=["Bole"],
        availability_schedule="Daily",
        status="pending"
    )

    # Tutor 5: No subject overlap -> Excluded from all tiers
    t5 = Tutor(
        full_name="History Tutor",
        gender="Male",
        phone_number="+251911111005",
        university="AAU",
        department="History",
        education_year="Graduate",
        subjects_qualified=["History", "Civics"],
        grades_qualified=["High School 9-10"],
        years_of_experience=5.0,
        expected_fee_etb=300.0,
        base_subcity="Bole",
        coverage_areas=["Bole"],
        availability_schedule="Daily",
        status="verified"
    )

    # Tutor 6: Exceeds 35% flex budget (Fee 600 > 540) -> Excluded from all tiers
    t6 = Tutor(
        full_name="Expensive Tutor",
        gender="Male",
        phone_number="+251911111006",
        university="AAU",
        department="Maths",
        education_year="Graduate",
        subjects_qualified=["Maths"],
        grades_qualified=["High School 9-10"],
        years_of_experience=5.0,
        expected_fee_etb=600.0,
        base_subcity="Bole",
        coverage_areas=["Bole"],
        availability_schedule="Daily",
        status="verified"
    )

    # Tutor 7: Incompatible grade stage (Primary 1-4 vs High School 9-10) -> Excluded from all tiers
    t7 = Tutor(
        full_name="Primary Only Tutor",
        gender="Male",
        phone_number="+251911111007",
        university="AAU",
        department="Maths",
        education_year="Graduate",
        subjects_qualified=["Maths"],
        grades_qualified=["Primary 1-4"],
        years_of_experience=5.0,
        expected_fee_etb=350.0,
        base_subcity="Bole",
        coverage_areas=["Bole"],
        availability_schedule="Daily",
        status="verified"
    )

    db_session.add_all([t1, t2, t3, t4, t5, t6, t7])
    await db_session.commit()

    found_parent, tiered = await get_tiered_matches(parent.id, db_session)
    assert found_parent is not None

    # Tier 1 verification
    assert len(tiered["tier1"]) == 1
    assert tiered["tier1"][0]["tutor"].full_name == "Sara Perfect"

    # Tier 2 verification
    assert len(tiered["tier2"]) == 1
    assert tiered["tier2"][0]["tutor"].full_name == "Dawit Commute"

    # Tier 3 verification
    assert len(tiered["tier3"]) == 1
    assert tiered["tier3"][0]["tutor"].full_name == "Martha Flex"
    assert "Gender flex" in tiered["tier3"][0]["flex_note"]

    # Verify t7 is not present in any tier
    all_matched_tutors = [item["tutor"].full_name for tier_list in tiered.values() for item in tier_list]
    assert "Primary Only Tutor" not in all_matched_tutors


@pytest.mark.asyncio
async def test_ping_candidates_and_availability_confirmation(db_session: AsyncSession, monkeypatch):
    """
    Verifies:
    1. handle_ping_candidates broadcasts DM to tutors with telegram_user_id and updates button in-place.
    2. handle_tutor_avail_yes edits tutor DM and posts confirmation card with assign button to Admin Group.
    3. handle_tutor_avail_no gracefully acknowledges in tutor DM.
    """
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    from app.config import settings

    monkeypatch.setattr(settings, "ADMIN_GROUP_ID", -1001234567890)

    await db_session.execute(delete(MatchInvite))
    await db_session.execute(delete(Tutor))
    await db_session.execute(delete(ParentRequest))
    await db_session.commit()

    parent = ParentRequest(
        parent_name="Ping Parent",
        phone_number="+251911333444",
        student_level="Grade 10",
        subjects=["Maths"],
        preferred_gender="No preference",
        preferred_experience="University Student",
        location_subcity="Bole",
        location_landmark="Near Edna",
        schedule_days=["Mon", "Wed"],
        time_slot="5:00 PM",
        session_duration="1.5 hrs",
        budget_etb=400.0,
        status="pending"
    )
    tutor = Tutor(
        telegram_user_id=123454321,
        full_name="Ping Tutor",
        gender="Male",
        phone_number="+251911002244",
        university="AAU",
        department="Maths",
        education_year="3rd Year",
        subjects_qualified=["Maths"],
        grades_qualified=["Grade 10"],
        years_of_experience=2.0,
        expected_fee_etb=350.0,
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

    # 1. Test ping_candidates broadcasts DM and deduplicates button in-place
    mock_query = AsyncMock()
    mock_message = AsyncMock()
    mock_message.reply_markup = InlineKeyboardMarkup([
        [InlineKeyboardButton("📡 Ping Candidates", callback_data=f"ping_candidates:{parent.id}")]
    ])
    mock_query.message = mock_message
    mock_update = MagicMock()
    mock_update.callback_query = mock_query

    mock_context = MagicMock()
    mock_context.bot = MagicMock()
    mock_context.bot.send_message = AsyncMock()

    await bot_handlers.handle_ping_candidates(mock_update, mock_context, f"ping_candidates:{parent.id}")

    # Button deduplicated
    assert mock_message.edit_reply_markup.called
    updated_markup = mock_message.edit_reply_markup.call_args.kwargs["reply_markup"]
    assert any("⏳ Ping Sent" in btn.text for row in updated_markup.inline_keyboard for btn in row)

    # DM sent to tutor with availability buttons
    assert mock_context.bot.send_message.called
    dm_call = mock_context.bot.send_message.call_args.kwargs
    assert dm_call["chat_id"] == 123454321
    assert "NEW TUTORING OPPORTUNITY" in dm_call["text"]
    dm_buttons = [btn.callback_data for row in dm_call["reply_markup"].inline_keyboard for btn in row]
    assert f"tutor_avail_yes:{parent.id}:{tutor.id}" in dm_buttons
    assert f"tutor_avail_no:{parent.id}:{tutor.id}" in dm_buttons

    # 2. Test tutor_avail_yes updates tutor DM and alerts Admin Group
    mock_context.bot.send_message.reset_mock()
    mock_tutor_msg = AsyncMock()
    mock_query.message = mock_tutor_msg
    mock_update.effective_user.id = tutor.telegram_user_id
    await bot_handlers.handle_tutor_avail_yes(mock_update, mock_context, f"tutor_avail_yes:{parent.id}:{tutor.id}")

    assert mock_tutor_msg.edit_text.called
    assert "Thank you, Ping Tutor" in mock_tutor_msg.edit_text.call_args.kwargs["text"]

    # Admin group alert sent
    assert mock_context.bot.send_message.called
    admin_alert_args = mock_context.bot.send_message.call_args.kwargs
    assert "AVAILABILITY CONFIRMED" in admin_alert_args["text"]
    assert "Ping Tutor" in admin_alert_args["text"]
    assert "Maths" in admin_alert_args["text"]
    confirm_btn = admin_alert_args["reply_markup"].inline_keyboard[0][0]
    assert confirm_btn.text == "✅ Assign"
    assert confirm_btn.callback_data == f"assign_match:{parent.id}:{tutor.id}"

    # 3. A second response on the same invite is ignored.
    mock_tutor_msg.reset_mock()
    mock_context.bot.send_message.reset_mock()
    await bot_handlers.handle_tutor_avail_no(mock_update, mock_context, f"tutor_avail_no:{parent.id}:{tutor.id}")
    assert not mock_tutor_msg.edit_text.called
    assert not mock_context.bot.send_message.called
    assert mock_query.answer.call_args.kwargs.get("show_alert") is True


@pytest.mark.asyncio
async def test_match_parent_zero_matches_shows_alert(db_session: AsyncSession, monkeypatch):
    """
    Verifies that when zero matches exist across all tiers, handle_match_parent
    triggers a non-disruptive Telegram popup alert (show_alert=True) with zero chat spam.
    """
    await db_session.execute(delete(Tutor))
    await db_session.execute(delete(ParentRequest))
    await db_session.commit()

    parent = ParentRequest(
        parent_name="Lonely Parent",
        phone_number="+251911999888",
        student_level="Grade 1",
        subjects=["Astrophysics"],
        preferred_gender="No preference",
        preferred_experience="Senior Teacher",
        location_subcity="Bole",
        schedule_days=["Mon"],
        time_slot="1:00 PM",
        session_duration="1 hr",
        budget_etb=100.0,
        status="pending"
    )
    db_session.add(parent)
    await db_session.commit()
    await db_session.refresh(parent)

    monkeypatch.setattr(bot_handlers, "AsyncSessionLocal", TestingSessionLocal)

    mock_query = AsyncMock()
    mock_message = AsyncMock()
    mock_query.message = mock_message
    mock_update = MagicMock()
    mock_update.callback_query = mock_query
    mock_context = MagicMock()

    await bot_handlers.handle_match_parent(mock_update, mock_context, f"match_parent:{parent.id}")

    assert mock_query.answer.called
    assert mock_query.answer.call_args.kwargs.get("show_alert") is True
    assert not mock_message.reply_text.called


@pytest.mark.asyncio
async def test_admin_callback_from_unauthorized_chat_rejected(monkeypatch):
    """Verifies that an admin action originating from outside ADMIN_GROUP_ID is blocked (FIX 5)."""
    from app.config import settings
    monkeypatch.setattr(settings, "ADMIN_GROUP_ID", -1001234567890)
    monkeypatch.setattr(settings, "SUPER_ADMIN_ID", 999000111)

    mock_query = AsyncMock()
    mock_query.data = "approve_tutor:42"
    mock_message = AsyncMock()
    mock_message.chat_id = -1009999999999  # Spoofed / wrong chat ID
    mock_query.message = mock_message

    mock_update = MagicMock()
    mock_update.callback_query = mock_query
    mock_update.effective_user.id = 999000111  # Is admin

    mock_context = MagicMock()

    await bot_handlers.handle_callback_query(mock_update, mock_context)
    mock_query.answer.assert_called_with("⛔ This action can only be performed in the Admin Group.", show_alert=True)


@pytest.mark.asyncio
async def test_view_document_callback_dispatches_document_to_admin_dm(db_session: AsyncSession, monkeypatch, tmp_path):
    """Verifies that view_doc:<tutor_id> sends the uploaded document to the admin's DM (FIX 2)."""
    from app.config import settings
    import app.bot.handlers as bh
    admin_id = 999000111
    monkeypatch.setattr(settings, "SUPER_ADMIN_ID", admin_id)
    monkeypatch.setattr(settings, "ADMIN_GROUP_ID", -1001234567890)

    # Create a mock file in UPLOAD_DIR
    fake_upload_dir = tmp_path / "uploads"
    fake_upload_dir.mkdir()
    doc_file = fake_upload_dir / "tutor_cert.pdf"
    doc_file.write_bytes(b"%PDF-1.4 test certificate")
    monkeypatch.setattr(bh, "UPLOAD_DIR", str(fake_upload_dir))

    tutor = Tutor(
        full_name="Certified Tutor",
        gender="Male",
        phone_number="+251911998877",
        university="AAU",
        department="Maths",
        education_year="Graduate",
        subjects_qualified=["Maths"],
        grades_qualified=["High School 9-10"],
        years_of_experience=3.0,
        expected_fee_etb=350.0,
        base_subcity="Bole",
        coverage_areas=["Bole"],
        availability_schedule="Daily",
        id_document_url="/uploads/tutor_cert.pdf",
        status="pending"
    )
    db_session.add(tutor)
    await db_session.commit()
    await db_session.refresh(tutor)

    mock_query = AsyncMock()
    mock_query.data = f"view_doc:{tutor.id}"
    mock_message = AsyncMock()
    mock_message.chat_id = -1001234567890
    mock_query.message = mock_message

    mock_update = MagicMock()
    mock_update.callback_query = mock_query
    mock_update.effective_user.id = admin_id

    mock_context = MagicMock()
    mock_context.bot = MagicMock()
    mock_context.bot.send_document = AsyncMock()

    await bh.handle_callback_query(mock_update, mock_context)
    assert mock_context.bot.send_document.called
    send_kwargs = mock_context.bot.send_document.call_args.kwargs
    assert send_kwargs["chat_id"] == admin_id
    assert send_kwargs["filename"] == "tutor_cert.pdf"
    assert "Certified Tutor" in send_kwargs["caption"]
    assert "Sent to your DMs" in mock_query.answer.call_args.args[0]

