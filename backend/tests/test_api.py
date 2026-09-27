import re
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ParentRequest, Tutor


@pytest.mark.asyncio
async def test_healthcheck(async_client: AsyncClient):
    """Verifies the health check endpoint returns 200 and healthy database status."""
    response = await async_client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["database"] == "connected"


@pytest.mark.asyncio
async def test_create_parent_request_success(async_client: AsyncClient, db_session: AsyncSession):
    """Verifies that a valid parent intake payload is saved with status 'pending'."""
    payload = {
        "telegram_user_id": 123456789,
        "parent_name": "Abebe Kebede",
        "phone_number": "+251911223344",
        "student_level": "High School 9-10",
        "subjects": ["Maths", "Physics"],
        "preferred_gender": "Male",
        "preferred_experience": "University Student",
        "location_subcity": "Bole",
        "location_landmark": "Around Edna Mall",
        "schedule_days": ["Mon", "Wed", "Fri"],
        "time_slot": "4:30 PM - 6:30 PM",
        "session_duration": "2 hrs",
        "budget_etb": 4500.0
    }

    response = await async_client.post("/api/v1/parents/request", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["id"] is not None
    assert data["status"] == "pending"
    assert data["parent_name"] == "Abebe Kebede"
    assert data["location_subcity"] == "Bole"
    assert data["subjects"] == ["Maths", "Physics"]

    # Verify directly against database
    query = select(ParentRequest).where(ParentRequest.id == data["id"])
    result = await db_session.execute(query)
    record = result.scalar_one_or_none()
    assert record is not None
    assert record.parent_name == "Abebe Kebede"
    assert record.status == "pending"
    assert record.budget_etb == 4500.0


@pytest.mark.asyncio
async def test_create_parent_request_validation_failure(async_client: AsyncClient):
    """Verifies that invalid payloads (e.g. non-positive budget, missing fields) return 422."""
    invalid_payload = {
        "parent_name": "Abebe",
        "phone_number": "+251911223344",
        "student_level": "Primary 1-4",
        "subjects": [],  # Empty subjects list should fail validation
        "preferred_experience": "University Student",
        "location_subcity": "Bole",
        "schedule_days": "Mon/Wed",
        "time_slot": "5:00 PM",
        "session_duration": "1 hr",
        "budget_etb": -100.0  # Invalid negative budget
    }

    response = await async_client.post("/api/v1/parents/request", json=invalid_payload)
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_register_tutor_success(async_client: AsyncClient, db_session: AsyncSession):
    """Verifies that a valid tutor profile is registered with status 'pending'."""
    payload = {
        "telegram_user_id": 987654321,
        "full_name": "Sara Tadesse",
        "gender": "Female",
        "phone_number": "+251922334455",
        "university": "Addis Ababa University (AAiT)",
        "department": "Electrical & Computer Engineering",
        "education_year": "4th Year",
        "subjects_qualified": ["Maths", "Physics", "Chemistry"],
        "grades_qualified": ["Primary 5-8", "High School 9-10"],
        "years_of_experience": 2.5,
        "expected_fee_etb": 350.0,
        "base_subcity": "Yeka",
        "coverage_areas": ["Yeka", "Bole", "Arada"],
        "availability_schedule": {
            "weekdays": "after 5 PM",
            "weekends": "all day"
        },
        "id_document_url": "https://example.com/uploads/sara_id.jpg",
        "entrance_result": 92.5
    }

    response = await async_client.post("/api/v1/tutors/register", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["id"] is not None
    assert data["status"] == "pending"
    assert data["full_name"] == "Sara Tadesse"
    assert data["gender"] == "Female"
    assert data["base_subcity"] == "Yeka"
    assert data["subjects_qualified"] == ["Maths", "Physics", "Chemistry"]
    assert data["entrance_result"] == payload["entrance_result"]

    # Verify directly against database
    query = select(Tutor).where(Tutor.id == data["id"])
    result = await db_session.execute(query)
    record = result.scalar_one_or_none()
    assert record is not None
    assert record.full_name == "Sara Tadesse"
    assert record.status == "pending"
    assert record.expected_fee_etb == 350.0
    assert record.entrance_result == payload["entrance_result"]


@pytest.mark.asyncio
async def test_register_tutor_ignores_client_telegram_id(async_client: AsyncClient):
    """Unauthenticated preview submissions cannot assign themselves a Telegram identity."""
    payload = {
        "telegram_user_id": 987654321,
        "full_name": "Sara Duplicate",
        "gender": "Female",
        "phone_number": "+251922334499",
        "university": "AAU",
        "department": "Computer Science",
        "education_year": "Graduate",
        "subjects_qualified": ["Maths"],
        "grades_qualified": ["High School 9-10"],
        "years_of_experience": 1.0,
        "expected_fee_etb": 400.0,
        "base_subcity": "Bole",
        "coverage_areas": ["Bole"],
        "availability_schedule": "Weekends"
    }

    response = await async_client.post("/api/v1/tutors/register", json=payload)
    assert response.status_code == 201
    assert response.json()["telegram_user_id"] is None


@pytest.mark.asyncio
async def test_unauthenticated_tutor_registration_allowed_in_production(async_client: AsyncClient, monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")
    monkeypatch.setattr(settings, "ALLOW_UNVERIFIED_WEB_PREVIEW", False)

    payload = {
        "telegram_user_id": 987654321,
        "full_name": "Browser Tutor",
        "gender": "Female",
        "phone_number": "0911223344",
        "university": "AAU",
        "department": "Mathematics",
        "education_year": "3rd Year",
        "subjects_qualified": ["Maths"],
        "grades_qualified": ["Grade 8"],
        "years_of_experience": 2,
        "expected_fee_etb": 300,
        "base_subcity": "Bole",
        "coverage_areas": ["Bole"],
        "availability_schedule": "Weekends",
    }

    response = await async_client.post("/api/v1/tutors/register", json=payload)

    assert response.status_code == 201
    assert response.json()["telegram_user_id"] is None


@pytest.mark.asyncio
async def test_register_tutor_validation_failure(async_client: AsyncClient):
    """Verifies validation failure on invalid tutor data (e.g. empty coverage areas, negative fee)."""
    invalid_payload = {
        "full_name": "T",  # Too short
        "gender": "Male",
        "phone_number": "123",
        "university": "AAU",
        "department": "Physics",
        "education_year": "3rd Year",
        "subjects_qualified": [],  # Empty
        "grades_qualified": ["High School 9-10"],
        "expected_fee_etb": 0.0,  # Must be > 0
        "base_subcity": "Arada",
        "coverage_areas": [],  # Empty
        "availability_schedule": "Flexible"
    }

    response = await async_client.post("/api/v1/tutors/register", json=invalid_payload)
    assert response.status_code == 422


def test_normalize_database_url_neon():
    """Verifies that channel_binding and sslmode are stripped, scheme is postgresql+asyncpg, and ssl='require' is set."""
    from app.database import normalize_database_url

    raw_neon_url = "postgresql://user:secret@ep-cool-flower-123456.us-east-2.aws.neon.tech/neondb?sslmode=require&channel_binding=prefer"
    clean_url, connect_args = normalize_database_url(raw_neon_url)

    assert clean_url.startswith("postgresql+asyncpg://")
    assert "channel_binding" not in clean_url
    assert "sslmode" not in clean_url
    assert connect_args == {"ssl": "require"}


def test_normalize_database_url_sqlite():
    """Verifies that non-PostgreSQL URLs like SQLite pass through untouched without SSL connect_args."""
    from app.database import normalize_database_url

    raw_sqlite_url = "sqlite+aiosqlite:///./test.db"
    clean_url, connect_args = normalize_database_url(raw_sqlite_url)

    assert clean_url == raw_sqlite_url
    assert connect_args == {}


@pytest.mark.asyncio
async def test_parent_request_forwards_to_telegram(async_client: AsyncClient, monkeypatch):
    """Verifies that creating a parent request formats an admin card with inline buttons and dispatches to ADMIN_GROUP_ID."""
    from unittest.mock import AsyncMock, MagicMock
    from app.config import settings
    import app.bot.bot_instance as bot_inst

    mock_send_message = AsyncMock(return_value=MagicMock(message_id=999))
    mock_bot = MagicMock()
    mock_bot.send_message = mock_send_message

    mock_app = MagicMock()
    mock_app.bot = mock_bot

    monkeypatch.setattr(bot_inst, "bot_app", mock_app)
    monkeypatch.setattr(settings, "ADMIN_GROUP_ID", -1001999999999)
    monkeypatch.setattr(settings, "MINI_APP_URL", "https://t.me/MentorLinkBot/admin")

    payload = {
        "parent_name": "Tigist Alemu",
        "phone_number": "+251911998877",
        "student_level": "Primary 5-8",
        "subjects": ["English", "Maths"],
        "preferred_gender": "Female",
        "preferred_experience": "Fresh Graduate",
        "location_subcity": "Arada",
        "location_landmark": "Near Piassa",
        "schedule_days": ["Tue", "Thu", "Sat"],
        "time_slot": "5:00 PM - 7:00 PM",
        "session_duration": "2 hrs",
        "budget_etb": 3500.0
    }

    response = await async_client.post("/api/v1/parents/request", json=payload)
    assert response.status_code == 201
    created_id = response.json()["id"]

    assert mock_send_message.called
    call_kwargs = mock_send_message.call_args.kwargs
    assert call_kwargs["chat_id"] == -1001999999999
    assert "PARENT REQUEST" in call_kwargs["text"]
    assert "Pending" in call_kwargs["text"]
    assert "Tigist Alemu" in call_kwargs["text"]
    assert "Arada" in call_kwargs["text"]
    assert "Near Piassa" in call_kwargs["text"]

    # Verify compact inline buttons
    reply_markup = call_kwargs["reply_markup"]
    buttons = next(row for row in reply_markup.inline_keyboard if any(button.callback_data for button in row))
    assert buttons[0].text in ("🔍 Match Radar", "🔍 Match Tutors")
    assert buttons[0].callback_data == f"match_parent:{created_id}"
    assert buttons[1].text in ("❌ Close Request", "❌ Close")
    assert buttons[1].callback_data == f"close_parent:{created_id}"
    review_button = next(button for row in reply_markup.inline_keyboard for button in row if button.text == "Review in App")
    assert review_button.url == f"https://t.me/MentorLinkBot/admin?startapp=request_{created_id}"


@pytest.mark.asyncio
async def test_tutor_registration_forwards_to_telegram(async_client: AsyncClient, monkeypatch):
    """Verifies that registering a tutor formats a compact verification card with inline buttons and dispatches to ADMIN_GROUP_ID."""
    from unittest.mock import AsyncMock, MagicMock
    from app.config import settings
    import app.bot.bot_instance as bot_inst

    mock_send_message = AsyncMock(return_value=MagicMock(message_id=1000))
    mock_bot = MagicMock()
    mock_bot.send_message = mock_send_message

    mock_app = MagicMock()
    mock_app.bot = mock_bot

    monkeypatch.setattr(bot_inst, "bot_app", mock_app)
    monkeypatch.setattr(settings, "ADMIN_GROUP_ID", -1001999999999)
    monkeypatch.setattr(settings, "TUTOR_REGISTRATION_TOPIC_ID", None)
    monkeypatch.setattr(settings, "MINI_APP_URL", "https://t.me/MentorLinkBot/admin")

    payload = {
        "telegram_user_id": 554433221,
        "full_name": "Dawit Bekele",
        "gender": "Male",
        "phone_number": "+251933445566",
        "university": "Addis Ababa University",
        "department": "Mathematics",
        "education_year": "Graduate",
        "subjects_qualified": ["Maths", "Calculus"],
        "grades_qualified": ["Prep 11-12", "Freshman"],
        "years_of_experience": 4.0,
        "expected_fee_etb": 500.0,
        "base_subcity": "Kirkos",
        "coverage_areas": ["Kirkos", "Bole", "Lideta"],
        "availability_schedule": "Daily after 4 PM",
        "id_document_url": "https://example.com/id/dawit.pdf",
        "entrance_result": 88
    }

    response = await async_client.post("/api/v1/tutors/register", json=payload)
    assert response.status_code == 201
    created_id = response.json()["id"]

    assert mock_send_message.called
    call_kwargs = mock_send_message.call_args.kwargs
    assert call_kwargs["chat_id"] == -1001999999999
    assert ("TUTOR TICKET" in call_kwargs["text"] or "TUTOR PROFILE" in call_kwargs["text"])
    assert "Pending Verification" in call_kwargs["text"]
    assert "Dawit Bekele" in call_kwargs["text"]
    assert "Kirkos" in call_kwargs["text"]
    assert "<blockquote>" in call_kwargs["text"]
    assert "https://example.com/id/dawit.pdf" not in call_kwargs["text"]
    assert "Entrance result: 88" in call_kwargs["text"]

    # Verify compact inline buttons
    reply_markup = call_kwargs["reply_markup"]
    buttons = next(row for row in reply_markup.inline_keyboard if any(button.callback_data and button.callback_data.startswith("approve_tutor:") for button in row))
    assert buttons[0].text == "✅ Approve"
    assert buttons[0].callback_data == f"approve_tutor:{created_id}"
    assert buttons[1].text == "❌ Reject"
    assert buttons[1].callback_data == f"reject_tutor:{created_id}"
    review_button = next(button for row in reply_markup.inline_keyboard for button in row if button.text == "Review in App")
    assert review_button.url == f"https://t.me/MentorLinkBot/admin?startapp=tutor_{created_id}"


@pytest.mark.asyncio
async def test_topic_routing_when_configured(async_client: AsyncClient, monkeypatch):
    """Verifies that message_thread_id is passed when topic IDs are configured."""
    from unittest.mock import AsyncMock, MagicMock
    from app.config import settings
    import app.bot.bot_instance as bot_inst

    mock_send_message = AsyncMock(return_value=MagicMock(message_id=2000))
    mock_bot = MagicMock()
    mock_bot.send_message = mock_send_message
    mock_app = MagicMock()
    mock_app.bot = mock_bot

    monkeypatch.setattr(bot_inst, "bot_app", mock_app)
    monkeypatch.setattr(settings, "ADMIN_GROUP_ID", -1001999999999)
    monkeypatch.setattr(settings, "PARENT_REQUESTS_TOPIC_ID", 101)
    monkeypatch.setattr(settings, "TUTOR_REGISTRATION_TOPIC_ID", 202)

    # 1. Parent Request topic check
    payload_parent = {
        "parent_name": "Topic Parent",
        "phone_number": "+251911882233",
        "student_level": "Primary 5-8",
        "subjects": ["Maths"],
        "preferred_gender": "No preference",
        "preferred_experience": "Fresh Graduate",
        "location_subcity": "Bole",
        "schedule_days": ["Mon"],
        "time_slot": "4:00 PM",
        "session_duration": "1 hr",
        "budget_etb": 2000.0
    }
    resp1 = await async_client.post("/api/v1/parents/request", json=payload_parent)
    assert resp1.status_code == 201
    assert mock_send_message.call_args.kwargs.get("message_thread_id") == 101

    # 2. Tutor Registration topic check
    payload_tutor = {
        "telegram_user_id": 999111222,
        "full_name": "Topic Tutor",
        "gender": "Female",
        "phone_number": "+251922776655",
        "university": "AAU",
        "department": "Physics",
        "education_year": "Graduate",
        "subjects_qualified": ["Physics"],
        "grades_qualified": ["High School 9-10"],
        "years_of_experience": 2.0,
        "expected_fee_etb": 300.0,
        "base_subcity": "Bole",
        "coverage_areas": ["Bole"],
        "availability_schedule": "Weekends"
    }
    resp2 = await async_client.post("/api/v1/tutors/register", json=payload_tutor)
    assert resp2.status_code == 201
    assert mock_send_message.call_args.kwargs.get("message_thread_id") == 202


@pytest.mark.asyncio
async def test_topic_routing_fallback_to_main_group(async_client: AsyncClient, monkeypatch):
    """Verifies that omitting topic IDs falls back cleanly without message_thread_id."""
    from unittest.mock import AsyncMock, MagicMock
    from app.config import settings
    import app.bot.bot_instance as bot_inst

    mock_send_message = AsyncMock(return_value=MagicMock(message_id=2001))
    mock_bot = MagicMock()
    mock_bot.send_message = mock_send_message
    mock_app = MagicMock()
    mock_app.bot = mock_bot

    monkeypatch.setattr(bot_inst, "bot_app", mock_app)
    monkeypatch.setattr(settings, "ADMIN_GROUP_ID", -1001999999999)
    monkeypatch.setattr(settings, "PARENT_REQUESTS_TOPIC_ID", None)

    payload = {
        "parent_name": "Fallback Parent",
        "phone_number": "+251911000111",
        "student_level": "Primary 1-4",
        "subjects": ["English"],
        "preferred_gender": "No preference",
        "preferred_experience": "Fresh Graduate",
        "location_subcity": "Yeka",
        "schedule_days": ["Tue"],
        "time_slot": "3:00 PM",
        "session_duration": "1 hr",
        "budget_etb": 2500.0
    }
    resp = await async_client.post("/api/v1/parents/request", json=payload)
    assert resp.status_code == 201
    assert "message_thread_id" not in mock_send_message.call_args.kwargs


def test_settings_topic_id_parsing():
    """Verifies that Settings safely parses empty string or valid integers for topic IDs."""
    from app.config import Settings

    s1 = Settings(PARENT_REQUESTS_TOPIC_ID="", TUTOR_REGISTRATION_TOPIC_ID="")
    assert s1.PARENT_REQUESTS_TOPIC_ID is None
    assert s1.TUTOR_REGISTRATION_TOPIC_ID is None

    s2 = Settings(PARENT_REQUESTS_TOPIC_ID="12345", TUTOR_REGISTRATION_TOPIC_ID=67890)
    assert s2.PARENT_REQUESTS_TOPIC_ID == 12345
    assert s2.TUTOR_REGISTRATION_TOPIC_ID == 67890


@pytest.mark.asyncio
async def test_upload_tutor_document_success(async_client: AsyncClient, monkeypatch):
    """Public browser tutor intake can upload a credential without Telegram initData."""
    from app.config import settings
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")
    monkeypatch.setattr(settings, "ALLOW_UNVERIFIED_WEB_PREVIEW", False)
    file_content = b"%PDF-1.4 Mock PDF Document Content"
    files = {"file": ("student_id.pdf", file_content, "application/pdf")}
    resp = await async_client.post("/api/v1/tutors/upload-document", files=files)
    assert resp.status_code == 201
    data = resp.json()
    assert re.match(r"^[0-9a-f]{32}\.pdf$", data["filename"])
    assert data["file_url"].startswith("/uploads/")
    assert data["file_url"].endswith(".pdf")


@pytest.mark.asyncio
async def test_upload_tutor_document_invalid_extension(async_client: AsyncClient):
    """Verifies that uploading an unsupported file type returns 400."""
    file_content = b"malicious binary or unsupported format"
    files = {"file": ("script.exe", file_content, "application/x-msdownload")}
    resp = await async_client.post("/api/v1/tutors/upload-document", files=files)
    assert resp.status_code == 400
    assert "Unsupported file format" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_parent_request_dynamic_forum_topic_and_index_card(async_client: AsyncClient, monkeypatch):
    """
    Verifies that creating a parent request:
    1. Dynamically creates dedicated forum topic `PAR-{id:04d} — Parent Name`
    2. Sends full management card with [ 🔍 Match Radar ] & [ ❌ Close Request ] into dedicated topic
    3. Posts ticket card with deep link [ 🔗 Open Workspace ] into parent requests directory topic
    4. Saves telegram_topic_id in the database record.
    """
    from unittest.mock import AsyncMock, MagicMock
    from app.config import settings
    import app.bot.bot_instance as bot_inst

    mock_topic = MagicMock(message_thread_id=7788)
    mock_create_topic = AsyncMock(return_value=mock_topic)
    mock_send_message = AsyncMock(side_effect=[
        MagicMock(message_id=901),  # Inside dedicated topic
        MagicMock(message_id=902)   # Inside directory index topic
    ])

    mock_bot = MagicMock()
    mock_bot.create_forum_topic = mock_create_topic
    mock_bot.send_message = mock_send_message

    mock_app = MagicMock()
    mock_app.bot = mock_bot

    monkeypatch.setattr(bot_inst, "bot_app", mock_app)
    monkeypatch.setattr(settings, "ADMIN_GROUP_ID", -1002345678901)
    monkeypatch.setattr(settings, "PARENT_REQUESTS_TOPIC_ID", 101)
    monkeypatch.setattr(settings, "MINI_APP_URL", "https://t.me/MentorLinkBot/admin")

    payload = {
        "parent_name": "Hiwot Tadesse",
        "phone_number": "+251911223344",
        "student_level": "High School 9-10",
        "subjects": ["Chemistry", "Biology"],
        "preferred_gender": "Female",
        "preferred_experience": "Experienced",
        "location_subcity": "Bole",
        "location_landmark": "Near Edna Mall",
        "schedule_days": ["Mon", "Wed", "Fri"],
        "time_slot": "4:30 PM - 6:30 PM",
        "session_duration": "2 hrs",
        "budget_etb": 500.0
    }

    response = await async_client.post("/api/v1/parents/request", json=payload)
    assert response.status_code == 201
    created_id = response.json()["id"]
    assert response.json()["telegram_topic_id"] == 7788

    # 1. Verify create_forum_topic called
    assert mock_create_topic.called
    topic_kwargs = mock_create_topic.call_args.kwargs
    assert topic_kwargs["chat_id"] == -1002345678901
    assert f"PAR-{created_id:04d} — Hiwot Tadesse" == topic_kwargs["name"]

    # 2. Verify 2 messages sent
    assert mock_send_message.call_count == 2

    # Call 1: Full management card inside dedicated topic
    call1_kwargs = mock_send_message.call_args_list[0].kwargs
    assert call1_kwargs["chat_id"] == -1002345678901
    assert call1_kwargs["message_thread_id"] == 7788
    assert "PARENT REQUEST | Pending" in call1_kwargs["text"]
    assert "<blockquote>" in call1_kwargs["text"]
    assert "Hiwot Tadesse" in call1_kwargs["text"]
    call1_buttons = next(row for row in call1_kwargs["reply_markup"].inline_keyboard if any(button.callback_data for button in row))
    assert call1_buttons[0].text == "🔍 Match Radar"
    assert call1_buttons[0].callback_data == f"match_parent:{created_id}"
    assert call1_buttons[1].text == "❌ Close Request"
    assert call1_buttons[1].callback_data == f"close_parent:{created_id}"

    # Call 2: Index ticket card inside directory topic
    call2_kwargs = mock_send_message.call_args_list[1].kwargs
    assert call2_kwargs["chat_id"] == -1002345678901
    assert call2_kwargs["message_thread_id"] == 101
    assert f"REQ-{created_id:04d}" in call2_kwargs["text"]
    assert "Hiwot Tadesse" in call2_kwargs["text"]
    assert "Bole" in call2_kwargs["text"]
    call2_buttons = call2_kwargs["reply_markup"].inline_keyboard[0]
    assert call2_buttons[0].text == "🔗 Open Workspace"
    assert call2_buttons[0].url == "https://t.me/c/2345678901/7788"
    assert call2_buttons[1].url == f"https://t.me/MentorLinkBot/admin?startapp=request_{created_id}"


@pytest.mark.asyncio
async def test_unauthenticated_parent_request_allowed_in_production(async_client: AsyncClient, monkeypatch):
    """
    Public browser intake works in production without Telegram initData and never trusts a client-supplied Telegram ID.
    """
    from app.config import settings
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")
    monkeypatch.setattr(settings, "ALLOW_UNVERIFIED_WEB_PREVIEW", False)

    payload = {
        "parent_name": "Unauth Parent",
        "phone_number": "+251911223344",
        "student_level": "Primary 1-4",
        "subjects": ["English"],
        "preferred_gender": "No preference",
        "preferred_experience": "Fresh Graduate",
        "location_subcity": "Bole",
        "schedule_days": ["Mon"],
        "time_slot": "4:00 PM",
        "session_duration": "2 hrs",
        "budget_etb": 350.0
    }
    resp = await async_client.post("/api/v1/parents/request", json=payload)
    assert resp.status_code == 201
    assert resp.json()["telegram_user_id"] is None


@pytest.mark.asyncio
async def test_invalid_telegram_credentials_still_rejected_for_public_intake(async_client: AsyncClient, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "BOT_TOKEN", "123456:invalid-test-token")
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")
    monkeypatch.setattr(settings, "ALLOW_UNVERIFIED_WEB_PREVIEW", False)
    response = await async_client.post(
        "/api/v1/parents/request",
        json={
            "parent_name": "Signed Session Test",
            "phone_number": "0911223344",
            "student_level": "Grade 8",
            "subjects": ["Maths"],
            "preferred_experience": "University Student",
            "location_subcity": "Bole",
            "schedule_days": ["Mon"],
            "time_slot": "4 PM",
            "session_duration": "1 hr",
            "budget_etb": 300,
        },
        headers={"Authorization": "tma invalid-init-data"},
    )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_authenticated_request_accepted_in_production(async_client: AsyncClient, monkeypatch):
    """
    Verifies that when ENVIRONMENT="production" and ALLOW_UNVERIFIED_WEB_PREVIEW=False,
    a request with a valid Telegram initData Authorization header is accepted and sets telegram_user_id.
    """
    import hashlib
    import hmac
    import json
    import time
    import urllib.parse
    from app.config import settings

    bot_token = "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11"
    monkeypatch.setattr(settings, "BOT_TOKEN", bot_token)
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")
    monkeypatch.setattr(settings, "ALLOW_UNVERIFIED_WEB_PREVIEW", False)

    user_data = json.dumps({"id": 778899, "first_name": "VerifiedParent"})
    auth_date = str(int(time.time()))
    params = {
        "auth_date": auth_date,
        "query_id": "AAHdF6IQAAAAAN0XohDhrOrc",
        "user": user_data,
    }
    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(params.items()))
    secret_key = hmac.new(b"WebAppData", bot_token.encode("utf-8"), hashlib.sha256).digest()
    params["hash"] = hmac.new(secret_key, data_check_string.encode("utf-8"), hashlib.sha256).hexdigest()
    init_data = urllib.parse.urlencode(params)

    payload = {
        "parent_name": "Verified Parent",
        "phone_number": "+251911223344",
        "student_level": "Primary 1-4",
        "subjects": ["English"],
        "preferred_gender": "No preference",
        "preferred_experience": "Fresh Graduate",
        "location_subcity": "Bole",
        "schedule_days": ["Mon"],
        "time_slot": "4:00 PM",
        "session_duration": "2 hrs",
        "budget_etb": 350.0,
    }

    resp = await async_client.post(
        "/api/v1/parents/request",
        json=payload,
        headers={"Authorization": f"tma {init_data}"}
    )
    assert resp.status_code == 201
    assert resp.json()["telegram_user_id"] == 778899


def test_webhook_settings_require_secret_and_https():
    """Webhook mode must not start without a secret and HTTPS endpoint."""
    from pydantic import ValidationError
    from app.config import Settings

    with pytest.raises(ValidationError):
        Settings(BOT_MODE="webhook", WEBHOOK_URL="http://example.com/telegram", WEBHOOK_SECRET="secret")

    with pytest.raises(ValidationError):
        Settings(BOT_MODE="webhook", WEBHOOK_URL="https://example.com/telegram")


@pytest.mark.asyncio
async def test_webhook_rejects_invalid_secret(async_client: AsyncClient, monkeypatch):
    """Webhook requests with an invalid path/header secret are rejected."""
    from app.config import settings

    monkeypatch.setattr(settings, "BOT_MODE", "webhook")
    monkeypatch.setattr(settings, "WEBHOOK_SECRET", "test-secret")
    response = await async_client.post(
        "/telegram/webhook/wrong-secret",
        json={"update_id": 1},
        headers={"X-Telegram-Bot-Api-Secret-Token": "wrong-secret"},
    )
    assert response.status_code == 404


def test_get_webapp_url_prioritizes_actual_web_hosting_domain(monkeypatch):
    """
    Verifies that _get_webapp_url prioritizes direct web URLs over t.me links,
    and falls back safely for test backwards compatibility.
    """
    from app.config import settings
    from app.bot.handlers import _get_webapp_url

    # When both are configured and MINI_APP_URL is a t.me link, WEBAPP_URL must be chosen
    monkeypatch.setattr(settings, "WEBAPP_URL", "https://mentorlink-frontend.vercel.app")
    monkeypatch.setattr(settings, "MINI_APP_URL", "https://t.me/MentorLinkBot/app")
    assert _get_webapp_url() == "https://mentorlink-frontend.vercel.app"

    # When only MINI_APP_URL is set as web hosting URL
    monkeypatch.setattr(settings, "WEBAPP_URL", None)
    monkeypatch.setattr(settings, "MINI_APP_URL", "https://mentorlink.onrender.com")
    assert _get_webapp_url() == "https://mentorlink.onrender.com"

    # Backwards compatibility fallback for test fixtures setting MINI_APP_URL to t.me
    monkeypatch.setattr(settings, "WEBAPP_URL", None)
    monkeypatch.setattr(settings, "MINI_APP_URL", "https://t.me/MentorLinkBot/app")
    assert _get_webapp_url() == "https://t.me/MentorLinkBot/app"




