"""Phase 4 — Ops Layer tests.

Covers:
- Incident CRUD endpoints
- Red-flag detector
- Role enforcement (verifier-only routes reject matcher, etc.)
- Admin user CRUD (super_admin only)
- Audit log viewer (super_admin only)
- /complaint bot command
"""
import hashlib
import hmac
import json
import time
from urllib.parse import urlencode
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import (
    AdminUser, AuditLog, ParentRequest, Tutor,
    TutorIncident, TutorVerification, SystemSetting,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _telegram_auth_header(user_id: int, bot_token: str) -> dict[str, str]:
    params = {
        "auth_date": str(int(time.time())),
        "user": json.dumps({"id": user_id, "first_name": "Admin"}),
    }
    data_check_string = "\n".join(f"{key}={value}" for key, value in sorted(params.items()))
    secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    params["hash"] = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
    return {"Authorization": f"tma {urlencode(params)}"}


def _tutor(name: str, **overrides) -> Tutor:
    defaults = dict(
        full_name=name, gender="Male", phone_number="+251911000001",
        university="AAU", department="CS", education_year="3rd Year",
        subjects_qualified=["Maths"], grades_qualified=["Primary 5-8"],
        years_of_experience=1.0, expected_fee_etb=300.0,
        base_subcity="Bole", coverage_areas=["Bole"],
        availability_schedule="Flexible", status="verified",
    )
    defaults.update(overrides)
    return Tutor(**defaults)


# ===========================================================================
# Incident CRUD
# ===========================================================================

@pytest.mark.asyncio
async def test_create_and_list_incidents(async_client: AsyncClient, db_session: AsyncSession, monkeypatch):
    bot_token = "123456:ABC"
    admin_id = 800001
    monkeypatch.setattr(settings, "BOT_TOKEN", bot_token)
    monkeypatch.setattr(settings, "SUPER_ADMIN_ID", None)
    monkeypatch.setattr(settings, "ALLOW_UNVERIFIED_WEB_PREVIEW", False)

    tutor = _tutor("Incident Tutor")
    db_session.add_all([AdminUser(telegram_id=admin_id, role="admin", is_active=True), tutor])
    await db_session.commit()

    # Create incident
    resp = await async_client.post(
        "/api/v1/admin/incidents",
        json={"tutor_id": tutor.id, "severity": "high", "description": "Missed multiple sessions"},
        headers=_telegram_auth_header(admin_id, bot_token),
    )
    assert resp.status_code == 201
    incident = resp.json()
    assert incident["severity"] == "high"
    assert incident["status"] == "open"
    assert incident["reported_by"] == admin_id

    # List incidents
    resp = await async_client.get(
        "/api/v1/admin/incidents",
        headers=_telegram_auth_header(admin_id, bot_token),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["id"] == incident["id"]

    # Audit log row created
    audit = (await db_session.execute(
        select(AuditLog).where(AuditLog.action == "create_incident")
    )).scalars().first()
    assert audit is not None
    assert audit.target_id == tutor.id


@pytest.mark.asyncio
async def test_patch_incident_resolve(async_client: AsyncClient, db_session: AsyncSession, monkeypatch):
    bot_token = "123456:ABC"
    admin_id = 800002
    monkeypatch.setattr(settings, "BOT_TOKEN", bot_token)
    monkeypatch.setattr(settings, "SUPER_ADMIN_ID", None)
    monkeypatch.setattr(settings, "ALLOW_UNVERIFIED_WEB_PREVIEW", False)

    tutor = _tutor("Resolve Tutor", phone_number="+251911000002")
    db_session.add_all([AdminUser(telegram_id=admin_id, role="admin", is_active=True), tutor])
    await db_session.flush()
    incident = TutorIncident(tutor_id=tutor.id, severity="low", description="Minor issue reported")
    db_session.add(incident)
    await db_session.commit()

    resp = await async_client.patch(
        f"/api/v1/admin/incidents/{incident.id}",
        json={"status": "resolved"},
        headers=_telegram_auth_header(admin_id, bot_token),
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "resolved"
    assert resp.json()["resolved_at"] is not None


# ===========================================================================
# Red-flag detector
# ===========================================================================

@pytest.mark.asyncio
async def test_flags_detect_missing_doc_and_duplicate_phone(async_client: AsyncClient, db_session: AsyncSession, monkeypatch):
    bot_token = "123456:ABC"
    admin_id = 800003
    monkeypatch.setattr(settings, "BOT_TOKEN", bot_token)
    monkeypatch.setattr(settings, "SUPER_ADMIN_ID", None)
    monkeypatch.setattr(settings, "ALLOW_UNVERIFIED_WEB_PREVIEW", False)

    # Two tutors with same phone and no document
    t1 = _tutor("Flag Tutor A", phone_number="+251911999999", id_document_url=None)
    t2 = _tutor("Flag Tutor B", phone_number="+251911999999", id_document_url=None)
    db_session.add_all([AdminUser(telegram_id=admin_id, role="admin", is_active=True), t1, t2])
    await db_session.commit()

    resp = await async_client.get(
        "/api/v1/admin/flags",
        headers=_telegram_auth_header(admin_id, bot_token),
    )
    assert resp.status_code == 200
    flags = resp.json()
    flag_types = [f["flag_type"] for f in flags]
    # Both should have missing_document and duplicate_phone flags
    assert flag_types.count("duplicate_phone") == 2
    assert flag_types.count("missing_document") == 2
    # Flags sorted by severity: high first
    assert flags[0]["severity"] == "high"


@pytest.mark.asyncio
async def test_flags_detect_low_entrance_score(async_client: AsyncClient, db_session: AsyncSession, monkeypatch):
    bot_token = "123456:ABC"
    admin_id = 800004
    monkeypatch.setattr(settings, "BOT_TOKEN", bot_token)
    monkeypatch.setattr(settings, "SUPER_ADMIN_ID", None)
    monkeypatch.setattr(settings, "ALLOW_UNVERIFIED_WEB_PREVIEW", False)

    tutor = _tutor("Low Score", phone_number="+251911000003",
                    entrance_result=30.0, id_document_url="/uploads/id.pdf")
    db_session.add_all([AdminUser(telegram_id=admin_id, role="admin", is_active=True), tutor])
    await db_session.commit()

    resp = await async_client.get(
        "/api/v1/admin/flags",
        headers=_telegram_auth_header(admin_id, bot_token),
    )
    assert resp.status_code == 200
    flags = resp.json()
    low_score_flags = [f for f in flags if f["flag_type"] == "low_entrance_score"]
    assert len(low_score_flags) == 1
    assert "30" in low_score_flags[0]["detail"]


# ===========================================================================
# Role enforcement
# ===========================================================================

@pytest.mark.asyncio
async def test_verifier_role_normalized_and_allowed_on_matcher_routes(async_client: AsyncClient, db_session: AsyncSession, monkeypatch):
    """A legacy verifier admin is normalized to admin and allowed on operational routes."""
    bot_token = "123456:ABC"
    admin_id = 800005
    monkeypatch.setattr(settings, "BOT_TOKEN", bot_token)
    monkeypatch.setattr(settings, "SUPER_ADMIN_ID", None)
    monkeypatch.setattr(settings, "ALLOW_UNVERIFIED_WEB_PREVIEW", False)

    tutor = _tutor("Verifier Allowed", phone_number="+251911000004", status="pending")
    db_session.add_all([AdminUser(telegram_id=admin_id, role="verifier", is_active=True), tutor])
    await db_session.commit()

    # Verification PATCH is allowed (not 403)
    resp = await async_client.patch(
        f"/api/v1/admin/tutors/{tutor.id}/verification",
        json={"id_verified": True},
        headers=_telegram_auth_header(admin_id, bot_token),
    )
    assert resp.status_code == 200
    assert resp.json()["id_verified"] is True


@pytest.mark.asyncio
async def test_matcher_role_normalized_and_allowed_on_verifier_routes(async_client: AsyncClient, db_session: AsyncSession, monkeypatch):
    """A legacy matcher admin is normalized to admin and allowed on verification and reject routes."""
    bot_token = "123456:ABC"
    admin_id = 800006
    monkeypatch.setattr(settings, "BOT_TOKEN", bot_token)
    monkeypatch.setattr(settings, "SUPER_ADMIN_ID", None)
    monkeypatch.setattr(settings, "ALLOW_UNVERIFIED_WEB_PREVIEW", False)

    tutor = _tutor("Matcher Allowed", phone_number="+251911000005", status="pending")
    db_session.add_all([AdminUser(telegram_id=admin_id, role="matcher", is_active=True), tutor])
    await db_session.commit()

    # Verification PATCH is allowed (not 403)
    resp = await async_client.patch(
        f"/api/v1/admin/tutors/{tutor.id}/verification",
        json={"id_verified": True},
        headers=_telegram_auth_header(admin_id, bot_token),
    )
    assert resp.status_code == 200

    # Reject is allowed (not 403)
    resp = await async_client.post(
        f"/api/v1/admin/tutors/{tutor.id}/reject",
        json={"reason": "Does not meet requirements"},
        headers=_telegram_auth_header(admin_id, bot_token),
    )
    assert resp.status_code == 200


# ===========================================================================
# Admin user CRUD (super_admin only)
# ===========================================================================

@pytest.mark.asyncio
async def test_admin_crud_super_admin_only(async_client: AsyncClient, db_session: AsyncSession, monkeypatch):
    bot_token = "123456:ABC"
    super_id = 800007
    normal_id = 800008
    monkeypatch.setattr(settings, "BOT_TOKEN", bot_token)
    monkeypatch.setattr(settings, "SUPER_ADMIN_ID", super_id)
    monkeypatch.setattr(settings, "ALLOW_UNVERIFIED_WEB_PREVIEW", False)

    # Normal admin cannot list admins
    db_session.add(AdminUser(telegram_id=normal_id, role="admin", is_active=True))
    await db_session.commit()

    resp = await async_client.get(
        "/api/v1/admin/admins",
        headers=_telegram_auth_header(normal_id, bot_token),
    )
    assert resp.status_code == 403

    # Super admin can list
    resp = await async_client.get(
        "/api/v1/admin/admins",
        headers=_telegram_auth_header(super_id, bot_token),
    )
    assert resp.status_code == 200

    # Adding legacy role returns 422
    resp_invalid = await async_client.post(
        "/api/v1/admin/admins",
        json={"telegram_id": 999002, "role": "verifier"},
        headers=_telegram_auth_header(super_id, bot_token),
    )
    assert resp_invalid.status_code == 422

    # Super admin can add valid admin role
    resp = await async_client.post(
        "/api/v1/admin/admins",
        json={"telegram_id": 999001, "role": "admin"},
        headers=_telegram_auth_header(super_id, bot_token),
    )
    assert resp.status_code == 201
    assert resp.json()["role"] == "admin"

    # Super admin can delete
    resp = await async_client.delete(
        "/api/v1/admin/admins/999001",
        headers=_telegram_auth_header(super_id, bot_token),
    )
    assert resp.status_code == 200

    # Bootstrap super_admin has no AdminUser row, so DELETE returns 404
    resp = await async_client.delete(
        f"/api/v1/admin/admins/{super_id}",
        headers=_telegram_auth_header(super_id, bot_token),
    )
    assert resp.status_code == 404  # no DB row for bootstrap admin


# ===========================================================================
# Audit log viewer (super_admin only)
# ===========================================================================

@pytest.mark.asyncio
async def test_audit_log_super_admin_only(async_client: AsyncClient, db_session: AsyncSession, monkeypatch):
    bot_token = "123456:ABC"
    super_id = 800009
    admin_id = 800010
    monkeypatch.setattr(settings, "BOT_TOKEN", bot_token)
    monkeypatch.setattr(settings, "SUPER_ADMIN_ID", super_id)
    monkeypatch.setattr(settings, "ALLOW_UNVERIFIED_WEB_PREVIEW", False)

    db_session.add(AdminUser(telegram_id=admin_id, role="admin", is_active=True))
    await db_session.commit()

    # Normal admin cannot access audit log
    resp = await async_client.get(
        "/api/v1/admin/audit",
        headers=_telegram_auth_header(admin_id, bot_token),
    )
    assert resp.status_code == 403

    # Super admin can access
    resp = await async_client.get(
        "/api/v1/admin/audit",
        headers=_telegram_auth_header(super_id, bot_token),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert "total" in data
