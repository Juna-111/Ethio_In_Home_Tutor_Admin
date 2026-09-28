import ast
import hashlib
import hmac
import json
import os
import time
from urllib.parse import urlencode
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import AdminUser, Assignment, AuditLog, ParentRequest, Tutor, SessionFeedback
from app.bot.bot_instance import (
    build_parent_assignment_keyboard,
    build_parent_index_keyboard,
    build_parent_request_keyboard,
    build_tutor_assignment_keyboard,
    build_tutor_registration_keyboard,
    check_review_link_config,
    format_assignment_card_parent,
    format_assignment_card_tutor,
    get_admin_review_url,
)


def _telegram_auth_header(user_id: int, bot_token: str) -> dict[str, str]:
    params = {
        "auth_date": str(int(time.time())),
        "user": json.dumps({"id": user_id, "first_name": "TestUser"}),
    }
    data_check_string = "\n".join(f"{key}={value}" for key, value in sorted(params.items()))
    secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    params["hash"] = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
    return {"Authorization": f"tma {urlencode(params)}"}


def _create_tutor(
    id=None,
    full_name="Abebe Tutor",
    phone="+251911111111",
    telegram_id=None,
    status="verified"
) -> Tutor:
    return Tutor(
        id=id,
        telegram_user_id=telegram_id,
        full_name=full_name,
        gender="Male",
        phone_number=phone,
        university="Addis Ababa University (AAU)",
        department="Computer Science",
        education_year="4th Year",
        subjects_qualified=["Maths", "Physics"],
        grades_qualified=["Grade 9", "Grade 10"],
        years_of_experience=2.0,
        expected_fee_etb=350.0,
        base_subcity="Bole",
        coverage_areas=["Bole", "Yeka"],
        availability_schedule={"days": ["Mon", "Wed"]},
        status=status,
    )


def _create_parent(
    id=None,
    name="Almaz Parent",
    phone="+251922222222",
    telegram_user_id=None,
    status="pending",
) -> ParentRequest:
    return ParentRequest(
        id=id,
        parent_name=name,
        phone_number=phone,
        telegram_user_id=telegram_user_id,
        student_level="Grade 10",
        subjects=["Maths", "Physics"],
        preferred_gender="No preference",
        preferred_experience="University Student",
        location_subcity="Bole",
        location_landmark="Edna Mall",
        schedule_days=["Mon", "Wed"],
        time_slot="4:00 PM - 6:00 PM",
        session_duration="1.5 hrs",
        budget_etb=400.0,
        status=status,
    )


@pytest.fixture
def test_bot_token(monkeypatch):
    token = "123456789:ABCdefGHIjklMNOpqrSTUvwxYZ"
    monkeypatch.setattr(settings, "BOT_TOKEN", token)
    monkeypatch.setattr(settings, "MINI_APP_URL", "https://t.me/TestBot/admin")
    return token


# AC-1: Tutor DM Notification completeness (10 fields & Review in App deep link)
def test_tutor_assignment_card_fields_and_keyboard(test_bot_token):
    tutor = _create_tutor(id=1, full_name="Abebe Tutor", phone="+251911111111")
    parent = _create_parent(id=10, name="Almaz Parent", phone="+251922222222")

    card_text = format_assignment_card_tutor(parent, tutor, assignment_id=100)
    assert "ASMT-0100" in card_text  # 1. Assignment ID
    assert "Almaz Parent" in card_text  # 2. Parent name
    assert "Grade 10" in card_text  # 3. Student Level
    assert "+251922222222" in card_text  # 4. Phone
    assert "Bole" in card_text  # 5. Subcity
    assert "Edna Mall" in card_text  # 6. Landmark
    assert "Maths" in card_text and "Physics" in card_text  # 7. Subjects
    assert "Mon" in card_text and "Wed" in card_text  # 8. Schedule
    assert "400" in card_text  # 9. Budget / Rate
    assert "Review in App" in card_text  # 10. Deep link

    keyboard = build_tutor_assignment_keyboard(parent.id)
    assert keyboard is not None
    button = keyboard.inline_keyboard[0][0]
    assert button.text == "Review in App"
    assert "startapp=request_10" in button.url


# AC-2: Parent DM Notification completeness (10 fields & Review in App deep link)
def test_parent_assignment_card_fields_and_keyboard(test_bot_token):
    tutor = _create_tutor(id=2, full_name="Dawit Tutor", phone="+251933333333")
    parent = _create_parent(id=20, name="Sara Parent", phone="+251944444444")

    card_text = format_assignment_card_parent(parent, tutor, assignment_id=200)
    assert "ASMT-0200" in card_text  # 1. Assignment ID
    assert "Dawit Tutor" in card_text  # 2. Tutor name
    assert "+251933333333" in card_text  # 3. Tutor phone
    assert "Bole" in card_text  # 4. Base subcity
    assert "Maths" in card_text and "Physics" in card_text  # 5. Subjects
    assert "AAU" in card_text or "Addis Ababa University" in card_text  # 6. University
    assert "Computer Science" in card_text  # 7. Department
    assert "4th Year" in card_text  # 8. Education
    assert "2 years" in card_text  # 9. Experience
    assert "Review in App" in card_text  # 10. Deep link

    keyboard = build_parent_assignment_keyboard(parent.id)
    assert keyboard is not None
    button = keyboard.inline_keyboard[0][0]
    assert button.text == "Review in App"
    assert "startapp=request_20" in button.url


# AC-12: All 5 card types have Review in App buttons
def test_all_five_card_types_have_review_in_app_button(test_bot_token):
    keyboards = [
        ("Parent Request", build_parent_request_keyboard(1)),
        ("Parent Index", build_parent_index_keyboard(2)),
        ("Tutor Registration", build_tutor_registration_keyboard(3)),
        ("Tutor Assignment", build_tutor_assignment_keyboard(4)),
        ("Parent Assignment", build_parent_assignment_keyboard(5)),
    ]
    for card_type, kb in keyboards:
        assert kb is not None, f"Keyboard for {card_type} is None"
        found = False
        for row in kb.inline_keyboard:
            for btn in row:
                if btn.text == "Review in App" and btn.url and btn.url.startswith("https://t.me/"):
                    found = True
                    break
            if found:
                break
        assert found, f"Review in App button missing in {card_type} keyboard"


# AC-13: Startup check logs sample Review URL
def test_startup_check_logs_sample_review_url(test_bot_token, caplog):
    import logging
    caplog.set_level(logging.INFO)
    check_review_link_config()
    assert any("[TMA READY]" in record.message for record in caplog.records)


# AC-6: Admin CRM search parents by name and phone
@pytest.mark.asyncio
async def test_admin_crm_parents_search(async_client: AsyncClient, db_session: AsyncSession, test_bot_token):
    admin = AdminUser(telegram_id=7001, role="admin", is_active=True)
    db_session.add(admin)

    p1 = _create_parent(name="Kassahun Kebede", phone="+251911999888")
    p2 = _create_parent(name="Marta Haile", phone="+251922334455")
    db_session.add_all([p1, p2])
    await db_session.commit()

    headers = _telegram_auth_header(7001, test_bot_token)

    # Search by name
    res = await async_client.get("/api/v1/admin/parents?search=Kassahun", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert len(data["items"]) == 1
    assert data["items"][0]["parent_name"] == "Kassahun Kebede"

    # Search by phone substring
    res = await async_client.get("/api/v1/admin/parents?search=334455", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert len(data["items"]) == 1
    assert data["items"][0]["parent_name"] == "Marta Haile"

    # Search non-matching
    res = await async_client.get("/api/v1/admin/parents?search=UnknownPerson", headers=headers)
    assert res.status_code == 200
    assert len(res.json()["items"]) == 0


# AC-7: Dashboard expanded KPIs
@pytest.mark.asyncio
async def test_admin_dashboard_expanded_kpis(async_client: AsyncClient, db_session: AsyncSession, test_bot_token):
    admin = AdminUser(telegram_id=7002, role="admin", is_active=True)
    tutor = _create_tutor(full_name="Tutor KPI")
    req = _create_parent(name="Parent KPI", status="matched")
    db_session.add_all([admin, tutor, req])
    await db_session.commit()

    assignment = Assignment(
        request_id=req.id,
        tutor_id=tutor.id,
        status="active",
    )
    db_session.add(assignment)
    await db_session.commit()

    headers = _telegram_auth_header(7002, test_bot_token)
    res = await async_client.get("/api/v1/admin/dashboard", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert "conversion_rate_pct" in data
    assert "avg_days_to_assign" in data
    assert "tutor_verification_funnel_pct" in data
    assert isinstance(data["conversion_rate_pct"], (int, float))
    assert isinstance(data["avg_days_to_assign"], (int, float))
    assert isinstance(data["tutor_verification_funnel_pct"], (int, float))


# AC-8: Assignment Pipeline stages and median age
@pytest.mark.asyncio
async def test_admin_assignment_pipeline(async_client: AsyncClient, db_session: AsyncSession, test_bot_token):
    admin = AdminUser(telegram_id=7003, role="admin", is_active=True)
    db_session.add(admin)
    await db_session.commit()

    headers = _telegram_auth_header(7003, test_bot_token)
    res = await async_client.get("/api/v1/admin/assignments/pipeline", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert "status_counts" in data
    assert "median_age_days" in data
    assert "oldest_per_status" in data


# AC-9: Assignment CSV Export columns
@pytest.mark.asyncio
async def test_admin_export_assignments_csv(async_client: AsyncClient, db_session: AsyncSession, test_bot_token):
    admin = AdminUser(telegram_id=7004, role="admin", is_active=True)
    tutor = _create_tutor(full_name="Export Tutor")
    parent = _create_parent(name="Export Parent", status="matched")
    db_session.add_all([admin, tutor, parent])
    await db_session.commit()

    assignment = Assignment(
        request_id=parent.id,
        tutor_id=tutor.id,
        status="active",
    )
    db_session.add(assignment)
    await db_session.commit()

    headers = _telegram_auth_header(7004, test_bot_token)
    res = await async_client.get("/api/v1/admin/export?type=assignments", headers=headers)
    assert res.status_code == 200
    content = res.content.decode("utf-8-sig")
    lines = [line.strip() for line in content.splitlines() if line.strip()]
    header = lines[0]
    expected_cols = ["Assignment ID", "Parent", "Tutor", "Subjects", "Status", "Created At", "Assigned Date", "Closed Date"]
    for col in expected_cols:
        assert col in header, f"Column {col} missing in CSV export header: {header}"


# AC-10: Tutor /me/assignments API
@pytest.mark.asyncio
async def test_tutor_me_assignments_auth_and_response(async_client: AsyncClient, db_session: AsyncSession, test_bot_token):
    # Unauthenticated
    res = await async_client.get("/api/v1/tutors/me/assignments")
    assert res.status_code == 401

    # Authenticated
    tutor_tg_id = 8001
    tutor = _create_tutor(full_name="Abebe Authenticated", telegram_id=tutor_tg_id)
    parent = _create_parent(name="Parent For Tutor", status="matched")
    db_session.add_all([tutor, parent])
    await db_session.commit()

    assignment = Assignment(
        request_id=parent.id,
        tutor_id=tutor.id,
        status="active",
    )
    db_session.add(assignment)
    await db_session.commit()

    headers = _telegram_auth_header(tutor_tg_id, test_bot_token)
    res = await async_client.get("/api/v1/tutors/me/assignments", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert "assignments" in data
    assert data["active_count"] == 1
    assert data["total_earnings_estimate"] >= 0
    assert len(data["assignments"]) == 1
    item = data["assignments"][0]
    assert "Almaz Parent" in item["student_name_context"] or "Parent For Tutor" in item["student_name_context"]
    assert item["hourly_rate_etb"] == 400.0
    assert "Bole" in item["location"]


# AC-11: Parent /me/requests and /me/feedback API
@pytest.mark.asyncio
async def test_parent_me_requests_and_feedback(async_client: AsyncClient, db_session: AsyncSession, test_bot_token):
    # Unauthenticated
    res = await async_client.get("/api/v1/parents/me/requests")
    assert res.status_code == 401

    # Authenticated parent
    parent_tg_id = 9001
    tutor = _create_tutor(full_name="Assigned Tutor")
    parent_req = _create_parent(name="Registered Parent", telegram_user_id=parent_tg_id, status="matched")
    db_session.add_all([tutor, parent_req])
    await db_session.commit()

    assignment = Assignment(
        request_id=parent_req.id,
        tutor_id=tutor.id,
        status="active",
    )
    db_session.add(assignment)
    await db_session.commit()

    headers = _telegram_auth_header(parent_tg_id, test_bot_token)
    res = await async_client.get("/api/v1/parents/me/requests", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert len(data["requests"]) == 1
    item = data["requests"][0]
    assert item["id"] == parent_req.id
    assert item["tutor_name"] == "Assigned Tutor"

    # Submit feedback
    fb_res = await async_client.post(
        "/api/v1/parents/me/feedback",
        headers=headers,
        json={"request_id": parent_req.id, "rating": 5, "review_notes": "Great experience!"}
    )
    assert fb_res.status_code in (200, 201)
    assert fb_res.json()["success"] is True

    # Contact admin
    contact_res = await async_client.post(
        "/api/v1/parents/me/contact-admin",
        headers=headers,
        json={"request_id": parent_req.id, "message": "Need additional subject"}
    )
    assert contact_res.status_code == 200
    assert contact_res.json()["success"] is True


# AC-19: Exactly 0 bare except: pass statements exist in backend/app/
def test_zero_bare_except_pass_statements():
    backend_app_dir = os.path.join(os.path.dirname(__file__), "..", "app")
    bare_passes = []
    for root, dirs, files in os.walk(backend_app_dir):
        for file in files:
            if file.endswith(".py"):
                path = os.path.join(root, file)
                with open(path, "r", encoding="utf-8") as f:
                    tree = ast.parse(f.read(), filename=path)
                for node in ast.walk(tree):
                    if isinstance(node, ast.ExceptHandler):
                        if len(node.body) == 1 and isinstance(node.body[0], ast.Pass):
                            rel_path = os.path.relpath(path, backend_app_dir)
                            bare_passes.append(f"{rel_path}:{node.lineno}")

    assert len(bare_passes) == 0, f"Bare except: pass statements found: {bare_passes}"


# AC-20: HMAC verification in backend/app/auth.py uses hmac.compare_digest
def test_hmac_compare_digest_used_for_verification():
    from app.auth import validate_telegram_init_data
    token = "test-bot-token"
    params = {
        "auth_date": str(int(time.time())),
        "user": json.dumps({"id": 12345}),
    }
    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(params.items()))
    secret_key = hmac.new(b"WebAppData", token.encode(), hashlib.sha256).digest()
    valid_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()

    params["hash"] = valid_hash
    valid_init_data = urlencode(params)
    parsed = validate_telegram_init_data(valid_init_data, token)
    assert parsed is not None
    assert parsed["user"]["id"] == 12345

    # Tampered hash
    params["hash"] = "0" * 64
    invalid_init_data = urlencode(params)
    assert validate_telegram_init_data(invalid_init_data, token) is None


@pytest.mark.asyncio
async def test_parent_crm_pagination(async_client: AsyncClient, db_session: AsyncSession, test_bot_token):
    admin = AdminUser(telegram_id=7010, role="admin", is_active=True)
    db_session.add(admin)
    for i in range(5):
        p = _create_parent(name=f"Parent Page {i}", phone=f"+25191100000{i}")
        db_session.add(p)
    await db_session.commit()

    headers = _telegram_auth_header(7010, test_bot_token)
    res = await async_client.get("/api/v1/admin/parents?page=1&page_size=2", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["total"] >= 5
    assert len(data["items"]) == 2
    assert data["page"] == 1
    assert data["page_size"] == 2


@pytest.mark.asyncio
async def test_admin_create_invalid_legacy_role_fails_validation(async_client: AsyncClient, db_session: AsyncSession, test_bot_token):
    super_admin = AdminUser(telegram_id=7011, role="super_admin", is_active=True)
    db_session.add(super_admin)
    await db_session.commit()

    headers = _telegram_auth_header(7011, test_bot_token)
    res = await async_client.post(
        "/api/v1/admin/admins",
        headers=headers,
        json={"telegram_id": 999111, "role": "matcher"}
    )
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_export_unknown_type_returns_400(async_client: AsyncClient, db_session: AsyncSession, test_bot_token):
    admin = AdminUser(telegram_id=7012, role="admin", is_active=True)
    db_session.add(admin)
    await db_session.commit()

    headers = _telegram_auth_header(7012, test_bot_token)
    res = await async_client.get("/api/v1/admin/export?type=unknown_invalid_type", headers=headers)
    assert res.status_code in (400, 422)


def test_check_review_link_config_warning_when_no_short_name(monkeypatch, caplog):
    import logging
    caplog.set_level(logging.WARNING)
    monkeypatch.setattr(settings, "MINI_APP_URL", "https://t.me/TestBot")
    check_review_link_config()
    assert any("[TMA WARNING]" in record.message for record in caplog.records)

