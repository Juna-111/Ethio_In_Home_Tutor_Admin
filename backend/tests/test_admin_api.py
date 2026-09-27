import hashlib
import hmac
import json
import time
from urllib.parse import urlencode

import pytest
from fastapi import HTTPException
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.admin_auth import AdminPrincipal, require_role
from app.config import settings
from app.models import AdminUser, Assignment, AuditLog, ParentRequest, Tutor
from app.services.audit import log_action


def _telegram_auth_header(user_id: int, bot_token: str) -> dict[str, str]:
    params = {
        "auth_date": str(int(time.time())),
        "user": json.dumps({"id": user_id, "first_name": "Admin"}),
    }
    data_check_string = "\n".join(f"{key}={value}" for key, value in sorted(params.items()))
    secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    params["hash"] = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
    return {"Authorization": f"tma {urlencode(params)}"}


def _parent_request(name: str, status: str = "pending") -> ParentRequest:
    return ParentRequest(
        parent_name=name,
        phone_number="+251911223344",
        student_level="Grade 8",
        subjects=["Maths"],
        preferred_gender="No preference",
        preferred_experience="University Student",
        location_subcity="Bole",
        schedule_days=["Mon"],
        time_slot="4 PM",
        session_duration="1 hr",
        budget_etb=300,
        status=status,
    )


def _tutor(name: str, status: str = "pending") -> Tutor:
    return Tutor(
        full_name=name,
        gender="Female",
        phone_number="+251922334455",
        university="AAU",
        department="Maths",
        education_year="Graduate",
        subjects_qualified=["Maths"],
        grades_qualified=["Grade 8"],
        years_of_experience=2,
        expected_fee_etb=300,
        base_subcity="Bole",
        coverage_areas=["Bole"],
        availability_schedule="Weekends",
        status=status,
    )


@pytest.mark.asyncio
async def test_admin_dashboard_requires_telegram_auth(async_client: AsyncClient, monkeypatch):
    monkeypatch.setattr(settings, "ALLOW_UNVERIFIED_WEB_PREVIEW", False)

    response = await async_client.get("/api/v1/admin/dashboard")

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_admin_dashboard_forbids_authenticated_non_admin(async_client: AsyncClient, monkeypatch):
    bot_token = "123456:admin-test-token"
    monkeypatch.setattr(settings, "BOT_TOKEN", bot_token)
    monkeypatch.setattr(settings, "SUPER_ADMIN_ID", None)
    monkeypatch.setattr(settings, "ALLOW_UNVERIFIED_WEB_PREVIEW", False)

    response = await async_client.get(
        "/api/v1/admin/dashboard",
        headers=_telegram_auth_header(700001, bot_token),
    )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_admin_dashboard_counts_database_records(
    async_client: AsyncClient,
    db_session: AsyncSession,
    monkeypatch,
):
    bot_token = "123456:admin-test-token"
    admin_id = 700002
    monkeypatch.setattr(settings, "BOT_TOKEN", bot_token)
    monkeypatch.setattr(settings, "SUPER_ADMIN_ID", None)
    monkeypatch.setattr(settings, "ALLOW_UNVERIFIED_WEB_PREVIEW", False)

    parent_pending = _parent_request("Pending Parent")
    parent_matched = _parent_request("Matched Parent", status="matched")
    tutor_pending = _tutor("Pending Tutor")
    tutor_verified = _tutor("Verified Tutor", status="verified")
    db_session.add_all([
        AdminUser(telegram_id=admin_id, role="admin", is_active=True),
        parent_pending,
        parent_matched,
        tutor_pending,
        tutor_verified,
    ])
    await db_session.flush()
    db_session.add(Assignment(request_id=parent_matched.id, tutor_id=tutor_verified.id, status="active"))
    await db_session.commit()

    response = await async_client.get(
        "/api/v1/admin/dashboard",
        headers=_telegram_auth_header(admin_id, bot_token),
    )

    assert response.status_code == 200
    assert response.json() == {
        "admin_telegram_id": admin_id,
        "admin_role": "admin",
        "pending_tutors": 1,
        "pending_requests": 1,
        "active_assignments": 1,
        "requests_today": 2,
    }


@pytest.mark.asyncio
async def test_require_role_rejects_admin_without_required_role():
    verifier_only = require_role("verifier")

    with pytest.raises(HTTPException) as exc_info:
        await verifier_only(principal=AdminPrincipal(telegram_id=700003, role="admin"))

    assert exc_info.value.status_code == 403


@pytest.mark.asyncio
async def test_log_action_adds_event_to_callers_transaction(db_session: AsyncSession):
    event = log_action(
        db_session,
        actor_id=700004,
        action="tutor_reviewed",
        target_type="tutor",
        target_id=42,
        reason="Checklist complete",
    )
    await db_session.commit()

    stored_event = await db_session.get(AuditLog, event.id)
    assert stored_event is not None
    assert stored_event.actor_telegram_id == 700004
    assert stored_event.action == "tutor_reviewed"
    assert stored_event.source == "miniapp"