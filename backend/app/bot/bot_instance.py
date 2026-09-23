import html
import logging
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


async def send_parent_request_card(parent_req) -> Optional[int]:
    """
    Sends a compact formatted intake card to ADMIN_GROUP_ID with action buttons:
    - [🔍 Match Tutors] (callback_data: match_parent:<id>)
    - [❌ Close] (callback_data: close_parent:<id>)
    Routes to get_parent_topic_id() if configured (Telegram Forum Supergroup).
    """
    if not bot_app or not settings.ADMIN_GROUP_ID:
        logger.debug("Bot or ADMIN_GROUP_ID not configured; skipping parent notification.")
        return None

    try:
        landmark_part = f" ({html.escape(parent_req.location_landmark)})" if parent_req.location_landmark else ""
        card_text = (
            f"📋 <b>PARENT REQUEST #{parent_req.id}</b> • 🟡 <b>Pending</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"👤 <b>{html.escape(parent_req.parent_name)}</b> | 📞 <code>{html.escape(parent_req.phone_number)}</code>\n"
            f"📍 <b>Location:</b> {html.escape(parent_req.location_subcity)}{landmark_part}\n"
            f"🎓 <b>Student:</b> {html.escape(parent_req.student_level)} | 📚 <b>Subjects:</b> {format_subjects(parent_req.subjects)}\n"
            f"⏰ <b>Schedule:</b> {format_schedule(parent_req.schedule_days)} ({html.escape(parent_req.time_slot)}, {html.escape(parent_req.session_duration)})\n"
            f"💰 <b>Budget:</b> {parent_req.budget_etb:,.2f} ETB | ⚧ <b>Pref:</b> {html.escape(parent_req.preferred_gender)} ({html.escape(parent_req.preferred_experience)})"
        )

        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("🔍 Match Tutors", callback_data=f"match_parent:{parent_req.id}"),
                InlineKeyboardButton("❌ Close", callback_data=f"close_parent:{parent_req.id}")
            ]
        ])

        send_kwargs = {
            "chat_id": settings.ADMIN_GROUP_ID,
            "text": card_text,
            "parse_mode": ParseMode.HTML,
            "reply_markup": keyboard
        }
        topic_id = get_parent_topic_id()
        if topic_id is not None:
            send_kwargs["message_thread_id"] = topic_id

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
        if tutor.id_document_url:
            doc_display = f'<a href="{html.escape(tutor.id_document_url)}">View Document</a>'
        else:
            doc_display = "Not provided"

        tg_id_str = str(tutor.telegram_user_id) if tutor.telegram_user_id else "N/A"

        card_text = (
            f"🧑‍🏫 <b>TUTOR PROFILE #{tutor.id}</b> • 🟡 <b>Pending Verification</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"👤 <b>{html.escape(tutor.full_name)}</b> ({html.escape(tutor.gender)}) | 📞 <code>{html.escape(tutor.phone_number)}</code> | 💬 ID: <code>{tg_id_str}</code>\n"
            f"🎓 <b>Education:</b> {html.escape(tutor.university)} — {html.escape(tutor.department)} ({html.escape(tutor.education_year)})\n"
            f"⭐ <b>Exp:</b> {tutor.years_of_experience:g} yrs | 💰 <b>Rate:</b> {tutor.expected_fee_etb:,.2f} ETB\n"
            f"📚 <b>Subjects:</b> {format_subjects(tutor.subjects_qualified)}\n"
            f"🎯 <b>Grades:</b> {format_subjects(tutor.grades_qualified)}\n"
            f"📍 <b>Base:</b> {html.escape(tutor.base_subcity)} | 🗺 <b>Covers:</b> {format_subjects(tutor.coverage_areas)}\n"
            f"⏰ <b>Availability:</b> {format_schedule(tutor.availability_schedule)}\n"
            f"📄 <b>ID Document:</b> {doc_display}"
        )

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
