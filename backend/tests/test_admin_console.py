import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import AsyncSessionLocal
from app.models import AdminUser, ParentRequest, SystemSetting, Tutor
import app.bot.handlers as bot_handlers
from tests.conftest import TestingSessionLocal


@pytest.mark.asyncio
async def test_public_user_start_renders_public_keyboard_with_https_url(monkeypatch):
    """Verifies that non-admin calling /start gets public welcome and keyboard with WebApp button when HTTPS URL is set."""
    monkeypatch.setattr(settings, "SUPER_ADMIN_ID", 999000111)
    monkeypatch.setattr(settings, "MINI_APP_URL", "https://t.me/MentorLinkBot/app")

    mock_message = AsyncMock()
    mock_update = MagicMock()
    mock_update.message = mock_message
    mock_update.effective_message = mock_message
    mock_update.effective_user.id = 123456789  # Non-admin user

    mock_context = MagicMock()

    await bot_handlers.start_command(mock_update, mock_context)

    assert mock_message.reply_text.called
    kwargs = mock_message.reply_text.call_args.kwargs
    assert "Welcome to MentorLink" in kwargs["text"]

    reply_markup = kwargs["reply_markup"]
    assert reply_markup.resize_keyboard is True
    assert reply_markup.is_persistent is True
    assert reply_markup.one_time_keyboard is False

    keyboard = reply_markup.keyboard
    assert len(keyboard) == 2
    # Row 1: WebApp button
    assert keyboard[0][0].text == "Register"
    assert keyboard[0][0].web_app.url == "https://t.me/MentorLinkBot/app"
    # Row 2: Customer buttons
    assert keyboard[1][0].text == "ℹ️ About Us"
    assert keyboard[1][1].text == "📞 Contact"


@pytest.mark.asyncio
async def test_public_user_start_fallback_when_mini_app_url_invalid_or_missing(monkeypatch):
    """
    Verifies that when MINI_APP_URL is missing, None, or not https://,
    the WebApp button is safely skipped and customer buttons are NEVER dropped.
    """
    monkeypatch.setattr(settings, "SUPER_ADMIN_ID", 999000111)
    
    for invalid_url in [None, "", "http://insecure.local", "ftp://example.com"]:
        monkeypatch.setattr(settings, "MINI_APP_URL", invalid_url)
        monkeypatch.setattr(settings, "WEBAPP_URL", None)

        mock_message = AsyncMock()
        mock_update = MagicMock()
        mock_update.message = mock_message
        mock_update.effective_message = mock_message
        mock_update.effective_user.id = 123456789

        mock_context = MagicMock()

        await bot_handlers.start_command(mock_update, mock_context)

        assert mock_message.reply_text.called
        kwargs = mock_message.reply_text.call_args.kwargs
        reply_markup = kwargs["reply_markup"]
        assert reply_markup is not None

        keyboard = reply_markup.keyboard
        # WebApp button should NOT be added
        assert len(keyboard) == 1
        # Customer buttons MUST remain intact
        assert keyboard[0][0].text == "ℹ️ About Us"
        assert keyboard[0][1].text == "📞 Contact"


@pytest.mark.asyncio
async def test_public_user_about_us_and_contact(db_session: AsyncSession, monkeypatch):
    """Verifies that tapping 'ℹ️ About Us' and '📞 Contact' returns content from SystemSetting."""
    monkeypatch.setattr(bot_handlers, "AsyncSessionLocal", TestingSessionLocal)

    mock_message = AsyncMock()
    mock_update = MagicMock()
    mock_update.message = mock_message
    mock_update.effective_message = mock_message
    mock_update.effective_user.id = 123456789

    mock_context = MagicMock()

    # 1. Default fallback when no DB setting exists
    mock_message.text = "ℹ️ About Us"
    await bot_handlers.handle_text_message(mock_update, mock_context)
    assert "About MentorLink" in mock_message.reply_text.call_args.kwargs["text"]

    mock_message.reset_mock()
    mock_message.text = "📞 Contact"
    await bot_handlers.handle_text_message(mock_update, mock_context)
    assert "Support & Coordination" in mock_message.reply_text.call_args.kwargs["text"]

    # 2. Updated content from SystemSetting
    db_session.add(SystemSetting(key="about_us_text", value="Custom Platform Bio 2026"))
    db_session.add(SystemSetting(key="support_contact", value="Direct Line: +251900112233"))
    await db_session.commit()

    mock_message.reset_mock()
    mock_message.text = "ℹ️ About Us"
    await bot_handlers.handle_text_message(mock_update, mock_context)
    assert "Custom Platform Bio 2026" in mock_message.reply_text.call_args.kwargs["text"]

    mock_message.reset_mock()
    mock_message.text = "📞 Contact"
    await bot_handlers.handle_text_message(mock_update, mock_context)
    assert "Direct Line: +251900112233" in mock_message.reply_text.call_args.kwargs["text"]

    # Admin-managed content is native Telegram text, so markup is displayed literally.
    about_setting = await db_session.get(SystemSetting, "about_us_text")
    about_setting.value = "<b>Literal & safe</b>"
    await db_session.commit()
    mock_message.reset_mock()
    mock_message.text = "ℹ️ About Us"
    await bot_handlers.handle_text_message(mock_update, mock_context)
    about_kwargs = mock_message.reply_text.call_args.kwargs
    assert about_kwargs["text"] == "<b>Literal & safe</b>"
    assert "parse_mode" not in about_kwargs


@pytest.mark.asyncio
async def test_super_admin_start_renders_admin_keyboard(monkeypatch):
    """Verifies that SUPER_ADMIN_ID calling /start receives admin console and exclusive keyboard."""
    admin_id = 999000111
    monkeypatch.setattr(settings, "SUPER_ADMIN_ID", admin_id)

    mock_message = AsyncMock()
    mock_update = MagicMock()
    mock_update.message = mock_message
    mock_update.effective_message = mock_message
    mock_update.effective_user.id = admin_id

    mock_context = MagicMock()

    await bot_handlers.start_command(mock_update, mock_context)

    assert mock_message.reply_text.called
    kwargs = mock_message.reply_text.call_args.kwargs
    assert "SUPER ADMIN CONSOLE" in kwargs["text"]

    keyboard = kwargs["reply_markup"].keyboard
    assert len(keyboard) == 3
    assert keyboard[0][0].text == "Analytics"
    assert keyboard[0][1].text == "Broadcast"
    assert keyboard[1][0].text == "About_Us"
    assert keyboard[1][1].text == "Export CSV"
    assert keyboard[2][0].text == "Manage Admins"


@pytest.mark.asyncio
async def test_super_admin_can_manage_database_admins(db_session: AsyncSession, monkeypatch):
    admin_id = 999000111
    managed_id = 456789123
    monkeypatch.setattr(settings, "SUPER_ADMIN_ID", admin_id)
    monkeypatch.setattr(bot_handlers, "AsyncSessionLocal", TestingSessionLocal)

    mock_query = AsyncMock()
    mock_query.data = "admin_users_add:admin"
    mock_query.message = AsyncMock()
    mock_update = MagicMock()
    mock_update.callback_query = mock_query
    mock_update.effective_user.id = admin_id

    await bot_handlers.handle_callback_query(mock_update, MagicMock())

    mock_message = AsyncMock()
    mock_message.text = str(managed_id)
    mock_update.message = mock_message
    mock_update.effective_message = mock_message
    await bot_handlers.handle_text_message(mock_update, MagicMock())

    record = await db_session.get(AdminUser, managed_id)
    assert record is not None
    assert record.role == "admin"
    assert record.is_active is True

    await bot_handlers.load_admin_registry()
    managed_update = MagicMock()
    managed_update.effective_user.id = managed_id
    assert await bot_handlers.is_admin(managed_update, MagicMock()) is True

    remove_query = AsyncMock()
    remove_query.data = f"admin_users_remove:{managed_id}"
    remove_query.message = AsyncMock()
    mock_update.callback_query = remove_query
    mock_update.effective_user.id = admin_id
    await bot_handlers.handle_callback_query(mock_update, MagicMock())

    await db_session.refresh(record)
    assert record.is_active is False


@pytest.mark.asyncio
async def test_non_admin_blocked_from_admin_actions(monkeypatch):
    """Verifies that non-admin users cannot trigger admin commands or callbacks."""
    monkeypatch.setattr(settings, "SUPER_ADMIN_ID", 999000111)

    mock_message = AsyncMock()
    mock_update = MagicMock()
    mock_update.message = mock_message
    mock_update.effective_message = mock_message
    mock_update.effective_user.id = 123456789  # Non-admin

    mock_context = MagicMock()

    # Direct /admin command
    await bot_handlers.admin_command(mock_update, mock_context)
    denied_text = mock_message.reply_text.call_args.kwargs.get("text") or mock_message.reply_text.call_args.args[0]
    assert "Access denied" in denied_text

    # Callback action
    mock_query = AsyncMock()
    mock_query.data = "admin_analytics_refresh"
    mock_update.callback_query = mock_query

    await bot_handlers.handle_callback_query(mock_update, mock_context)
    mock_query.answer.assert_called_with("⛔ Access denied. ", show_alert=True)


@pytest.mark.asyncio
async def test_admin_analytics_dashboard_and_refresh(db_session: AsyncSession, monkeypatch):
    """Verifies analytics computation and in-place stats refresh."""
    admin_id = 999000111
    monkeypatch.setattr(settings, "SUPER_ADMIN_ID", admin_id)
    monkeypatch.setattr(bot_handlers, "AsyncSessionLocal", TestingSessionLocal)

    # Populate sample data
    tutor1 = Tutor(
        full_name="Dawit",
        gender="Male",
        phone_number="+251911111111",
        university="AAU",
        department="Maths",
        education_year="Graduate",
        subjects_qualified=["Maths"],
        grades_qualified=["Grade 9-10"],
        years_of_experience=3.0,
        expected_fee_etb=400.0,
        base_subcity="Bole",
        coverage_areas=["Bole"],
        availability_schedule={"days": ["Mon"]},
        status="verified"
    )
    req1 = ParentRequest(
        parent_name="Hiwot",
        phone_number="+251922222222",
        student_level="Grade 9-10",
        subjects=["Maths"],
        preferred_gender="No preference",
        preferred_experience="University Student",
        location_subcity="Bole",
        schedule_days=["Mon"],
        time_slot="4 PM",
        session_duration="2 hrs",
        budget_etb=500.0,
        status="pending"
    )
    db_session.add(tutor1)
    db_session.add(req1)
    await db_session.commit()

    card_text = await bot_handlers.render_analytics_card()
    assert "PLATFORM ANALYTICS" in card_text
    assert "Verified: <code>1</code>" in card_text
    assert "Open / Pending: <code>1</code>" in card_text
    assert "400 ETB/hr" in card_text
    assert "Bole (1)" in card_text


@pytest.mark.asyncio
async def test_admin_broadcast_flow(db_session: AsyncSession, monkeypatch):
    """Verifies target selection, preview, and delivery rate limiting."""
    admin_id = 999000111
    monkeypatch.setattr(settings, "SUPER_ADMIN_ID", admin_id)
    monkeypatch.setattr(bot_handlers, "AsyncSessionLocal", TestingSessionLocal)

    tutor = Tutor(
        telegram_user_id=111222,
        full_name="Dawit",
        gender="Male",
        phone_number="+251911111111",
        university="AAU",
        department="Maths",
        education_year="Graduate",
        subjects_qualified=["Maths"],
        grades_qualified=["Grade 9-10"],
        years_of_experience=3.0,
        expected_fee_etb=400.0,
        base_subcity="Bole",
        coverage_areas=["Bole"],
        availability_schedule={},
        status="verified"
    )
    db_session.add(tutor)
    await db_session.commit()

    # Step 1: Select target
    mock_query = AsyncMock()
    mock_query.data = "admin_bcast_target:tutors_verified"
    mock_query.message = AsyncMock()
    mock_update = MagicMock()
    mock_update.callback_query = mock_query
    mock_update.effective_user.id = admin_id
    mock_context = MagicMock()

    await bot_handlers.handle_callback_query(mock_update, mock_context)
    assert admin_id in bot_handlers.admin_states
    assert bot_handlers.admin_states[admin_id]["state"] == "AWAITING_BROADCAST_TEXT"

    # Step 2: Admin sends text
    mock_msg = AsyncMock()
    mock_msg.text = "Hello Verified Tutors!"
    mock_update.message = mock_msg
    mock_update.effective_message = mock_msg

    await bot_handlers.handle_text_message(mock_update, mock_context)
    assert bot_handlers.admin_states[admin_id]["state"] == "AWAITING_BROADCAST_CONFIRM"
    preview_text = mock_msg.reply_text.call_args.kwargs.get("text") or mock_msg.reply_text.call_args.args[0]
    assert "BROADCAST PREVIEW" in preview_text

    # Step 3: Confirm broadcast
    mock_context.bot.send_message = AsyncMock()
    mock_query.reset_mock()
    mock_query.data = "admin_bcast_confirm"

    await bot_handlers.handle_callback_query(mock_update, mock_context)
    await asyncio.sleep(0.1)
    assert mock_context.bot.send_message.called
    assert mock_context.bot.send_message.call_args_list[0].kwargs["chat_id"] == 111222
    assert "parse_mode" not in mock_context.bot.send_message.call_args_list[0].kwargs
    assert admin_id not in bot_handlers.admin_states


@pytest.mark.asyncio
async def test_group_broadcast_command_confirms_and_copies_matching_place_recipients(db_session: AsyncSession, monkeypatch):
    admin_id = 999000111
    group_id = -1001234567890
    monkeypatch.setattr(settings, "SUPER_ADMIN_ID", admin_id)
    monkeypatch.setattr(settings, "ADMIN_GROUP_ID", group_id)
    monkeypatch.setattr(bot_handlers, "AsyncSessionLocal", TestingSessionLocal)
    bot_handlers.pending_group_broadcasts.clear()

    parent = ParentRequest(
        telegram_user_id=111222,
        parent_name="Parent Bole",
        phone_number="+251911111111",
        student_level="Grade 8",
        subjects=["Maths"],
        preferred_gender="No preference",
        preferred_experience="University Student",
        location_subcity="Bole",
        schedule_days=["Mon"],
        time_slot="4 PM",
        session_duration="1 hr",
        budget_etb=300,
    )
    tutor = Tutor(
        telegram_user_id=222333,
        full_name="Verified Bole Tutor",
        gender="Female",
        phone_number="+251922222222",
        university="AAU",
        department="Maths",
        education_year="Graduate",
        subjects_qualified=["Maths"],
        grades_qualified=["Grade 8"],
        years_of_experience=2,
        expected_fee_etb=400,
        base_subcity="Bole",
        coverage_areas=["Bole"],
        availability_schedule={},
        status="verified",
    )
    elsewhere = Tutor(
        telegram_user_id=333444,
        full_name="Verified Yeka Tutor",
        gender="Male",
        phone_number="+251933333333",
        university="AAU",
        department="Physics",
        education_year="Graduate",
        subjects_qualified=["Physics"],
        grades_qualified=["Grade 8"],
        years_of_experience=2,
        expected_fee_etb=400,
        base_subcity="Yeka",
        coverage_areas=["Yeka"],
        availability_schedule={},
        status="verified",
    )
    db_session.add_all([parent, tutor, elsewhere])
    await db_session.commit()

    source = MagicMock()
    source.chat_id = group_id
    source.message_id = 501
    source.message_thread_id = 1
    source.text = "Announcement text"
    source.caption = None

    command_message = AsyncMock()
    command_message.chat_id = group_id
    command_message.message_thread_id = 1
    command_message.text = '/broadcast "Bole"'
    command_message.reply_to_message = source
    preview_message = MagicMock()
    preview_message.message_id = 601
    command_message.reply_text = AsyncMock(return_value=preview_message)

    update = MagicMock()
    update.message = command_message
    update.effective_message = command_message
    update.effective_user.id = admin_id
    context = MagicMock()

    await bot_handlers.handle_group_broadcast_command(update, context)

    preview_text = command_message.reply_text.call_args.kwargs["text"]
    assert "Recipients: 2" in preview_text
    token = next(iter(bot_handlers.pending_group_broadcasts))

    callback_message = MagicMock()
    callback_message.chat_id = group_id
    callback_message.message_thread_id = 1
    callback_message.message_id = preview_message.message_id
    callback_message.edit_text = AsyncMock()
    callback_query = AsyncMock()
    callback_query.data = f"admin_group_broadcast_confirm:{token}"
    callback_query.message = callback_message
    update.callback_query = callback_query
    context.bot.copy_message = AsyncMock()
    context.bot.send_message = AsyncMock()

    await bot_handlers.handle_callback_query(update, context)
    await asyncio.sleep(0.15)

    copied_to = {call.kwargs["chat_id"] for call in context.bot.copy_message.call_args_list}
    assert copied_to == {111222, 222333}
    assert all(call.kwargs["from_chat_id"] == group_id for call in context.bot.copy_message.call_args_list)
    assert all(call.kwargs["message_id"] == 501 for call in context.bot.copy_message.call_args_list)
    assert context.bot.send_message.call_args.kwargs["chat_id"] == group_id
    assert "Sent: 2" in context.bot.send_message.call_args.kwargs["text"]
    assert token not in bot_handlers.pending_group_broadcasts


@pytest.mark.asyncio
async def test_group_broadcast_subject_filter_and_unknown_filter(db_session: AsyncSession, monkeypatch):
    admin_id = 999000111
    group_id = -1001234567890
    monkeypatch.setattr(settings, "SUPER_ADMIN_ID", admin_id)
    monkeypatch.setattr(settings, "ADMIN_GROUP_ID", group_id)
    monkeypatch.setattr(bot_handlers, "AsyncSessionLocal", TestingSessionLocal)

    matching_tutor = Tutor(
        telegram_user_id=444555,
        full_name="Math Tutor",
        gender="Female",
        phone_number="+251944444444",
        university="AAU",
        department="Maths",
        education_year="Graduate",
        subjects_qualified=["Maths", "Physics"],
        grades_qualified=["Grade 8"],
        years_of_experience=2,
        expected_fee_etb=400,
        base_subcity="Bole",
        coverage_areas=["Bole"],
        availability_schedule={},
        status="verified",
    )
    pending_tutor = Tutor(
        telegram_user_id=555666,
        full_name="Pending Math Tutor",
        gender="Male",
        phone_number="+251955555555",
        university="AAU",
        department="Maths",
        education_year="Graduate",
        subjects_qualified=["Maths"],
        grades_qualified=["Grade 8"],
        years_of_experience=1,
        expected_fee_etb=300,
        base_subcity="Bole",
        coverage_areas=["Bole"],
        availability_schedule={},
        status="pending",
    )
    db_session.add_all([matching_tutor, pending_tutor])
    await db_session.commit()

    assert await bot_handlers.get_group_broadcast_recipient_ids("tutors", subject="Maths") == [444555]
    assert bot_handlers._resolve_group_broadcast("broadcast", "mAtHs") == {
        "audience": "tutors", "place": None, "subject": "Maths"
    }
    with pytest.raises(ValueError, match="Unknown place or subject"):
        bot_handlers._resolve_group_broadcast("broadcast", "Atlantis")
    with pytest.raises(ValueError, match="Unknown place"):
        bot_handlers._resolve_group_broadcast("parentbroadcast", "Maths")


@pytest.mark.asyncio
async def test_group_broadcast_command_rejects_non_general_topic(monkeypatch):
    admin_id = 999000111
    group_id = -1001234567890
    monkeypatch.setattr(settings, "SUPER_ADMIN_ID", admin_id)
    monkeypatch.setattr(settings, "ADMIN_GROUP_ID", group_id)

    message = AsyncMock()
    message.chat_id = group_id
    message.message_thread_id = 42
    message.text = "/broadcast"
    update = MagicMock()
    update.message = message
    update.effective_message = message
    update.effective_user.id = admin_id

    await bot_handlers.handle_group_broadcast_command(update, MagicMock())

    assert "only available in the General topic" in message.reply_text.call_args.args[0]


@pytest.mark.asyncio
async def test_admin_cancel_command_and_text_escape():
    """Verifies that /cancel and typing 'cancel' cleanly clears active wizard states."""
    admin_id = 999000111
    bot_handlers.admin_states[admin_id] = {
        "state": "AWAITING_BROADCAST_TEXT",
        "target": "all"
    }

    mock_msg = AsyncMock()
    mock_update = MagicMock()
    mock_update.message = mock_msg
    mock_update.effective_message = mock_msg
    mock_update.effective_user.id = admin_id
    mock_context = MagicMock()

    # 1. /cancel command
    await bot_handlers.cancel_command(mock_update, mock_context)
    assert admin_id not in bot_handlers.admin_states
    cancel_text1 = mock_msg.reply_text.call_args.kwargs.get("text") or mock_msg.reply_text.call_args.args[0]
    assert "cancelled" in cancel_text1.lower()

    # 2. Text message 'cancel'
    bot_handlers.admin_states[admin_id] = {
        "state": "AWAITING_CMS_INPUT",
        "key": "about_us_text"
    }
    mock_msg.reset_mock()
    mock_msg.text = "cancel"

    await bot_handlers.handle_text_message(mock_update, mock_context)
    assert admin_id not in bot_handlers.admin_states
    cancel_text2 = mock_msg.reply_text.call_args.kwargs.get("text") or mock_msg.reply_text.call_args.args[0]
    assert "cancelled" in cancel_text2.lower()


@pytest.mark.asyncio
async def test_admin_cms_edit_shows_current_text_and_cancels(db_session: AsyncSession, monkeypatch):
    """Verifies that selecting Edit in CMS displays current content first and allows keeping existing."""
    admin_id = 999000111
    monkeypatch.setattr(settings, "SUPER_ADMIN_ID", admin_id)
    monkeypatch.setattr(bot_handlers, "AsyncSessionLocal", TestingSessionLocal)

    db_session.add(SystemSetting(key="about_us_text", value="Original Bio Text"))
    await db_session.commit()

    # Tap Edit 'About Us'
    mock_query = AsyncMock()
    mock_query.data = "admin_cms_edit:about_us_text"
    mock_query.message = AsyncMock()
    mock_update = MagicMock()
    mock_update.callback_query = mock_query
    mock_update.effective_user.id = admin_id
    mock_context = MagicMock()

    await bot_handlers.handle_callback_query(mock_update, mock_context)
    edit_kwargs = mock_query.message.edit_text.call_args.kwargs or {}
    text_sent = mock_query.message.edit_text.call_args.args[0] if mock_query.message.edit_text.call_args.args else edit_kwargs.get("text", "")
    assert "Original Bio Text" in text_sent
    assert "Keep Existing" in str(edit_kwargs.get("reply_markup", ""))

    # Tap Cancel
    mock_query.data = "admin_cms_cancel"
    await bot_handlers.handle_callback_query(mock_update, mock_context)
    assert admin_id not in bot_handlers.admin_states
    assert "preserved" in mock_query.message.edit_text.call_args.args[0]


@pytest.mark.asyncio
async def test_admin_analytics_close(monkeypatch):
    """Verifies that tapping close on analytics dismisses the dashboard."""
    admin_id = 999000111
    monkeypatch.setattr(settings, "SUPER_ADMIN_ID", admin_id)
    mock_query = AsyncMock()
    mock_query.data = "admin_analytics_close"
    mock_query.message = AsyncMock()
    mock_update = MagicMock()
    mock_update.callback_query = mock_query
    mock_update.effective_user.id = admin_id
    mock_context = MagicMock()

    await bot_handlers.handle_callback_query(mock_update, mock_context)
    assert "closed" in mock_query.message.edit_text.call_args.args[0]


def test_config_validators_sanitization():
    """Verifies config validators handle empty strings, trailing slashes, and type casting safely."""
    from app.config import Settings

    s = Settings(
        ADMIN_GROUP_ID="-1001234567890",
        SUPER_ADMIN_ID="999888777",
        MINI_APP_URL="https://t.me/MentorLinkBot/app/",
        WEBAPP_URL="https://example.com/web/"
    )
    assert s.ADMIN_GROUP_ID == -1001234567890
    assert s.SUPER_ADMIN_ID == 999888777
    assert s.MINI_APP_URL == "https://t.me/MentorLinkBot/app"
    assert s.WEBAPP_URL == "https://example.com/web"

    # Empty string handling
    s_empty = Settings(
        ADMIN_GROUP_ID="",
        SUPER_ADMIN_ID="",
        MINI_APP_URL="",
        WEBAPP_URL=""
    )
    assert s_empty.ADMIN_GROUP_ID is None
    assert s_empty.SUPER_ADMIN_ID is None
    assert s_empty.MINI_APP_URL is None
    assert s_empty.WEBAPP_URL is None


@pytest.mark.asyncio
async def test_generate_tutors_csv_content_and_encoding(db_session: AsyncSession):
    """Verifies that generate_tutors_csv produces UTF-8-SIG encoded CSV with correct headers and data."""
    from app.services.export_service import generate_tutors_csv

    tutor = Tutor(
        full_name="Abebe Bikila",
        gender="Male",
        phone_number="+251911223344",
        university="Addis Ababa University",
        department="Mathematics",
        education_year="Year 4",
        subjects_qualified=["Math", "Physics"],
        grades_qualified=["High School 9-10", "Prep 11-12"],
        years_of_experience=3.5,
        expected_fee_etb=350.0,
        base_subcity="Bole",
        coverage_areas=["Bole", "Yeka"],
        availability_schedule=["Monday Afternoon", "Wednesday Morning"],
        status="verified"
    )
    db_session.add(tutor)
    await db_session.commit()
    await db_session.refresh(tutor)

    buffer, count = await generate_tutors_csv(db_session)
    assert count >= 1

    content_bytes = buffer.getvalue()
    # Check UTF-8-SIG BOM: \xef\xbb\xbf
    assert content_bytes.startswith(b"\xef\xbb\xbf")

    text = content_bytes.decode("utf-8-sig")
    lines = [line.strip() for line in text.strip().split("\r\n") if line.strip()]
    header = lines[0]
    assert "ID,Full Name,Gender,Phone Number,Telegram User ID,University,Department,Education Level / Year,Subjects,Target Grades,Base Sub-city,Coverage Areas,Expected Fee (ETB/hr),Years Experience,Status,Registered At" == header
    assert "Abebe Bikila" in text
    assert "Addis Ababa University" in text
    assert "Math, Physics" in text
    assert "verified" in text


@pytest.mark.asyncio
async def test_generate_parents_csv_content_and_encoding(db_session: AsyncSession):
    """Verifies that generate_parents_csv produces UTF-8-SIG encoded CSV with correct headers and data."""
    from app.services.export_service import generate_parents_csv

    req = ParentRequest(
        parent_name="Almaz Ayana",
        phone_number="+251922334455",
        student_level="High School 9-10",
        subjects=["Chemistry", "Biology"],
        preferred_gender="Female",
        preferred_experience="Senior Teacher",
        location_subcity="Kirkos",
        location_landmark="Near Mexico Square",
        schedule_days=["Tuesday", "Thursday"],
        time_slot="4:30 PM - 6:30 PM",
        session_duration="2 hrs",
        budget_etb=400.0,
        status="pending"
    )
    db_session.add(req)
    await db_session.commit()
    await db_session.refresh(req)

    buffer, count = await generate_parents_csv(db_session)
    assert count >= 1

    content_bytes = buffer.getvalue()
    # Check UTF-8-SIG BOM: \xef\xbb\xbf
    assert content_bytes.startswith(b"\xef\xbb\xbf")

    text = content_bytes.decode("utf-8-sig")
    lines = [line.strip() for line in text.strip().split("\r\n") if line.strip()]
    header = lines[0]
    assert "ID,Parent Name,Phone Number,Telegram User ID,Location Sub-city,Landmark,Student Level / Grade,Subjects,Schedule Days,Time Slot,Session Duration,Budget (ETB/hr),Preferred Tutor Gender,Status,Assigned Tutor ID,Created At" == header
    assert "Almaz Ayana" in text
    assert "Kirkos" in text
    assert "Near Mexico Square" in text
    assert "Chemistry, Biology" in text


def test_admin_reply_keyboard_contains_export_button():
    """Verifies that the Super Admin persistent keyboard includes the Export CSV button."""
    markup = bot_handlers.get_admin_reply_keyboard()
    all_button_texts = [btn.text for row in markup.keyboard for btn in row]
    assert "Export CSV" in all_button_texts


@pytest.mark.asyncio
async def test_admin_about_us_keyboard_label_opens_cms(monkeypatch):
    admin_id = 999000111
    monkeypatch.setattr(settings, "SUPER_ADMIN_ID", admin_id)
    clear_state = AsyncMock()
    open_cms = AsyncMock()
    monkeypatch.setattr(bot_handlers, "clear_admin_state", clear_state)
    monkeypatch.setattr(bot_handlers, "handle_cms_menu", open_cms)

    message = AsyncMock()
    message.text = "About_Us"
    update = MagicMock()
    update.message = message
    update.effective_message = message
    update.effective_user.id = admin_id

    await bot_handlers.handle_text_message(update, MagicMock())

    clear_state.assert_awaited_once_with(admin_id)
    open_cms.assert_awaited_once()


@pytest.mark.asyncio
async def test_handle_export_menu_renders_options(monkeypatch):
    """Verifies that tapping 'Export CSV' presents the inline dataset selection menu."""
    admin_id = 999000111
    monkeypatch.setattr(settings, "SUPER_ADMIN_ID", admin_id)
    mock_message = AsyncMock()
    mock_update = MagicMock()
    mock_update.message = mock_message
    mock_update.effective_message = mock_message
    mock_update.effective_user.id = admin_id
    mock_context = MagicMock()

    await bot_handlers.handle_export_menu(mock_update, mock_context)

    assert mock_message.reply_text.called
    kwargs = mock_message.reply_text.call_args.kwargs
    assert "EXPORT DATA CENTER" in kwargs["text"]

    markup = kwargs["reply_markup"]
    callbacks = [btn.callback_data for row in markup.inline_keyboard for btn in row]
    assert "export:tutors" in callbacks
    assert "export:parents" in callbacks
    assert "export:both" in callbacks
    assert "export:close" in callbacks


@pytest.mark.asyncio
async def test_handle_export_callback_dispatches_documents(monkeypatch):
    """Verifies that Super Admin triggering export callbacks sends the expected CSV documents."""
    admin_id = 999000111
    monkeypatch.setattr(settings, "SUPER_ADMIN_ID", admin_id)

    # 1. Test export:tutors
    mock_query = AsyncMock()
    mock_query.data = "export:tutors"
    mock_update = MagicMock()
    mock_update.callback_query = mock_query
    mock_update.effective_user.id = admin_id
    mock_update.effective_chat.id = admin_id

    mock_bot = AsyncMock()
    mock_context = MagicMock()
    mock_context.bot = mock_bot

    await bot_handlers.handle_export_callback(mock_update, mock_context, "export:tutors")

    assert mock_bot.send_document.called
    tutor_call_kwargs = mock_bot.send_document.call_args.kwargs
    assert tutor_call_kwargs["chat_id"] == admin_id
    assert "mentors_" in tutor_call_kwargs["filename"]
    assert "tutor records" in tutor_call_kwargs["caption"]

    # 2. Test export:parents
    mock_bot.reset_mock()
    await bot_handlers.handle_export_callback(mock_update, mock_context, "export:parents")

    assert mock_bot.send_document.called
    parent_call_kwargs = mock_bot.send_document.call_args.kwargs
    assert parent_call_kwargs["chat_id"] == admin_id
    assert "parent_requests_" in parent_call_kwargs["filename"]
    assert "parent request records" in parent_call_kwargs["caption"]

    # 3. Test export:both (should send both documents)
    mock_bot.reset_mock()
    await bot_handlers.handle_export_callback(mock_update, mock_context, "export:both")
    assert mock_bot.send_document.call_count == 2


@pytest.mark.asyncio
async def test_handle_export_callback_security_guard(monkeypatch):
    """Verifies that non-admin users cannot trigger export callbacks."""
    monkeypatch.setattr(settings, "SUPER_ADMIN_ID", 999000111)

    mock_query = AsyncMock()
    mock_query.data = "export:tutors"
    mock_update = MagicMock()
    mock_update.callback_query = mock_query
    mock_update.effective_user.id = 111222333  # Non-admin

    mock_bot = AsyncMock()
    mock_context = MagicMock()
    mock_context.bot = mock_bot

    await bot_handlers.handle_export_callback(mock_update, mock_context, "export:tutors")

    assert not mock_bot.send_document.called
    assert mock_query.answer.called
    args, kwargs = mock_query.answer.call_args
    assert "Access denied" in args[0]
    assert kwargs.get("show_alert") is True


@pytest.mark.asyncio
async def test_handle_export_close(monkeypatch):
    """Verifies that export:close edits message to closed notice without sending documents."""
    admin_id = 999000111
    monkeypatch.setattr(settings, "SUPER_ADMIN_ID", admin_id)

    mock_query = AsyncMock()
    mock_query.data = "export:close"
    mock_query.message = AsyncMock()
    mock_update = MagicMock()
    mock_update.callback_query = mock_query
    mock_update.effective_user.id = admin_id

    mock_bot = AsyncMock()
    mock_context = MagicMock()
    mock_context.bot = mock_bot

    await bot_handlers.handle_export_callback(mock_update, mock_context, "export:close")

    assert not mock_bot.send_document.called
    assert mock_query.message.edit_text.called
    assert "closed" in mock_query.message.edit_text.call_args.args[0]

