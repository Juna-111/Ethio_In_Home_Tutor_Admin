"""Session feedback collection via Telegram bot DM.

Phase 3: DMs a parent a 1–5 rating request N days after assignment,
and records the response as a SessionFeedback row.
"""
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode

from app.models import Assignment, ParentRequest, SessionFeedback, SystemSetting

logger = logging.getLogger("mentorlink.bot.feedback")

# Default days after assignment before requesting feedback
DEFAULT_FEEDBACK_DELAY_DAYS = 3


async def get_feedback_delay_days(session: AsyncSession) -> int:
    """Read configurable delay from SystemSetting, fallback to default."""
    setting = await session.get(SystemSetting, "feedback_delay_days")
    if setting:
        try:
            return max(1, int(setting.value))
        except (ValueError, TypeError) as exc:
            logger.warning("Invalid feedback_delay_days setting '%s': %s", setting.value, exc)
    return DEFAULT_FEEDBACK_DELAY_DAYS


async def record_feedback(
    assignment_id: int, rating: int, session: AsyncSession, comment: Optional[str] = None
) -> SessionFeedback:
    """Persist a parent's session rating. Idempotent per assignment."""
    existing = await session.scalar(
        select(SessionFeedback).where(SessionFeedback.assignment_id == assignment_id)
    )
    if existing:
        existing.rating = rating
        if comment is not None:
            existing.comment = comment
        await session.commit()
        return existing

    feedback = SessionFeedback(
        assignment_id=assignment_id,
        rating=max(1, min(5, rating)),
        comment=comment,
        submitted_by="parent",
    )
    session.add(feedback)
    await session.commit()
    return feedback


async def get_pending_feedback_assignments(session: AsyncSession) -> list[Assignment]:
    """Find active assignments past the feedback delay that have no feedback yet."""
    delay_days = await get_feedback_delay_days(session)
    cutoff = datetime.now(timezone.utc) - timedelta(days=delay_days)

    result = await session.execute(
        select(Assignment).where(
            Assignment.status == "active",
            Assignment.assigned_at <= cutoff,
            Assignment.id.not_in(
                select(SessionFeedback.assignment_id)
            ),
        )
    )
    return list(result.scalars().all())


def build_rating_keyboard(assignment_id: int) -> InlineKeyboardMarkup:
    """Build a 1–5 star inline keyboard for rating an assignment."""
    buttons = [
        InlineKeyboardButton(
            f"{'⭐' * i}", callback_data=f"rate_session:{assignment_id}:{i}"
        )
        for i in range(1, 6)
    ]
    return InlineKeyboardMarkup([buttons])


async def send_feedback_request(bot, assignment: Assignment, session: AsyncSession) -> bool:
    """Send a feedback DM to the parent for a given assignment.

    Returns True if the message was sent successfully.
    """
    parent = await session.get(ParentRequest, assignment.request_id)
    if not parent or not parent.telegram_user_id:
        logger.debug("No parent telegram_user_id for assignment %s", assignment.id)
        return False

    keyboard = build_rating_keyboard(assignment.id)
    text = (
        "<b>How was your tutoring session?</b>\n\n"
        "We'd love to hear your feedback! Please rate your recent "
        "tutoring experience on a scale of 1 to 5 stars."
    )
    try:
        await bot.send_message(
            chat_id=parent.telegram_user_id,
            text=text,
            parse_mode=ParseMode.HTML,
            reply_markup=keyboard,
        )
        return True
    except Exception as exc:
        logger.error(
            "Failed to send feedback request for assignment %s to parent %s: %s",
            assignment.id,
            parent.telegram_user_id,
            exc,
        )
        return False
