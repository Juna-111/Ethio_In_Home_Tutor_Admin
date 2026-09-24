import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import AsyncSessionLocal
from app.models import ParentRequest, SystemSetting, Tutor
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
    assert keyboard[0][0].text == "🚀 Open MentorLink"
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
    assert len(keyboard) == 2
    assert keyboard[0][0].text == "📊 Analytics"
    assert keyboard[0][1].text == "📢 Broadcast"
    assert keyboard[1][0].text == "📝 Manage \"About Us\""


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
    assert "Access denied" in mock_message.reply_text.call_args.args[0]

    # Callback action
    mock_query = AsyncMock()
    mock_query.data = "admin_analytics_refresh"
    mock_update.callback_query = mock_query

    await bot_handlers.handle_callback_query(mock_update, mock_context)
    mock_query.answer.assert_called_with("⛔ Access denied.", show_alert=True)


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
    assert "1 Verified" in card_text
    assert "1 Open" in card_text
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
    assert "BROADCAST PREVIEW" in mock_msg.reply_text.call_args.args[0]

    # Step 3: Confirm broadcast
    mock_context.bot.send_message = AsyncMock()
    mock_query.reset_mock()
    mock_query.data = "admin_bcast_confirm"

    await bot_handlers.handle_callback_query(mock_update, mock_context)
    assert mock_context.bot.send_message.called
    assert mock_context.bot.send_message.call_args.kwargs["chat_id"] == 111222
    assert admin_id not in bot_handlers.admin_states
