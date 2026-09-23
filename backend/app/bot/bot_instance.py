import html
import logging
from typing import Optional

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import Application, ApplicationBuilder

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
    Sends a formatted intake card to ADMIN_GROUP_ID with action buttons:
    - [🔍 Find Best Tutors] (callback_data: match_parent:<id>)
    - [❌ Close Request] (callback_data: close_parent:<id>)
    """
    if not bot_app or not settings.ADMIN_GROUP_ID:
        logger.debug("Bot or ADMIN_GROUP_ID not configured; skipping parent notification.")
        return None

    try:
        landmark_info = f" ({html.escape(parent_req.location_landmark)})" if parent_req.location_landmark else ""
        card_text = (
            f"📋 <b>NEW PARENT TUTORING REQUEST #{parent_req.id}</b>\n\n"
            f"👤 <b>Parent Name:</b> {html.escape(parent_req.parent_name)}\n"
            f"📞 <b>Phone:</b> {html.escape(parent_req.phone_number)}\n"
            f"🎓 <b>Student Level:</b> {html.escape(parent_req.student_level)}\n"
            f"📚 <b>Subjects:</b> {format_subjects(parent_req.subjects)}\n"
            f"📍 <b>Location:</b> {html.escape(parent_req.location_subcity)}{landmark_info}\n"
            f"📅 <b>Schedule Days:</b> {format_schedule(parent_req.schedule_days)}\n"
            f"⏰ <b>Time Slot:</b> {html.escape(parent_req.time_slot)} ({html.escape(parent_req.session_duration)})\n"
            f"💰 <b>Budget:</b> {parent_req.budget_etb:,.2f} ETB\n"
            f"🧑‍🏫 <b>Tutor Prefs:</b> {html.escape(parent_req.preferred_gender)} | {html.escape(parent_req.preferred_experience)}\n"
            f"📊 <b>Status:</b> ⏳ {html.escape(parent_req.status).capitalize()}\n"
        )

        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("🔍 Find Best Tutors", callback_data=f"match_parent:{parent_req.id}"),
                InlineKeyboardButton("❌ Close Request", callback_data=f"close_parent:{parent_req.id}")
            ]
        ])

        msg = await bot_app.bot.send_message(
            chat_id=settings.ADMIN_GROUP_ID,
            text=card_text,
            parse_mode=ParseMode.HTML,
            reply_markup=keyboard
        )
        return msg.message_id
    except Exception as exc:
        logger.error("Failed to forward parent request #%s to Admin Group: %s", parent_req.id, exc)
        return None


async def send_tutor_registration_card(tutor) -> Optional[int]:
    """
    Sends a formatted tutor verification card to ADMIN_GROUP_ID with action buttons:
    - [✅ Approve Tutor] (callback_data: approve_tutor:<id>)
    - [❌ Reject] (callback_data: reject_tutor:<id>)
    """
    if not bot_app or not settings.ADMIN_GROUP_ID:
        logger.debug("Bot or ADMIN_GROUP_ID not configured; skipping tutor notification.")
        return None

    try:
        id_doc_line = ""
        if tutor.id_document_url:
            id_doc_line = f"🆔 <b>ID Document:</b> <a href=\"{html.escape(tutor.id_document_url)}\">View Document</a>\n"

        tg_id_line = f"💬 <b>Telegram ID:</b> <code>{tutor.telegram_user_id}</code>\n" if tutor.telegram_user_id else ""

        card_text = (
            f"🧑‍🏫 <b>NEW TUTOR REGISTRATION #{tutor.id}</b>\n\n"
            f"👤 <b>Full Name:</b> {html.escape(tutor.full_name)} ({html.escape(tutor.gender)})\n"
            f"📞 <b>Phone:</b> {html.escape(tutor.phone_number)}\n"
            f"{tg_id_line}"
            f"🏛 <b>University:</b> {html.escape(tutor.university)} - {html.escape(tutor.department)}\n"
            f"🎓 <b>Year/Status:</b> {html.escape(tutor.education_year)}\n"
            f"⭐ <b>Experience:</b> {tutor.years_of_experience:g} yrs\n"
            f"📚 <b>Subjects:</b> {format_subjects(tutor.subjects_qualified)}\n"
            f"🎯 <b>Grades:</b> {format_subjects(tutor.grades_qualified)}\n"
            f"📍 <b>Base Subcity:</b> {html.escape(tutor.base_subcity)}\n"
            f"🗺 <b>Coverage:</b> {format_subjects(tutor.coverage_areas)}\n"
            f"⏰ <b>Availability:</b> {format_schedule(tutor.availability_schedule)}\n"
            f"💰 <b>Expected Fee:</b> {tutor.expected_fee_etb:,.2f} ETB\n"
            f"{id_doc_line}"
            f"📊 <b>Status:</b> ⏳ {html.escape(tutor.status).capitalize()}\n"
        )

        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("✅ Approve Tutor", callback_data=f"approve_tutor:{tutor.id}"),
                InlineKeyboardButton("❌ Reject", callback_data=f"reject_tutor:{tutor.id}")
            ]
        ])

        msg = await bot_app.bot.send_message(
            chat_id=settings.ADMIN_GROUP_ID,
            text=card_text,
            parse_mode=ParseMode.HTML,
            reply_markup=keyboard,
            disable_web_page_preview=False
        )
        return msg.message_id
    except Exception as exc:
        logger.error("Failed to forward tutor registration #%s to Admin Group: %s", tutor.id, exc)
        return None
