import hashlib
import hmac
import json
import time
from urllib.parse import urlencode
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.admin_auth import AdminPrincipal, require_role
from app.config import settings
from app.models import AdminUser, Assignment, AuditLog, MatchInvite, ParentRequest, Tutor
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
async def test_admin_parent_crm_paginates_parent_groups_without_losing_history(
    async_client: AsyncClient,
    db_session: AsyncSession,
    monkeypatch,
):
    bot_token = "123456:admin-test-token"
    admin_id = 700014
    monkeypatch.setattr(settings, "BOT_TOKEN", bot_token)
    monkeypatch.setattr(settings, "SUPER_ADMIN_ID", None)
    monkeypatch.setattr(settings, "ALLOW_UNVERIFIED_WEB_PREVIEW", False)

    first_parent_old = _parent_request("First Parent Old")
    first_parent_new = _parent_request("First Parent New")
    second_parent = _parent_request("Second Parent")
    second_parent.phone_number = "+251922334455"

    db_session.add_all([
        AdminUser(telegram_id=admin_id, role="admin", is_active=True),
        first_parent_old,
        first_parent_new,
        second_parent,
    ])
    await db_session.flush()

    # Make the first parent group clearly newer than the second group.
    from datetime import datetime, timedelta, timezone
    now = datetime.now(timezone.utc)
    first_parent_old.created_at = now - timedelta(days=2)
    first_parent_new.created_at = now - timedelta(days=1)
    second_parent.created_at = now - timedelta(days=3)
    await db_session.commit()

    response = await async_client.get(
        "/api/v1/admin/parents",
        params={"page": 1, "page_size": 1},
        headers=_telegram_auth_header(admin_id, bot_token),
    )

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 2
    assert len(data["items"]) == 1
    assert data["items"][0]["phone_number"] == first_parent_new.phone_number
    assert data["items"][0]["total_requests"] == 2
    assert [item["parent_name"] for item in data["items"][0]["requests"]] == [
        "First Parent New",
        "First Parent Old",
    ]


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
    data = response.json()
    assert data["admin_telegram_id"] == admin_id
    assert data["admin_role"] == "admin"
    assert data["pending_tutors"] == 1
    assert data["pending_requests"] == 1
    assert data["active_assignments"] == 1
    assert data["requests_today"] == 2
    assert data["conversion_rate_pct"] == 50.0
    assert data["tutor_verification_funnel_pct"] == 50.0


@pytest.mark.asyncio
async def test_require_role_rejects_admin_without_required_role():
    super_admin_only = require_role("super_admin")

    with pytest.raises(HTTPException) as exc_info:
        await super_admin_only(principal=AdminPrincipal(telegram_id=700003, role="admin"))

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


@pytest.mark.asyncio
async def test_admin_request_list_filters_and_paginates(
    async_client: AsyncClient,
    db_session: AsyncSession,
    monkeypatch,
):
    bot_token = "123456:admin-test-token"
    admin_id = 700005
    monkeypatch.setattr(settings, "BOT_TOKEN", bot_token)
    monkeypatch.setattr(settings, "SUPER_ADMIN_ID", None)
    monkeypatch.setattr(settings, "ALLOW_UNVERIFIED_WEB_PREVIEW", False)
    db_session.add_all([
        AdminUser(telegram_id=admin_id, role="admin", is_active=True),
        _parent_request("Bole Maths", status="pending"),
        ParentRequest(
            parent_name="Yeka Physics", phone_number="+251911223344", student_level="Grade 9",
            subjects=["Physics"], preferred_gender="No preference", preferred_experience="Fresh Graduate",
            location_subcity="Yeka", schedule_days=["Tue"], time_slot="5 PM", session_duration="1 hr",
            budget_etb=400, status="closed",
        ),
    ])
    await db_session.commit()

    response = await async_client.get(
        "/api/v1/admin/requests",
        params={"status": "pending", "subcity": "bole", "subject": "Maths", "page": 1, "page_size": 1},
        headers=_telegram_auth_header(admin_id, bot_token),
    )

    assert response.status_code == 200
    assert response.json()["total"] == 1
    assert response.json()["items"][0]["parent_name"] == "Bole Maths"


@pytest.mark.asyncio
async def test_candidate_response_includes_explainable_factor_scores(
    async_client: AsyncClient,
    db_session: AsyncSession,
    monkeypatch,
):
    bot_token = "123456:admin-test-token"
    admin_id = 700006
    monkeypatch.setattr(settings, "BOT_TOKEN", bot_token)
    monkeypatch.setattr(settings, "SUPER_ADMIN_ID", None)
    monkeypatch.setattr(settings, "ALLOW_UNVERIFIED_WEB_PREVIEW", False)
    parent = _parent_request("Score Parent")
    parent.schedule_days = ["Mon", "Tue"]
    parent.budget_etb = 400
    tutor = _tutor("Score Tutor", status="verified")
    tutor.education_year = "3rd Year"
    tutor.availability_schedule = ["Mon", "Fri"]
    tutor.expected_fee_etb = 350
    db_session.add_all([AdminUser(telegram_id=admin_id, role="admin", is_active=True), parent, tutor])
    await db_session.commit()
    await db_session.refresh(parent)

    response = await async_client.get(
        f"/api/v1/admin/requests/{parent.id}/candidates",
        headers=_telegram_auth_header(admin_id, bot_token),
    )

    assert response.status_code == 200
    candidate = response.json()["candidates"][0]
    assert candidate["full_name"] == "Score Tutor"
    assert candidate["overall_score"] == 92.5
    assert candidate["score_breakdown"]["subject_match"]["score"] == 100
    assert candidate["score_breakdown"]["schedule_overlap"]["score"] == 50
    assert "1 of 2 requested days" in candidate["score_breakdown"]["schedule_overlap"]["explanation"]


@pytest.mark.asyncio
async def test_admin_assignment_commits_one_assignment_and_audit_row(
    async_client: AsyncClient,
    db_session: AsyncSession,
    monkeypatch,
):
    bot_token = "123456:admin-test-token"
    admin_id = 700007
    monkeypatch.setattr(settings, "BOT_TOKEN", bot_token)
    monkeypatch.setattr(settings, "SUPER_ADMIN_ID", None)
    monkeypatch.setattr(settings, "ALLOW_UNVERIFIED_WEB_PREVIEW", False)
    parent = _parent_request("Assign Parent")
    tutor = _tutor("Assign Tutor", status="verified")
    db_session.add_all([AdminUser(telegram_id=admin_id, role="matcher", is_active=True), parent, tutor])
    await db_session.flush()
    db_session.add(MatchInvite(request_id=parent.id, tutor_id=tutor.id, status="yes"))
    await db_session.commit()

    response = await async_client.post(
        f"/api/v1/admin/requests/{parent.id}/assign",
        json={"tutor_id": tutor.id},
        headers=_telegram_auth_header(admin_id, bot_token),
    )

    assert response.status_code == 200
    assignments = (await db_session.execute(select(Assignment).where(Assignment.request_id == parent.id))).scalars().all()
    audits = (await db_session.execute(select(AuditLog).where(
        AuditLog.target_type == "parent_request", AuditLog.target_id == parent.id,
    ))).scalars().all()
    stored_parent = await db_session.get(ParentRequest, parent.id)
    assert len(assignments) == 1
    assert assignments[0].tutor_id == tutor.id
    assert stored_parent.status == "matched"
    assert len(audits) == 1
    assert audits[0].action == "assign_tutor"


@pytest.mark.asyncio
async def test_admin_assignment_notifies_parent_and_tutor(
    async_client: AsyncClient,
    db_session: AsyncSession,
    monkeypatch,
):
    """Regression test: assign() must DM both sides with each other's contact info."""
    bot_token = "123456:admin-test-token"
    admin_id = 700107
    monkeypatch.setattr(settings, "BOT_TOKEN", bot_token)
    monkeypatch.setattr(settings, "SUPER_ADMIN_ID", None)
    monkeypatch.setattr(settings, "ALLOW_UNVERIFIED_WEB_PREVIEW", False)
    import app.bot.bot_instance as bot_instance
    mock_bot = MagicMock()
    mock_bot.send_message = AsyncMock()
    monkeypatch.setattr(bot_instance, "bot_app", MagicMock(bot=mock_bot))

    parent = _parent_request("Notify Parent")
    parent.telegram_user_id = 900001
    tutor = _tutor("Notify Tutor", status="verified")
    tutor.telegram_user_id = 900002
    db_session.add_all([AdminUser(telegram_id=admin_id, role="matcher", is_active=True), parent, tutor])
    await db_session.flush()
    db_session.add(MatchInvite(request_id=parent.id, tutor_id=tutor.id, status="yes"))
    await db_session.commit()

    response = await async_client.post(
        f"/api/v1/admin/requests/{parent.id}/assign",
        json={"tutor_id": tutor.id},
        headers=_telegram_auth_header(admin_id, bot_token),
    )

    assert response.status_code == 200
    assert mock_bot.send_message.await_count == 2
    calls = mock_bot.send_message.await_args_list
    recipients = {c.kwargs["chat_id"] for c in calls}
    assert recipients == {parent.telegram_user_id, tutor.telegram_user_id}

    parent_call = next(c for c in calls if c.kwargs["chat_id"] == parent.telegram_user_id)
    tutor_call = next(c for c in calls if c.kwargs["chat_id"] == tutor.telegram_user_id)
    assert "Notify Tutor" in parent_call.kwargs["text"]
    assert tutor.phone_number in parent_call.kwargs["text"]
    assert "Notify Parent" in tutor_call.kwargs["text"]
    assert parent.phone_number in tutor_call.kwargs["text"]


@pytest.mark.asyncio
async def test_admin_assignment_notification_failure_does_not_break_assignment(
    async_client: AsyncClient,
    db_session: AsyncSession,
    monkeypatch,
):
    """If the Telegram DM fails (e.g. user blocked the bot), the assignment itself must still succeed."""
    bot_token = "123456:admin-test-token"
    admin_id = 700108
    monkeypatch.setattr(settings, "BOT_TOKEN", bot_token)
    monkeypatch.setattr(settings, "SUPER_ADMIN_ID", None)
    monkeypatch.setattr(settings, "ALLOW_UNVERIFIED_WEB_PREVIEW", False)
    import app.bot.bot_instance as bot_instance
    mock_bot = MagicMock()
    mock_bot.send_message = AsyncMock(side_effect=Exception("Forbidden: bot was blocked by the user"))
    monkeypatch.setattr(bot_instance, "bot_app", MagicMock(bot=mock_bot))

    parent = _parent_request("Blocked Parent")
    parent.telegram_user_id = 900003
    tutor = _tutor("Blocked Tutor", status="verified")
    tutor.telegram_user_id = 900004
    db_session.add_all([AdminUser(telegram_id=admin_id, role="matcher", is_active=True), parent, tutor])
    await db_session.flush()
    db_session.add(MatchInvite(request_id=parent.id, tutor_id=tutor.id, status="yes"))
    await db_session.commit()

    response = await async_client.post(
        f"/api/v1/admin/requests/{parent.id}/assign",
        json={"tutor_id": tutor.id},
        headers=_telegram_auth_header(admin_id, bot_token),
    )

    assert response.status_code == 200
    assignments = (await db_session.execute(select(Assignment).where(Assignment.request_id == parent.id))).scalars().all()
    assert len(assignments) == 1


@pytest.mark.asyncio
async def test_admin_tutor_search_matches_name_and_phone(
    async_client: AsyncClient,
    db_session: AsyncSession,
    monkeypatch,
):
    bot_token = "123456:admin-test-token"
    admin_id = 700110
    monkeypatch.setattr(settings, "BOT_TOKEN", bot_token)
    monkeypatch.setattr(settings, "SUPER_ADMIN_ID", None)
    monkeypatch.setattr(settings, "ALLOW_UNVERIFIED_WEB_PREVIEW", False)
    target = _tutor("Bethlehem Girma", status="verified")
    target.phone_number = "+251911223344"
    other = _tutor("Samuel Wolde", status="verified")
    other.phone_number = "+251955667788"
    db_session.add_all([AdminUser(telegram_id=admin_id, role="admin", is_active=True), target, other])
    await db_session.commit()
    headers = _telegram_auth_header(admin_id, bot_token)

    by_name = await async_client.get("/api/v1/admin/tutors?search=bethlehem", headers=headers)
    assert by_name.status_code == 200
    names = [item["full_name"] for item in by_name.json()["items"]]
    assert names == ["Bethlehem Girma"]

    by_phone = await async_client.get("/api/v1/admin/tutors?search=955667788", headers=headers)
    assert by_phone.status_code == 200
    names = [item["full_name"] for item in by_phone.json()["items"]]
    assert names == ["Samuel Wolde"]


@pytest.mark.asyncio
async def test_admin_coverage_gap_ratio_matches_seeded_counts(
    async_client: AsyncClient,
    db_session: AsyncSession,
    monkeypatch,
):
    bot_token = "123456:admin-test-token"
    admin_id = 700008
    monkeypatch.setattr(settings, "BOT_TOKEN", bot_token)
    monkeypatch.setattr(settings, "SUPER_ADMIN_ID", None)
    monkeypatch.setattr(settings, "ALLOW_UNVERIFIED_WEB_PREVIEW", False)
    first = _parent_request("Demand 1")
    second = _parent_request("Demand 2")
    supply = _tutor("Supply Tutor", status="verified")
    db_session.add_all([AdminUser(telegram_id=admin_id, role="admin", is_active=True), first, second, supply])
    await db_session.commit()

    response = await async_client.get(
        "/api/v1/admin/analytics/coverage-gaps",
        headers=_telegram_auth_header(admin_id, bot_token),
    )

    assert response.status_code == 200
    gap = next(item for item in response.json() if item["subcity"] == "Bole" and item["subject"] == "Maths")
    assert gap["pending_requests"] == 2
    assert gap["approved_tutors"] == 1
    assert gap["gap_ratio"] == 0.5


@pytest.mark.asyncio
async def test_admin_ping_sends_bulk_availability_prompt_and_audits(
    async_client: AsyncClient,
    db_session: AsyncSession,
    monkeypatch,
):
    bot_token = "123456:admin-test-token"
    admin_id = 700009
    monkeypatch.setattr(settings, "BOT_TOKEN", bot_token)
    monkeypatch.setattr(settings, "SUPER_ADMIN_ID", None)
    monkeypatch.setattr(settings, "ALLOW_UNVERIFIED_WEB_PREVIEW", False)
    import app.bot.bot_instance as bot_instance
    mock_bot = MagicMock()
    mock_bot.send_message = AsyncMock()
    monkeypatch.setattr(bot_instance, "bot_app", MagicMock(bot=mock_bot))
    parent = _parent_request("Ping Parent")
    tutor = _tutor("Ping Tutor", status="verified")
    tutor.telegram_user_id = 456123
    db_session.add_all([AdminUser(telegram_id=admin_id, role="matcher", is_active=True), parent, tutor])
    await db_session.commit()

    response = await async_client.post(
        f"/api/v1/admin/requests/{parent.id}/ping",
        json={"tutor_ids": [tutor.id]},
        headers=_telegram_auth_header(admin_id, bot_token),
    )

    assert response.status_code == 200
    assert "1 tutor" in response.json()["message"]
    assert mock_bot.send_message.await_count == 1
    invite = await db_session.scalar(select(MatchInvite).where(
        MatchInvite.request_id == parent.id, MatchInvite.tutor_id == tutor.id,
    ))
    assert invite.status == "sent"
    audit = await db_session.scalar(select(AuditLog).where(
        AuditLog.action == "ping_candidates", AuditLog.target_id == parent.id,
    ))
    assert audit is not None


@pytest.mark.asyncio
@pytest.mark.parametrize(("action", "expected_status", "audit_action"), [
    ("close", "closed", "close_request"),
    ("waitlist", "waitlisted", "waitlist_request"),
])
async def test_admin_request_terminal_actions_update_status_and_audit(
    action: str,
    expected_status: str,
    audit_action: str,
    async_client: AsyncClient,
    db_session: AsyncSession,
    monkeypatch,
):
    bot_token = "123456:admin-test-token"
    admin_id = 700010
    monkeypatch.setattr(settings, "BOT_TOKEN", bot_token)
    monkeypatch.setattr(settings, "SUPER_ADMIN_ID", None)
    monkeypatch.setattr(settings, "ALLOW_UNVERIFIED_WEB_PREVIEW", False)
    parent = _parent_request(f"{action.title()} Parent")
    db_session.add_all([AdminUser(telegram_id=admin_id, role="admin", is_active=True), parent])
    await db_session.commit()

    response = await async_client.post(
        f"/api/v1/admin/requests/{parent.id}/{action}",
        headers=_telegram_auth_header(admin_id, bot_token),
    )

    assert response.status_code == 200
    await db_session.refresh(parent)
    assert parent.status == expected_status
    audit = await db_session.scalar(select(AuditLog).where(
        AuditLog.target_id == parent.id, AuditLog.action == audit_action,
    ))
    assert audit is not None


@pytest.mark.asyncio
async def test_idle_tutor_list_and_reactivation_nudge(
    async_client: AsyncClient,
    db_session: AsyncSession,
    monkeypatch,
):
    bot_token = "123456:admin-test-token"
    admin_id = 700011
    monkeypatch.setattr(settings, "BOT_TOKEN", bot_token)
    monkeypatch.setattr(settings, "SUPER_ADMIN_ID", None)
    monkeypatch.setattr(settings, "ALLOW_UNVERIFIED_WEB_PREVIEW", False)
    import app.bot.bot_instance as bot_instance
    mock_bot = MagicMock()
    mock_bot.send_message = AsyncMock()
    monkeypatch.setattr(bot_instance, "bot_app", MagicMock(bot=mock_bot))
    tutor = _tutor("Idle Tutor", status="verified")
    tutor.telegram_user_id = 456124
    db_session.add_all([AdminUser(telegram_id=admin_id, role="admin", is_active=True), tutor])
    await db_session.commit()

    headers = _telegram_auth_header(admin_id, bot_token)
    idle_response = await async_client.get("/api/v1/admin/tutors/idle?days=14", headers=headers)
    assert idle_response.status_code == 200
    assert idle_response.json()[0]["full_name"] == "Idle Tutor"

    nudge_response = await async_client.post(
        f"/api/v1/admin/tutors/{tutor.id}/reactivate-nudge",
        headers=headers,
    )
    assert nudge_response.status_code == 200
    audit = await db_session.scalar(select(AuditLog).where(
        AuditLog.action == "reactivate_nudge", AuditLog.target_id == tutor.id,
    ))
    assert audit is not None


@pytest.mark.asyncio
async def test_admin_direct_assignment_without_prior_invite_succeeds(
    async_client: AsyncClient,
    db_session: AsyncSession,
    monkeypatch,
):
    """An administrator can directly assign any verified active tutor even without a prior ping."""
    bot_token = "123456:admin-test-token"
    admin_id = 700012
    monkeypatch.setattr(settings, "BOT_TOKEN", bot_token)
    monkeypatch.setattr(settings, "SUPER_ADMIN_ID", None)
    monkeypatch.setattr(settings, "ALLOW_UNVERIFIED_WEB_PREVIEW", False)
    import app.bot.bot_instance as bot_instance
    mock_bot = MagicMock()
    mock_bot.send_message = AsyncMock()
    monkeypatch.setattr(bot_instance, "bot_app", MagicMock(bot=mock_bot))

    parent = _parent_request("Direct Assign Parent")
    parent.telegram_user_id = 910001
    tutor = _tutor("Direct Assign Tutor", status="verified")
    tutor.telegram_user_id = 910002
    db_session.add_all([AdminUser(telegram_id=admin_id, role="admin", is_active=True), parent, tutor])
    await db_session.commit()

    # Note: No MatchInvite is pre-seeded
    response = await async_client.post(
        f"/api/v1/admin/requests/{parent.id}/assign",
        json={"tutor_id": tutor.id},
        headers=_telegram_auth_header(admin_id, bot_token),
    )
    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True

    # Verify MatchInvite was auto-recorded
    invite = await db_session.scalar(select(MatchInvite).where(
        MatchInvite.request_id == parent.id, MatchInvite.tutor_id == tutor.id
    ))
    assert invite is not None
    assert invite.status == "yes"

    # Verify Assignment was created
    assignment = await db_session.scalar(select(Assignment).where(Assignment.request_id == parent.id))
    assert assignment is not None
    assert assignment.tutor_id == tutor.id

    # Verify parent and tutor received DMs
    assert mock_bot.send_message.await_count == 2


def test_assignment_and_invite_relationships_are_database_foreign_keys():
    """Business records must not outlive the request or tutor they reference."""
    assignment_fks = {
        (fk.parent.name, fk.column.table.name, fk.column.name)
        for fk in Assignment.__table__.foreign_keys
    }
    invite_fks = {
        (fk.parent.name, fk.column.table.name, fk.column.name)
        for fk in MatchInvite.__table__.foreign_keys
    }

    assert ("request_id", "parent_requests", "id") in assignment_fks
    assert ("tutor_id", "tutors", "id") in assignment_fks
    assert ("request_id", "parent_requests", "id") in invite_fks
    assert ("tutor_id", "tutors", "id") in invite_fks


@pytest.mark.asyncio
async def test_admin_assignment_is_idempotently_rejected_after_request_is_matched(
    async_client: AsyncClient,
    db_session: AsyncSession,
    monkeypatch,
):
    bot_token = "123456:admin-test-token"
    admin_id = 700013
    monkeypatch.setattr(settings, "BOT_TOKEN", bot_token)
    monkeypatch.setattr(settings, "SUPER_ADMIN_ID", None)
    monkeypatch.setattr(settings, "ALLOW_UNVERIFIED_WEB_PREVIEW", False)

    parent = _parent_request("Already Assigned Parent", status="matched")
    tutor = _tutor("Already Assigned Tutor", status="verified")
    db_session.add_all([AdminUser(telegram_id=admin_id, role="admin", is_active=True), parent, tutor])
    await db_session.flush()
    db_session.add(Assignment(request_id=parent.id, tutor_id=tutor.id, status="active"))
    await db_session.commit()

    response = await async_client.post(
        f"/api/v1/admin/requests/{parent.id}/assign",
        json={"tutor_id": tutor.id},
        headers=_telegram_auth_header(admin_id, bot_token),
    )

    assert response.status_code == 409
    assignments = (
        await db_session.execute(
            select(Assignment).where(Assignment.request_id == parent.id)
        )
    ).scalars().all()
    assert len(assignments) == 1


def test_extracted_admin_analytics_router_is_registered():
    from app.main import app

    paths = {route.path for route in app.routes}
    assert "/api/v1/admin/analytics/funnel" in paths
    assert "/api/v1/admin/analytics/availability-mismatch" in paths
    assert "/api/v1/admin/analytics/coverage-gaps" in paths


def test_extracted_bot_modules_import_cleanly():
    from app.bot.formatters import _format_schedule, _format_subjects
    from app.services.bot_analytics import render_analytics_card

    assert _format_subjects(["Maths", "Physics"]) == "Maths, Physics"
    assert _format_schedule(["Monday", "Tuesday"]) == "Monday, Tuesday"
    assert callable(render_analytics_card)

@pytest.mark.asyncio
async def test_extracted_bot_analytics_uses_the_test_database(db_session: AsyncSession):
    from app.models import ParentRequest, Tutor
    from app.services.bot_analytics import render_analytics_card

    db_session.add(Tutor(
        full_name="Analytics Tutor", gender="female", phone_number="0911000000",
        university="Test University", department="Mathematics", education_year="2026",
        subjects_qualified=["Maths"], grades_qualified=["Grade 8"], years_of_experience=3,
        expected_fee_etb=500, base_subcity="Bole", coverage_areas=["Bole"],
        availability_schedule=["Monday"], status="verified", is_paused=False,
    ))
    db_session.add(ParentRequest(
        parent_name="Analytics Parent", phone_number="0911222222", student_level="Grade 8",
        subjects=["Maths"], preferred_gender="No preference", preferred_experience="Any",
        location_subcity="Bole", schedule_days=["Monday"], time_slot="17:00",
        session_duration="1 hour", budget_etb=600, status="pending",
    ))
    await db_session.commit()

    card = await render_analytics_card()

    assert "Analytics Tutor" not in card
    assert "1</code> Total" in card
    assert "500" in card
    assert "Bole (1)" in card