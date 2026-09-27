"""Durable, idempotent background scheduler service.

Runs scheduled checks (feedback collection, red-flag alerts, re-verification reminders,
and probation check-ins) protected by transactional event claiming to prevent duplicate
DMs or duplicate group alerts across multiple app instances or overlapping cron hits.
"""
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from telegram.constants import ParseMode

from app.bot.feedback import get_pending_feedback_assignments, send_feedback_request
from app.bot.topics import get_tutor_topic_id
from app.config import settings
from app.models import (
    Assignment,
    NotificationOutbox,
    ParentRequest,
    ScheduledEventClaim,
    SystemSetting,
    Tutor,
    TutorVerification,
)

logger = logging.getLogger("mentorlink.services.scheduler")


async def claim_event(
    db: AsyncSession,
    event_key: str,
    check_type: str,
    entity_type: str,
    entity_id: int,
) -> bool:
    """Transactionally claims an event occurrence.

    Returns True if this worker won the claim, False if already claimed.
    Uses nested transaction (savepoint) to gracefully handle concurrent race conditions.
    """
    existing = await db.scalar(
        select(ScheduledEventClaim).where(ScheduledEventClaim.event_key == event_key)
    )
    if existing:
        return False

    claim = ScheduledEventClaim(
        event_key=event_key,
        check_type=check_type,
        entity_type=entity_type,
        entity_id=entity_id,
    )
    db.add(claim)
    try:
        async with db.begin_nested():
            await db.flush()
        return True
    except Exception as exc:
        logger.debug("Event %s already claimed by another runner: %s", event_key, exc)
        return False


async def run_feedback_checks(db: AsyncSession, bot: Optional[Any] = None) -> int:
    """Finds active assignments requiring feedback, claims them, and enqueues outbox DMs."""
    assignments = await get_pending_feedback_assignments(db)
    claimed_count = 0

    for asmt in assignments:
        event_key = f"feedback_request:assignment:{asmt.id}"
        claimed = await claim_event(db, event_key, "feedback_request", "assignment", asmt.id)
        if not claimed:
            continue

        parent = await db.get(ParentRequest, asmt.request_id)
        recipient_id = parent.telegram_user_id if parent else None

        outbox = NotificationOutbox(
            event_key=event_key,
            target_type="feedback_dm",
            recipient_id=recipient_id,
            message_text=f"Session rating request for assignment #{asmt.id}.",
            status="pending",
        )
        db.add(outbox)
        claimed_count += 1

    await db.commit()
    return claimed_count


async def run_red_flag_checks(db: AsyncSession, bot: Optional[Any] = None) -> int:
    """Scans pending/verified tutors for anomalies and generates group alerts idempotently."""
    setting_thresh = await db.get(SystemSetting, "entrance_score_threshold")
    entrance_threshold = float(setting_thresh.value) if setting_thresh else 50.0

    setting_outlier = await db.get(SystemSetting, "fee_outlier_factor")
    fee_outlier_factor = float(setting_outlier.value) if setting_outlier else 2.0

    result = await db.execute(
        select(Tutor).where(Tutor.status.in_(["pending", "verified"]))
    )
    tutors = result.scalars().all()

    phone_map: dict[str, list[Tutor]] = {}
    exp_fees: dict[str, list[float]] = {}
    for t in tutors:
        phone_map.setdefault(t.phone_number, []).append(t)
        band = "0-1" if t.years_of_experience < 1 else ("1-3" if t.years_of_experience < 3 else "3+")
        exp_fees.setdefault(band, []).append(t.expected_fee_etb)

    band_avg = {band: sum(fees) / len(fees) for band, fees in exp_fees.items() if fees}

    claimed_count = 0
    topic_id = get_tutor_topic_id()

    for t in tutors:
        flags_to_check = []
        if not t.id_document_url:
            flags_to_check.append((
                f"red_flag:missing_document:tutor:{t.id}",
                "missing_document",
                "medium",
                "No ID document uploaded.",
            ))

        if t.entrance_result is not None and t.entrance_result < entrance_threshold:
            flags_to_check.append((
                f"red_flag:low_entrance_score:tutor:{t.id}",
                "low_entrance_score",
                "medium",
                f"Entrance score {t.entrance_result} is below threshold {entrance_threshold}.",
            ))

        if len(phone_map.get(t.phone_number, [])) > 1:
            other_ids = [o.id for o in phone_map[t.phone_number] if o.id != t.id]
            flags_to_check.append((
                f"red_flag:duplicate_phone:tutor:{t.id}",
                "duplicate_phone",
                "high",
                f"Phone {t.phone_number} shared with tutor(s) {other_ids}.",
            ))

        band = "0-1" if t.years_of_experience < 1 else ("1-3" if t.years_of_experience < 3 else "3+")
        avg = band_avg.get(band)
        if avg and t.expected_fee_etb > avg * fee_outlier_factor:
            flags_to_check.append((
                f"red_flag:fee_outlier:tutor:{t.id}",
                "fee_outlier",
                "low",
                f"Fee {t.expected_fee_etb:.0f} ETB exceeds {fee_outlier_factor}x band avg ({avg:.0f} ETB).",
            ))

        for event_key, flag_type, severity, detail in flags_to_check:
            claimed = await claim_event(db, event_key, "red_flag", "tutor", t.id)
            if not claimed:
                continue

            msg = (
                f"🚩 <b>Red Flag Alert [{severity.upper()}]</b>\n\n"
                f"Tutor: <b>{t.full_name}</b> (ID: {t.id})\n"
                f"Flag: <code>{flag_type}</code>\n"
                f"Detail: {detail}"
            )
            outbox = NotificationOutbox(
                event_key=event_key,
                target_type="admin_group",
                topic_id=topic_id,
                message_text=msg,
                status="pending",
            )
            db.add(outbox)
            claimed_count += 1

    await db.commit()
    return claimed_count


async def run_reverification_checks(db: AsyncSession, bot: Optional[Any] = None) -> int:
    """Reminds admins when verified tutors exceed the re-verification cadence."""
    setting = await db.get(SystemSetting, "reverification_interval_days")
    interval_days = int(setting.value) if setting else 90

    result = await db.execute(
        select(Tutor).where(Tutor.status == "verified")
    )
    tutors = result.scalars().all()
    now = datetime.now(timezone.utc)
    claimed_count = 0
    topic_id = get_tutor_topic_id()

    for t in tutors:
        verification = await db.get(TutorVerification, t.id)
        base_time = None
        if verification and verification.last_verified_at:
            base_time = verification.last_verified_at
        elif t.created_at:
            base_time = t.created_at

        if not base_time:
            continue

        if base_time.tzinfo is None:
            base_time = base_time.replace(tzinfo=timezone.utc)

        age = now - base_time
        if age >= timedelta(days=interval_days):
            cycle = max(1, int(age.total_seconds() // (interval_days * 86400)))
            event_key = f"reverification:tutor:{t.id}:cycle_{cycle}"
            claimed = await claim_event(db, event_key, "reverification", "tutor", t.id)
            if not claimed:
                continue

            last_date_str = base_time.strftime("%Y-%m-%d")
            msg = (
                f"🔄 <b>Re-Verification Due</b>\n\n"
                f"Tutor <b>{t.full_name}</b> (ID: {t.id}) was last verified on {last_date_str}.\n"
                f"Cadence cycle: {cycle}. Please re-verify credentials in the Admin Mini App."
            )
            outbox = NotificationOutbox(
                event_key=event_key,
                target_type="admin_group",
                topic_id=topic_id,
                message_text=msg,
                status="pending",
            )
            db.add(outbox)
            claimed_count += 1

    await db.commit()
    return claimed_count


async def run_probation_checks(db: AsyncSession, bot: Optional[Any] = None) -> int:
    """Reminds admins to monitor active assignments for tutors placed on probation."""
    setting = await db.get(SystemSetting, "probation_reminder_days")
    interval_days = int(setting.value) if setting else 7

    result = await db.execute(
        select(Tutor).where(Tutor.status == "probation")
    )
    tutors = result.scalars().all()
    now = datetime.now(timezone.utc)
    claimed_count = 0
    topic_id = get_tutor_topic_id()

    for t in tutors:
        asmt_res = await db.execute(
            select(Assignment).where(
                Assignment.tutor_id == t.id,
                Assignment.status == "active",
            )
        )
        active_asmts = asmt_res.scalars().all()
        for asmt in active_asmts:
            assigned_time = asmt.assigned_at
            if assigned_time.tzinfo is None:
                assigned_time = assigned_time.replace(tzinfo=timezone.utc)

            age = now - assigned_time
            if age >= timedelta(days=interval_days):
                cycle = max(1, int(age.total_seconds() // (interval_days * 86400)))
                event_key = f"probation_reminder:tutor:{t.id}:assignment:{asmt.id}:cycle_{cycle}"
                claimed = await claim_event(db, event_key, "probation", "tutor", t.id)
                if not claimed:
                    continue

                msg = (
                    f"⚠️ <b>Probation Check-in Reminder</b>\n\n"
                    f"Tutor <b>{t.full_name}</b> (ID: {t.id}) is currently on <b>probation</b> "
                    f"with active assignment #{asmt.id}.\n"
                    f"Please follow up with parent/tutor to ensure quality."
                )
                outbox = NotificationOutbox(
                    event_key=event_key,
                    target_type="admin_group",
                    topic_id=topic_id,
                    message_text=msg,
                    status="pending",
                )
                db.add(outbox)
                claimed_count += 1

    await db.commit()
    return claimed_count


async def drain_notification_outbox(db: AsyncSession, bot: Optional[Any] = None) -> int:
    """Drains pending notifications from the outbox table via the Telegram bot instance."""
    result = await db.execute(
        select(NotificationOutbox).where(NotificationOutbox.status == "pending")
    )
    pending_items = result.scalars().all()
    sent_count = 0

    if not pending_items:
        return 0

    for item in pending_items:
        if not bot:
            continue

        try:
            if item.target_type == "admin_group":
                chat_id = settings.ADMIN_GROUP_ID
                if chat_id or getattr(bot, "is_mock", False):
                    await bot.send_message(
                        chat_id=chat_id,
                        text=item.message_text,
                        message_thread_id=item.topic_id or get_tutor_topic_id(),
                        parse_mode=ParseMode.HTML,
                    )
                    item.status = "sent"
                    item.sent_at = datetime.now(timezone.utc)
                    sent_count += 1
            elif item.target_type == "feedback_dm":
                if item.event_key.startswith("feedback_request:assignment:"):
                    asmt_id = int(item.event_key.split(":")[-1])
                    asmt = await db.get(Assignment, asmt_id)
                    if asmt:
                        ok = await send_feedback_request(bot, asmt, db)
                        if ok:
                            item.status = "sent"
                            item.sent_at = datetime.now(timezone.utc)
                            sent_count += 1
                        else:
                            item.status = "failed"
                            item.error_message = "send_feedback_request returned False"
                    else:
                        item.status = "failed"
                        item.error_message = f"Assignment {asmt_id} not found"
                elif item.recipient_id:
                    await bot.send_message(
                        chat_id=item.recipient_id,
                        text=item.message_text,
                        parse_mode=ParseMode.HTML,
                    )
                    item.status = "sent"
                    item.sent_at = datetime.now(timezone.utc)
                    sent_count += 1
            elif item.target_type == "dm" and item.recipient_id:
                await bot.send_message(
                    chat_id=item.recipient_id,
                    text=item.message_text,
                    parse_mode=ParseMode.HTML,
                )
                item.status = "sent"
                item.sent_at = datetime.now(timezone.utc)
                sent_count += 1
        except Exception as exc:
            logger.error("Failed to drain outbox item %s: %s", item.id, exc)
            item.status = "failed"
            item.error_message = str(exc)

    await db.commit()
    return sent_count


async def run_all_scheduled_tasks(db: AsyncSession, bot: Optional[Any] = None) -> dict[str, Any]:
    """Master runner invoked by the cron endpoint or periodic runner."""
    feedback_checked = await run_feedback_checks(db, bot)
    red_flags_checked = await run_red_flag_checks(db, bot)
    reverification_checked = await run_reverification_checks(db, bot)
    probation_checked = await run_probation_checks(db, bot)
    outbox_drained = await drain_notification_outbox(db, bot)

    return {
        "feedback_checked": feedback_checked,
        "red_flags_checked": red_flags_checked,
        "reverification_checked": reverification_checked,
        "probation_checked": probation_checked,
        "outbox_drained": outbox_drained,
    }
