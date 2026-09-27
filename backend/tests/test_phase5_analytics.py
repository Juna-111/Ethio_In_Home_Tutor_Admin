"""Phase 5 — Analytics, Ops, and Scheduler Tests.

Covers:
1. Funnel analytics consistency: started >= submitted >= approved, rates between 0 and 1.
2. Schedule availability mismatch cross-tabulation.
3. Byte-for-byte CSV export parity with export_service.py.
4. Waitlist auto-backfill alert on tutor verification approval.
5. Durable, idempotent cron event claiming and recurring reminders.
6. Cron endpoint authentication (CRON_SECRET and Admin principal).
"""
import hashlib
import hmac
import io
import json
import time
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import (
    AdminUser,
    Assignment,
    AuditLog,
    NotificationOutbox,
    ParentRequest,
    RegistrationFunnelEvent,
    ScheduledEventClaim,
    SystemSetting,
    Tutor,
    TutorVerification,
)
from app.services.export_service import generate_parents_csv, generate_tutors_csv
from app.services.scheduler import (
    claim_event,
    run_all_scheduled_tasks,
    run_feedback_checks,
    run_probation_checks,
    run_red_flag_checks,
    run_reverification_checks,
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


async def _create_admin(db: AsyncSession, tg_id: int = 99901, role: str = "super_admin") -> AdminUser:
    admin = AdminUser(telegram_id=tg_id, role=role, is_active=True)
    db.add(admin)
    await db.commit()
    return admin


# ---------------------------------------------------------------------------
# Test 1: Funnel Analytics
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_funnel_counts_consistency(async_client: AsyncClient, db_session: AsyncSession, monkeypatch):
    bot_token = settings.BOT_TOKEN or "test_token"
    monkeypatch.setattr(settings, "BOT_TOKEN", bot_token)
    admin = await _create_admin(db_session, 99911, "super_admin")
    headers = _telegram_auth_header(admin.telegram_id, bot_token)

    # 1. Start 3 funnels via public endpoint
    for sid in ["sess_1", "sess_2", "sess_3"]:
        res = await async_client.post("/api/v1/tutors/funnel/start", json={"session_id": sid})
        assert res.status_code == 201
        assert res.json()["ok"] is True

    # 2. Add 2 tutors (1 verified, 1 pending)
    t1 = Tutor(
        full_name="Tutor Verified",
        gender="Male",
        phone_number="+251911111111",
        university="AAU",
        department="Math",
        education_year="4th Year",
        subjects_qualified=["Maths"],
        grades_qualified=["Grade 9-12"],
        years_of_experience=3.0,
        expected_fee_etb=400.0,
        base_subcity="Bole",
        coverage_areas=["Bole"],
        availability_schedule="Morning",
        status="verified",
    )
    t2 = Tutor(
        full_name="Tutor Pending",
        gender="Female",
        phone_number="+251911111112",
        university="AAU",
        department="Physics",
        education_year="3rd Year",
        subjects_qualified=["Physics"],
        grades_qualified=["Grade 9-12"],
        years_of_experience=1.5,
        expected_fee_etb=350.0,
        base_subcity="Yeka",
        coverage_areas=["Yeka"],
        availability_schedule="Evening",
        status="pending",
    )
    db_session.add_all([t1, t2])
    await db_session.commit()

    # 3. Query funnel analytics
    res = await async_client.get("/api/v1/admin/analytics/funnel", headers=headers)
    assert res.status_code == 200
    data = res.json()

    assert data["started"] >= data["submitted"]
    assert data["submitted"] >= data["approved"]
    assert data["started"] >= 3
    assert data["submitted"] >= 2
    assert data["approved"] == 1
    assert 0.0 <= data["submission_rate"] <= 1.0
    assert 0.0 <= data["approval_rate"] <= 1.0


# ---------------------------------------------------------------------------
# Test 2: Availability Mismatch Cross-Tabulation
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_availability_mismatch(async_client: AsyncClient, db_session: AsyncSession, monkeypatch):
    bot_token = settings.BOT_TOKEN or "test_token"
    monkeypatch.setattr(settings, "BOT_TOKEN", bot_token)
    admin = await _create_admin(db_session, 99912, "super_admin")
    headers = _telegram_auth_header(admin.telegram_id, bot_token)

    # 3 Morning parent requests
    for i in range(3):
        req = ParentRequest(
            parent_name=f"Parent {i}",
            phone_number=f"+25192200000{i}",
            location_subcity="Bole",
            student_level="Grade 10",
            subjects=["Maths"],
            schedule_days=["Mon", "Wed"],
            time_slot="Morning (8:00 - 12:00)",
            session_duration="1.5 hours",
            budget_etb=350.0,
            preferred_gender="Any",
            status="pending",
        )
        db_session.add(req)

    # 1 Morning tutor, 2 Evening tutors
    t1 = Tutor(
        full_name="Morning Tutor",
        gender="Male",
        phone_number="+251911222221",
        university="AAU",
        department="Math",
        education_year="Graduate",
        subjects_qualified=["Maths"],
        grades_qualified=["Grade 9-12"],
        years_of_experience=4.0,
        expected_fee_etb=400.0,
        base_subcity="Bole",
        coverage_areas=["Bole"],
        availability_schedule="Morning slots only",
        status="verified",
    )
    t2 = Tutor(
        full_name="Evening Tutor 1",
        gender="Female",
        phone_number="+251911222222",
        university="AAU",
        department="Chemistry",
        education_year="4th Year",
        subjects_qualified=["Chemistry"],
        grades_qualified=["Grade 9-12"],
        years_of_experience=2.0,
        expected_fee_etb=300.0,
        base_subcity="Bole",
        coverage_areas=["Bole"],
        availability_schedule="Evening (4:00 - 8:00)",
        status="verified",
    )
    t3 = Tutor(
        full_name="Evening Tutor 2",
        gender="Male",
        phone_number="+251911222223",
        university="AAU",
        department="Biology",
        education_year="3rd Year",
        subjects_qualified=["Biology"],
        grades_qualified=["Grade 9-12"],
        years_of_experience=1.0,
        expected_fee_etb=250.0,
        base_subcity="Bole",
        coverage_areas=["Bole"],
        availability_schedule="Evening",
        status="pending",
    )
    db_session.add_all([t1, t2, t3])
    await db_session.commit()

    res = await async_client.get("/api/v1/admin/analytics/availability-mismatch", headers=headers)
    assert res.status_code == 200
    data = res.json()

    assert data["total_demand"] == 3
    assert data["total_supply"] == 3

    items_by_slot = {item["slot"]: item for item in data["items"]}
    morning = items_by_slot["Morning"]
    assert morning["demand"] == 3
    assert morning["supply"] == 1
    assert morning["gap"] == 2
    assert morning["mismatch_ratio"] > 0.5

    evening = items_by_slot["Evening"]
    assert evening["demand"] == 0
    assert evening["supply"] == 2
    assert evening["gap"] == 0


# ---------------------------------------------------------------------------
# Test 3: CSV Export Byte-for-Byte Parity
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_csv_export_byte_for_byte_parity(async_client: AsyncClient, db_session: AsyncSession, monkeypatch):
    bot_token = settings.BOT_TOKEN or "test_token"
    monkeypatch.setattr(settings, "BOT_TOKEN", bot_token)
    admin = await _create_admin(db_session, 99913, "super_admin")
    headers = _telegram_auth_header(admin.telegram_id, bot_token)

    # Seed data
    t = Tutor(
        full_name="Export Tutor Abebe",
        gender="Male",
        phone_number="+251911333333",
        university="AAU",
        department="Physics",
        education_year="4th Year",
        subjects_qualified=["Physics", "Maths"],
        grades_qualified=["Grade 9-12"],
        years_of_experience=2.5,
        expected_fee_etb=350.0,
        base_subcity="Kirkos",
        coverage_areas=["Kirkos", "Bole"],
        availability_schedule="Weekends",
        status="verified",
    )
    p = ParentRequest(
        parent_name="Parent Aster",
        phone_number="+251922333333",
        location_subcity="Kirkos",
        location_landmark="Near Stadium",
        student_level="Grade 11",
        subjects=["Physics"],
        schedule_days=["Sat", "Sun"],
        time_slot="Morning",
        session_duration="1.5 hours",
        budget_etb=350.0,
        preferred_gender="Male",
        status="pending",
    )
    db_session.add_all([t, p])
    await db_session.commit()

    # 1. Compare Tutors CSV
    expected_tutors_buf, _ = await generate_tutors_csv(db_session)
    expected_tutors_bytes = expected_tutors_buf.getvalue()

    res_tutors = await async_client.get("/api/v1/admin/export?type=tutors", headers=headers)
    assert res_tutors.status_code == 200
    assert res_tutors.headers["content-type"].startswith("text/csv")
    assert res_tutors.content == expected_tutors_bytes

    # 2. Compare Parents CSV
    expected_parents_buf, _ = await generate_parents_csv(db_session)
    expected_parents_bytes = expected_parents_buf.getvalue()

    res_parents = await async_client.get("/api/v1/admin/export?type=parents", headers=headers)
    assert res_parents.status_code == 200
    assert res_parents.headers["content-type"].startswith("text/csv")
    assert res_parents.content == expected_parents_bytes


# ---------------------------------------------------------------------------
# Test 4: Waitlist Auto-Backfill Alert on Tutor Approval
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_waitlist_auto_backfill_alert_on_tutor_approval(
    async_client: AsyncClient, db_session: AsyncSession, monkeypatch
):
    bot_token = settings.BOT_TOKEN or "test_token"
    monkeypatch.setattr(settings, "BOT_TOKEN", bot_token)
    admin = await _create_admin(db_session, 99914, "verifier")
    headers = _telegram_auth_header(admin.telegram_id, bot_token)

    # 1. Create a waitlisted parent request for "Chemistry"
    req = ParentRequest(
        parent_name="Waitlisted Parent",
        phone_number="+251922444444",
        location_subcity="Bole",
        student_level="Grade 12",
        subjects=["Chemistry"],
        schedule_days=["Tue", "Thu"],
        time_slot="Evening",
        session_duration="1.5 hours",
        budget_etb=400.0,
        preferred_gender="Any",
        status="waitlisted",
    )
    # 2. Create pending tutor offering "Chemistry"
    tutor = Tutor(
        full_name="Waitlist Solver",
        gender="Female",
        phone_number="+251911444444",
        university="AAU",
        department="Chemistry",
        education_year="Graduate",
        subjects_qualified=["Chemistry"],
        grades_qualified=["Grade 9-12"],
        years_of_experience=5.0,
        expected_fee_etb=400.0,
        base_subcity="Bole",
        coverage_areas=["Bole"],
        availability_schedule="Evening",
        status="pending",
    )
    db_session.add_all([req, tutor])
    await db_session.commit()
    await db_session.refresh(tutor)

    # 3. Approve tutor via verification checklist
    patch_payload = {
        "id_verified": True,
        "entrance_result_verified": True,
        "phone_confirmed": True,
        "claims_plausible": True,
    }
    res = await async_client.patch(
        f"/api/v1/admin/tutors/{tutor.id}/verification",
        json=patch_payload,
        headers=headers,
    )
    assert res.status_code == 200
    assert res.json()["all_complete"] is True
    assert res.json()["tutor_status"] == "verified"

    # 4. Verify waitlist match outbox alert was created
    outbox_res = await db_session.execute(
        select(NotificationOutbox).where(
            NotificationOutbox.event_key.like(f"waitlist_backfill:tutor:{tutor.id}:%")
        )
    )
    outbox_item = outbox_res.scalar_one_or_none()
    assert outbox_item is not None
    assert "Waitlist Match Found" in outbox_item.message_text
    assert "1" in outbox_item.message_text  # matches 1 request


# ---------------------------------------------------------------------------
# Test 5: Durable Idempotent Claiming and Reminders
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_cron_durable_claiming_and_reminders(db_session: AsyncSession):
    now = datetime.now(timezone.utc)
    old_date = now - timedelta(days=120)

    # 1. Assignment needing feedback (assigned 10 days ago)
    parent = ParentRequest(
        parent_name="Parent Feedback",
        phone_number="+251922555555",
        telegram_user_id=888888,
        location_subcity="Bole",
        student_level="Grade 10",
        subjects=["English"],
        schedule_days=["Mon"],
        time_slot="Morning",
        session_duration="1.5 hours",
        budget_etb=300.0,
        preferred_gender="Any",
        status="active",
    )
    db_session.add(parent)
    await db_session.flush()

    tutor = Tutor(
        full_name="Probation Tutor",
        gender="Male",
        phone_number="+251911555555",
        university="AAU",
        department="English",
        education_year="3rd Year",
        subjects_qualified=["English"],
        grades_qualified=["Grade 9-12"],
        years_of_experience=1.0,
        expected_fee_etb=300.0,
        base_subcity="Bole",
        coverage_areas=["Bole"],
        availability_schedule="Morning",
        status="probation",
    )
    db_session.add(tutor)
    await db_session.flush()

    asmt = Assignment(
        request_id=parent.id,
        tutor_id=tutor.id,
        assigned_by="system",
        assigned_at=now - timedelta(days=10),
        status="active",
    )
    db_session.add(asmt)

    # 2. Verified tutor needing re-verification (>90 days old)
    reverify_tutor = Tutor(
        full_name="Needs Reverify",
        gender="Female",
        phone_number="+251911666666",
        university="AAU",
        department="History",
        education_year="Graduate",
        subjects_qualified=["History"],
        grades_qualified=["Grade 9-12"],
        years_of_experience=4.0,
        expected_fee_etb=350.0,
        base_subcity="Arada",
        coverage_areas=["Arada"],
        availability_schedule="Flexible",
        status="verified",
        created_at=old_date,
    )
    db_session.add(reverify_tutor)
    await db_session.flush()

    verification = TutorVerification(
        tutor_id=reverify_tutor.id,
        id_verified=True,
        entrance_result_verified=True,
        phone_confirmed=True,
        claims_plausible=True,
        last_verified_at=old_date,
    )
    db_session.add(verification)
    await db_session.commit()

    # FIRST RUN: Should claim tasks and queue notifications
    res1 = await run_all_scheduled_tasks(db_session, bot=None)
    assert res1["feedback_checked"] >= 1
    assert res1["reverification_checked"] >= 1
    assert res1["probation_checked"] >= 1

    # Count claims and outbox rows
    claims_count = (await db_session.execute(select(ScheduledEventClaim))).scalars().all()
    outbox_count = (await db_session.execute(select(NotificationOutbox))).scalars().all()
    assert len(claims_count) >= 3
    assert len(outbox_count) >= 3

    # SECOND RUN: Must be 100% idempotent — 0 new claims
    res2 = await run_all_scheduled_tasks(db_session, bot=None)
    assert res2["feedback_checked"] == 0
    assert res2["reverification_checked"] == 0
    assert res2["probation_checked"] == 0

    # Ensure concurrent duplicate claim simulation returns False
    key = f"feedback_request:assignment:{asmt.id}"
    duplicate_claim = await claim_event(db_session, key, "feedback_request", "assignment", asmt.id)
    assert duplicate_claim is False


# ---------------------------------------------------------------------------
# Test 6: Cron Endpoint Authentication
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_cron_endpoint_auth(async_client: AsyncClient, db_session: AsyncSession, monkeypatch):
    secret = "test_cron_secret_key_123"
    monkeypatch.setattr(settings, "CRON_SECRET", secret)
    monkeypatch.setattr(settings, "ALLOW_UNVERIFIED_WEB_PREVIEW", False)

    # 1. Unauthenticated request -> 401
    res_no_auth = await async_client.post("/api/v1/admin/cron/run")
    assert res_no_auth.status_code == 401

    # 2. Invalid secret -> 401
    res_bad_secret = await async_client.post(
        "/api/v1/admin/cron/run",
        headers={"X-Cron-Secret": "wrong_secret"},
    )
    assert res_bad_secret.status_code == 401

    # 3. Valid X-Cron-Secret header -> 200
    res_good_secret = await async_client.post(
        "/api/v1/admin/cron/run",
        headers={"X-Cron-Secret": secret},
    )
    assert res_good_secret.status_code == 200
    assert res_good_secret.json()["ok"] is True
    assert "result" in res_good_secret.json()

    # 4. Valid Authorization Bearer header -> 200
    res_bearer = await async_client.post(
        "/api/v1/admin/cron/run",
        headers={"Authorization": f"Bearer {secret}"},
    )
    assert res_bearer.status_code == 200
    assert res_bearer.json()["ok"] is True
