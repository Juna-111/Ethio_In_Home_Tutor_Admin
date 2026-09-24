import html
import logging
import re
from typing import Optional

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import Application, ApplicationBuilder

from app.bot.topics import get_parent_topic_id, get_tutor_topic_id
from app.config import settings

logger = logging.getLogger("mentorlink.bot")

bot_app: Optional[Application] = None


async def init_bot_app() -> Optional[Application]:
    """
    Initializes the python-telegram-bot Application instance during FastAPI startup.
    Gracefully handles missing or invalid tokens so backend startup never fails.
    """
    global bot_app

    token = settings.BOT_TOKEN
    if not token or token.strip() in ("", "your_bot_token", "your_bot_token_here"):
        logger.info("BOT_TOKEN is not configured. Telegram bot forwarding will be disabled.")
        return None

    try:
        from app.bot.handlers import register_handlers

        application = ApplicationBuilder().token(token.strip()).build()
        register_handlers(application)

        await application.initialize()
        await application.start()

        if application.updater:
            await application.updater.start_polling(drop_pending_updates=True)

        bot_app = application
        logger.info("Telegram Bot Application successfully initialized and polling started.")
        return bot_app
    except Exception as exc:
        logger.error("Failed to initialize Telegram Bot: %s", exc, exc_info=True)
        bot_app = None
        return None


async def shutdown_bot_app() -> None:
    """Shuts down the Telegram bot polling and application cleanly."""
    global bot_app
    if bot_app:
        try:
            if bot_app.updater and bot_app.updater.running:
                await bot_app.updater.stop()
            if bot_app.running:
                await bot_app.stop()
            await bot_app.shutdown()
            logger.info("Telegram Bot Application shut down cleanly.")
        except Exception as exc:
            logger.error("Error during Telegram Bot shutdown: %s", exc)
        finally:
            bot_app = None


def format_subjects(subjects) -> str:
    if isinstance(subjects, list):
        return ", ".join(html.escape(str(s)) for s in subjects)
    return html.escape(str(subjects))


def format_schedule(schedule) -> str:
    if isinstance(schedule, list):
        return ", ".join(html.escape(str(s)) for s in schedule)
    elif isinstance(schedule, dict):
        return ", ".join(f"{html.escape(str(k))}: {html.escape(str(v))}" for k, v in schedule.items())
    return html.escape(str(schedule))


def format_parent_card(parent_req, status_override: Optional[str] = None) -> str:
    """Renders the Blockquote Terminal Data Card for a parent tutoring request."""
    header_status = status_override or "🟡 <b>Pending</b>"
    tg_id_str = str(parent_req.telegram_user_id) if parent_req.telegram_user_id else "N/A"
    landmark_part = f" ({html.escape(parent_req.location_landmark)})" if parent_req.location_landmark else ""
    timing_str = f"{format_schedule(parent_req.schedule_days)} ({html.escape(parent_req.time_slot)}, {html.escape(parent_req.session_duration)})"
    subjects_str = format_subjects(parent_req.subjects)

    return (
        f"📋 <b>PARENT REQUEST #{parent_req.id:04d}</b> • {header_status}\n\n"
        f"<blockquote><b>Parent:</b> {html.escape(parent_req.parent_name)}\n"
        f"<b>Contact:</b> <code>{html.escape(parent_req.phone_number)}</code> (TG: <code>{tg_id_str}</code>)\n"
        f"<b>Location:</b> {html.escape(parent_req.location_subcity)}{landmark_part}\n"
        f"<b>Student:</b> {html.escape(parent_req.student_level)} │ <b>Subjects:</b> {subjects_str}\n"
        f"<b>Timing:</b> {timing_str}\n"
        f"<b>Budget:</b> {parent_req.budget_etb:,.2f} ETB/hr │ <b>Pref:</b> {html.escape(parent_req.preferred_gender)} ({html.escape(parent_req.preferred_experience)})</blockquote>"
    )


def format_parent_directory_badge(parent_req) -> str:
    """Renders the compact badge for the main Directory Index Topic ('📥 Parent Requests')."""
    subjects_str = format_subjects(parent_req.subjects)
    schedule_str = format_schedule(parent_req.schedule_days)
    return (
        f"🎫 <b>REQ-{parent_req.id:04d}</b> ── {html.escape(parent_req.student_level)} ({subjects_str})\n"
        f"👤 <b>{html.escape(parent_req.parent_name)}</b> • {html.escape(parent_req.location_subcity)}\n"
        f"⏰ {schedule_str} • 💰 {parent_req.budget_etb:,.2f} ETB/hr"
    )


def format_tutor_card(tutor, status_override: Optional[str] = None, admin_username: Optional[str] = None) -> str:
    """Renders the Blockquote Terminal Data Card for a tutor profile with optional status override."""
    if tutor.id_document_url:
        parts = [p.strip() for p in tutor.id_document_url.split(" | ") if p.strip()]
        links = []
        for idx, part in enumerate(parts):
            if part.startswith("/uploads/"):
                base = settings.WEBAPP_URL.rstrip("/") if settings.WEBAPP_URL else ""
                href = f"{base}{part}"
                links.append(f'<a href="{html.escape(href)}">📎 Uploaded Doc</a>')
            elif part.startswith("http"):
                label = "🌐 Portfolio/URL" if len(parts) > 1 and idx > 0 else "📄 View Document"
                links.append(f'<a href="{html.escape(part)}">{label}</a>')
            else:
                links.append(f'<a href="{html.escape(part)}">📄 Doc</a>')
        doc_display = " │ ".join(links)
    else:
        doc_display = "Not provided"

    tg_id_str = str(tutor.telegram_user_id) if tutor.telegram_user_id else "N/A"
    header_status = status_override or "🟡 <b>Pending Verification</b>"

    if admin_username:
        clean_user = admin_username.lstrip("@")
        admin_line = f"Admin: @{clean_user}"
    elif status_override and "by @" in status_override:
        match = re.search(r"by (@\w+)", status_override)
        admin_line = f"Admin: {match.group(1)}" if match else "Admin: Pending"
    elif status_override and "by " in status_override:
        admin_part = status_override.split("by ")[-1].replace("</b>", "").strip()
        admin_line = f"Admin: @{admin_part.lstrip('@')}" if admin_part else "Admin: Pending"
    else:
        admin_line = "Admin: Pending"

    coverage_areas = tutor.coverage_areas if isinstance(tutor.coverage_areas, list) else [str(tutor.coverage_areas)]
    if len(coverage_areas) > 2:
        coverage_summary = f"+{len(coverage_areas) - 1} Sub-cities"
    else:
        coverage_summary = ", ".join(html.escape(str(c)) for c in coverage_areas)

    years_exp = f"{tutor.years_of_experience:g}"
    timing_str = format_schedule(tutor.availability_schedule)
    subjects_str = format_subjects(tutor.subjects_qualified)
    grades_str = format_subjects(tutor.grades_qualified)

    return (
        f"🧑‍🏫 <b>TUTOR TICKET #{tutor.id:04d}</b> • {header_status}\n"
        f"{admin_line}\n\n"
        f"<blockquote><b>Candidate:</b> {html.escape(tutor.full_name)} ({html.escape(tutor.gender)})\n"
        f"<b>Contact:</b> <code>{html.escape(tutor.phone_number)}</code> (TG: <code>{tg_id_str}</code>)\n"
        f"<b>Uni/Major:</b> {html.escape(tutor.university)} • {html.escape(tutor.department)} ({html.escape(tutor.education_year)})\n"
        f"<b>Fee & Exp:</b> {tutor.expected_fee_etb:,.2f} ETB/hr │ {years_exp} yrs exp\n\n"
        f"<b>Teaches:</b> {subjects_str}\n"
        f"<b>Level:</b> {grades_str}\n"
        f"<b>Territory:</b> Base {html.escape(tutor.base_subcity)} ({coverage_summary})\n"
        f"<b>Timing:</b> {timing_str}</blockquote>\n\n"
        f"🔗 <b>Credentials:</b> {doc_display}"
    )


from sqlalchemy.ext.asyncio import AsyncSession
from app.database import AsyncSessionLocal
from app.models import ParentRequest


def get_clean_chat_id(chat_id: int | str) -> str:
    """Extracts the clean numerical ID from Telegram -100 supergroup format for web deep links."""
    raw = str(chat_id).strip()
    if raw.startswith("-100"):
        return raw[4:]
    elif raw.startswith("-"):
        return raw[1:]
    return raw


async def send_parent_request_card(parent_req, db_session: Optional[AsyncSession] = None) -> Optional[int]:
    """
    Sends parent request notification cards to ADMIN_GROUP_ID:
    1. Dynamically creates a dedicated forum topic: `REQ-{id:04d} — {parent_name} ({location_subcity})` (max 128 chars)
    2. Sends the full management card with [ 🔍 Match Radar ] and [ ❌ Close Request ] inside the dedicated topic.
    3. Posts an index ticket link with [ 🔗 Open Ticket ] into the Parent Requests Directory Topic.
    Fallback: If forum topics are not supported or creation fails, posts directly to the parent index topic.
    """
    if not bot_app or not settings.ADMIN_GROUP_ID:
        logger.debug("Bot or ADMIN_GROUP_ID not configured; skipping parent notification.")
        return None

    try:
        topic = None
        if hasattr(bot_app.bot, "create_forum_topic"):
            try:
                prefix = f"REQ-{parent_req.id:04d} — "
                subcity_part = f" ({parent_req.location_subcity})" if parent_req.location_subcity else ""
                max_name_len = 128 - len(prefix) - len(subcity_part)
                name_clean = parent_req.parent_name or "Parent"
                name_part = name_clean[:max_name_len] if max_name_len > 5 else name_clean[:20]
                topic_name = f"{prefix}{name_part}{subcity_part}"[:128]

                topic = await bot_app.bot.create_forum_topic(
                    chat_id=settings.ADMIN_GROUP_ID,
                    name=topic_name
                )
                parent_req.telegram_topic_id = topic.message_thread_id
                if db_session:
                    await db_session.commit()
                else:
                    async with AsyncSessionLocal() as session:
                        p = await session.get(ParentRequest, parent_req.id)
                        if p:
                            p.telegram_topic_id = topic.message_thread_id
                            await session.commit()
            except Exception as exc:
                logger.warning("Could not create dedicated forum topic for REQ-%04d: %s", parent_req.id, exc)
                topic = None

        card_text = format_parent_card(parent_req)
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("🔍 Match Radar", callback_data=f"match_parent:{parent_req.id}"),
                InlineKeyboardButton("❌ Close Request", callback_data=f"close_parent:{parent_req.id}")
            ]
        ])

        parent_index_topic_id = get_parent_topic_id()

        if topic and topic.message_thread_id:
            # 1. Post full management card inside dedicated ticket topic
            card_msg = await bot_app.bot.send_message(
                chat_id=settings.ADMIN_GROUP_ID,
                text=card_text,
                parse_mode=ParseMode.HTML,
                reply_markup=keyboard,
                message_thread_id=topic.message_thread_id
            )

            # 2. Post Ticket Notification to the Index Topic ("📥 Parent Requests")
            clean_id = get_clean_chat_id(settings.ADMIN_GROUP_ID)
            topic_url = f"https://t.me/c/{clean_id}/{topic.message_thread_id}"

            index_text = format_parent_directory_badge(parent_req)
            index_keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("🔗 Open Workspace / Ticket ↗️", url=topic_url)]
            ])

            index_kwargs = {
                "chat_id": settings.ADMIN_GROUP_ID,
                "text": index_text,
                "parse_mode": ParseMode.HTML,
                "reply_markup": index_keyboard
            }
            if parent_index_topic_id is not None:
                index_kwargs["message_thread_id"] = parent_index_topic_id

            await bot_app.bot.send_message(**index_kwargs)
            return card_msg.message_id
        else:
            # Fallback for non-forum groups or if topic creation failed
            send_kwargs = {
                "chat_id": settings.ADMIN_GROUP_ID,
                "text": card_text,
                "parse_mode": ParseMode.HTML,
                "reply_markup": keyboard
            }
            if parent_index_topic_id is not None:
                send_kwargs["message_thread_id"] = parent_index_topic_id

            msg = await bot_app.bot.send_message(**send_kwargs)
            return msg.message_id

    except Exception as exc:
        logger.error("Failed to forward parent request #%s to Admin Group: %s", parent_req.id, exc)
        return None


async def send_tutor_registration_card(tutor) -> Optional[int]:
    """
    Sends a compact formatted tutor verification card to ADMIN_GROUP_ID with action buttons:
    - [✅ Approve] (callback_data: approve_tutor:<id>)
    - [❌ Reject] (callback_data: reject_tutor:<id>)
    Routes to get_tutor_topic_id() if configured (Telegram Forum Supergroup).
    """
    if not bot_app or not settings.ADMIN_GROUP_ID:
        logger.debug("Bot or ADMIN_GROUP_ID not configured; skipping tutor notification.")
        return None

    try:
        card_text = format_tutor_card(tutor)

        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("✅ Approve", callback_data=f"approve_tutor:{tutor.id}"),
                InlineKeyboardButton("❌ Reject", callback_data=f"reject_tutor:{tutor.id}")
            ]
        ])

        send_kwargs = {
            "chat_id": settings.ADMIN_GROUP_ID,
            "text": card_text,
            "parse_mode": ParseMode.HTML,
            "reply_markup": keyboard,
            "disable_web_page_preview": False
        }
        topic_id = get_tutor_topic_id()
        if topic_id is not None:
            send_kwargs["message_thread_id"] = topic_id

        msg = await bot_app.bot.send_message(**send_kwargs)
        return msg.message_id
    except Exception as exc:
        logger.error("Failed to forward tutor registration #%s to Admin Group: %s", tutor.id, exc)
        return None
