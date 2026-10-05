import html
import logging
import re
from typing import Optional
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, MenuButtonWebApp, WebAppInfo
from telegram.constants import ParseMode
from telegram.ext import Application, ApplicationBuilder

from app.bot.topics import get_parent_topic_id, get_tutor_topic_id
from app.config import settings

logger = logging.getLogger("mentorlink.bot")

bot_app: Optional[Application] = None


async def configure_customer_menu_button(application: Application) -> bool:
    """Configure Telegram's native chat menu to launch the customer Mini App."""
    try:
        from app.bot.handlers import _get_webapp_url

        webapp_url = _get_webapp_url()
        if not webapp_url:
            logger.warning("Customer menu WebApp not configured: WEBAPP_URL/MINI_APP_URL is missing.")
            return False

        await application.bot.set_chat_menu_button(
            menu_button=MenuButtonWebApp(
                text="Register",
                web_app=WebAppInfo(url=webapp_url),
            )
        )
        logger.info("Telegram customer chat menu configured to open the Mini App.")
        return True
    except Exception as exc:
        logger.error("Failed to configure Telegram customer chat menu: %s", exc, exc_info=True)
        return False


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

    if settings.BOT_MODE == "webhook" and (not settings.WEBHOOK_URL or not settings.WEBHOOK_SECRET):
        raise RuntimeError("WEBHOOK_URL and WEBHOOK_SECRET are required when BOT_MODE=webhook")

    try:
        from app.bot.handlers import load_admin_registry, register_handlers

        builder = ApplicationBuilder().token(token.strip())
        if settings.BOT_MODE == "webhook":
            builder = builder.updater(None)
        application = builder.build()
        register_handlers(application)
        await load_admin_registry()

        await application.initialize()
        await configure_customer_menu_button(application)
        await application.start()

        if settings.BOT_MODE == "webhook":
            await application.bot.set_webhook(
                url=settings.WEBHOOK_URL,
                secret_token=settings.WEBHOOK_SECRET,
                drop_pending_updates=True,
            )
            logger.info("Telegram bot webhook registered.")
        else:
            # Purge stale webhooks and update locks before attaching polling.
            await application.bot.delete_webhook(drop_pending_updates=True)
            if application.updater:
                await application.updater.start_polling(drop_pending_updates=True)
            logger.info("Telegram bot polling started.")

        bot_app = application
        logger.info("Telegram Bot Application successfully initialized in %s mode.", settings.BOT_MODE)
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
    header_status = status_override or "Pending"
    tg_id_str = str(parent_req.telegram_user_id) if parent_req.telegram_user_id else "N/A"
    landmark_part = f" ({html.escape(parent_req.location_landmark)})" if parent_req.location_landmark else ""
    timing_str = f"{format_schedule(parent_req.schedule_days)} ({html.escape(parent_req.time_slot)}, {html.escape(parent_req.session_duration)})"
    subjects_str = format_subjects(parent_req.subjects)

    return (
        f"<b>PARENT REQUEST | {header_status}</b>\n\n"
        "<b>CONTACT</b>\n"
        f"<blockquote><b>Parent:</b> {html.escape(parent_req.parent_name)}\n"
        f"<b>Phone:</b> <code>{html.escape(parent_req.phone_number)}</code>\n"
        f"<b>Telegram ID:</b> <code>{tg_id_str}</code></blockquote>\n\n"
        "<b>STUDENT REQUIREMENTS</b>\n"
        f"<blockquote><b>Level:</b> {html.escape(parent_req.student_level)}\n"
        f"<b>Subjects:</b> {subjects_str}\n"
        f"<b>Tutor preference:</b> {html.escape(parent_req.preferred_gender)}\n"
        f"<b>Experience preference:</b> {html.escape(parent_req.preferred_experience)}</blockquote>\n\n"
        "<b>LOCATION</b>\n"
        f"<blockquote><b>Subcity:</b> {html.escape(parent_req.location_subcity)}{landmark_part}</blockquote>\n\n"
        "<b>SCHEDULE AND BUDGET</b>\n"
        f"<blockquote><b>Schedule:</b> {timing_str}\n"
        f"<b>Budget:</b> {parent_req.budget_etb:,.2f} ETB/hr</blockquote>"
    )


def format_parent_directory_badge(parent_req) -> str:
    """Renders the compact badge for the main Parent Requests directory topic."""
    subjects_str = format_subjects(parent_req.subjects)
    schedule_str = format_schedule(parent_req.schedule_days)
    return (
        f"<b>REQ-{parent_req.id:04d}</b> ── {html.escape(parent_req.student_level)}\n"
        f"<b>{html.escape(parent_req.parent_name)}</b> • {html.escape(parent_req.location_subcity)}\n"
        f"Subjects: {subjects_str} • Schedule: {schedule_str}\n"
        f"Status: <b>{html.escape(parent_req.status)}</b>"
    )


def format_tutor_card(tutor, status_override: Optional[str] = None, admin_username: Optional[str] = None) -> str:
    """Renders the Blockquote Terminal Data Card for a tutor profile with optional status override."""

    entrance_result_display = f"{tutor.entrance_result:g}" if tutor.entrance_result is not None else "Not provided"

    tg_id_str = str(tutor.telegram_user_id) if tutor.telegram_user_id else "N/A"
    header_status = status_override or "Pending Verification"

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
        f"<b>TUTOR TICKET | {header_status}</b>\n"
        f"{admin_line}\n\n"
        "<b>CANDIDATE</b>\n"
        f"<blockquote><b>Name:</b> {html.escape(tutor.full_name)}\n"
        f"<b>Gender:</b> {html.escape(tutor.gender)}\n"
        f"<b>Phone:</b> <code>{html.escape(tutor.phone_number)}</code>\n"
        f"<b>Telegram ID:</b> <code>{tg_id_str}</code></blockquote>\n\n"
        "<b>ACADEMIC BACKGROUND</b>\n"
        f"<blockquote><b>University:</b> {html.escape(tutor.university)}\n"
        f"<b>Department:</b> {html.escape(tutor.department)}\n"
        f"<b>Education:</b> {html.escape(tutor.education_year)}</blockquote>\n\n"
        "<b>TEACHING PROFILE</b>\n"
        f"<blockquote><b>Subjects:</b> {subjects_str}\n"
        f"<b>Grades:</b> {grades_str}\n"
        f"<b>Experience:</b> {years_exp} years\n"
        f"<b>Expected fee:</b> {tutor.expected_fee_etb:,.2f} ETB/hr</blockquote>\n\n"
        "<b>LOCATION AND AVAILABILITY</b>\n"
        f"<blockquote><b>Base subcity:</b> {html.escape(tutor.base_subcity)}\n"
        f"<b>Coverage areas:</b> {coverage_summary}\n"
        f"<b>Schedule:</b> {timing_str}</blockquote>\n\n"
        f"<b>DOCUMENTS AND RESULTS</b>\nEntrance result: {entrance_result_display}"
    )


def format_assignment_card_tutor(parent_req, tutor, assignment_id: Optional[int] = None) -> str:
    """Renders the Blockquote Terminal Data Card for tutor assignment notification."""
    asmt_tag = f" | ASMT-{assignment_id:04d}" if assignment_id else ""
    req_tag = f"REQ-{parent_req.id:04d}"
    landmark_part = f" ({html.escape(parent_req.location_landmark)})" if getattr(parent_req, "location_landmark", None) else ""
    schedule_days_str = format_schedule(parent_req.schedule_days)
    time_slot_str = html.escape(str(parent_req.time_slot))
    duration_str = html.escape(str(parent_req.session_duration))
    timing_str = f"{schedule_days_str} | {time_slot_str} ({duration_str})"
    subjects_str = format_subjects(parent_req.subjects)
    review_url = get_admin_review_url(f"request_{parent_req.id}") or ""
    review_link_html = f'\n\n<a href="{review_url}">Review in App</a>' if review_url else ""

    return (
        f"<b>TUTORING ASSIGNMENT{asmt_tag}</b>\n\n"
        f"<b>STUDENT & PARENT DETAILS</b> ({req_tag})\n"
        f"<blockquote><b>Parent:</b> {html.escape(parent_req.parent_name)}\n"
        f"<b>Student Level:</b> {html.escape(parent_req.student_level)}\n"
        f"<b>Phone:</b> <code>{html.escape(parent_req.phone_number)}</code></blockquote>\n\n"
        "<b>REQUIREMENTS</b>\n"
        f"<blockquote><b>Subjects:</b> {subjects_str}\n"
        f"<b>Location:</b> {html.escape(parent_req.location_subcity)}{landmark_part}</blockquote>\n\n"
        "<b>SCHEDULE & BUDGET</b>\n"
        f"<blockquote><b>Schedule:</b> {timing_str}\n"
        f"<b>Budget:</b> {parent_req.budget_etb:,.2f} ETB/hr</blockquote>"
        f"{review_link_html}"
    )


def format_assignment_card_parent(parent_req, tutor, assignment_id: Optional[int] = None) -> str:
    """Renders the Blockquote Terminal Data Card for parent assignment notification."""
    asmt_tag = f" | ASMT-{assignment_id:04d}" if assignment_id else ""
    req_tag = f"REQ-{parent_req.id:04d}"
    subjects_str = format_subjects(tutor.subjects_qualified)
    years_exp = f"{tutor.years_of_experience:g}"
    review_url = get_admin_review_url(f"request_{parent_req.id}") or ""
    review_link_html = f'\n\n<a href="{review_url}">Review in App</a>' if review_url else ""

    coverage_areas = tutor.coverage_areas if isinstance(tutor.coverage_areas, list) else [str(tutor.coverage_areas)]
    if len(coverage_areas) > 2:
        coverage_summary = f"+{len(coverage_areas) - 1} Sub-cities"
    else:
        coverage_summary = ", ".join(html.escape(str(c)) for c in coverage_areas)

    return (
        f"<b>ASSIGNED MENTOR DETAILS{asmt_tag}</b>\n\n"
        f"<b>MENTOR PROFILE</b> ({req_tag})\n"
        f"<blockquote><b>Name:</b> {html.escape(tutor.full_name)}\n"
        f"<b>Phone:</b> <code>{html.escape(tutor.phone_number)}</code>\n"
        f"<b>Experience:</b> {years_exp} years</blockquote>\n\n"
        "<b>ACADEMIC BACKGROUND</b>\n"
        f"<blockquote><b>University:</b> {html.escape(tutor.university)}\n"
        f"<b>Department:</b> {html.escape(tutor.department)}\n"
        f"<b>Education:</b> {html.escape(tutor.education_year)}</blockquote>\n\n"
        "<b>TEACHING & LOCATION</b>\n"
        f"<blockquote><b>Subjects:</b> {subjects_str}\n"
        f"<b>Base Subcity:</b> {html.escape(tutor.base_subcity)} ({coverage_summary})</blockquote>"
        f"{review_link_html}"
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


_review_url_warning_logged = False


def _bot_username() -> Optional[str]:
    """Username of the running bot, or None if it is not initialised."""
    if bot_app is None:
        return None
    try:
        username = bot_app.bot.username
    except Exception:
        return None
    return username.lstrip("@") if isinstance(username, str) and username else None


REVIEW_PAYLOAD_PREFIX = "review_"


def get_admin_review_bot_url(start_param: str) -> Optional[str]:
    """Bot deep link (t.me/<bot>?start=review_<param>). Needs no BotFather app registration."""
    username = _bot_username()
    if not username:
        return None
    return f"https://t.me/{username}?start={REVIEW_PAYLOAD_PREFIX}{start_param}"


def _resolve_mini_app_base_url() -> Optional[str]:
    """Return the ``https://t.me/<bot>/<short_name>`` base for Mini App deep links.

    Preference order:
      1. ``MINI_APP_URL`` when it is already a t.me direct link (the documented setting).
      2. ``https://t.me/<running bot's username>/<ADMIN_MINI_APP_SHORT_NAME>`` as a
         fallback, so setting MINI_APP_URL to the raw web URL (an easy mistake) no longer
         silently removes the "Review in App" buttons from every admin card.
    """
    mini_app_url = settings.MINI_APP_URL
    if mini_app_url and mini_app_url.startswith("https://t.me/"):
        return mini_app_url

    short_name = (settings.ADMIN_MINI_APP_SHORT_NAME or "").strip().strip("/")
    username = _bot_username()
    if username and short_name:
        return f"https://t.me/{username}/{short_name}"
    return None


def get_admin_review_url(start_param: str) -> Optional[str]:
    """Build a Telegram Mini App deep link from the configured bot app URL."""
    global _review_url_warning_logged
    mini_app_url = _resolve_mini_app_base_url()
    if not mini_app_url:
        if not _review_url_warning_logged:
            _review_url_warning_logged = True
            logger.warning(
                "Cannot build 'Review in App' links, so admin cards will have no such button. "
                "Set MINI_APP_URL to your BotFather direct link (https://t.me/<bot>/<short_name>) "
                "- NOT the Vercel URL - or make sure the bot is running and "
                "ADMIN_MINI_APP_SHORT_NAME matches the app you registered with /newapp."
            )
        return None
    parsed = urlsplit(mini_app_url)
    query = [(key, value) for key, value in parse_qsl(parsed.query, keep_blank_values=True) if key != "startapp"]
    query.append(("startapp", start_param))
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, urlencode(query), parsed.fragment))


def get_admin_review_buttons(start_param: str) -> list:
    """Buttons that open the admin app for a record, per ADMIN_REVIEW_LINK_MODE.

    A direct Mini App link can be resolved by Telegram to the bot chat instead of the app, so by
    default a second button goes through the bot, which replies with a real Mini App button.
    """
    mode = (settings.ADMIN_REVIEW_LINK_MODE or "both").strip().lower()
    direct = get_admin_review_url(start_param) if mode in ("direct", "both") else None
    via_bot = get_admin_review_bot_url(start_param) if (mode in ("bot", "both") or not direct) else None
    buttons = []
    if direct:
        buttons.append(InlineKeyboardButton("Review in App", url=direct))
    if via_bot:
        buttons.append(InlineKeyboardButton("Open via bot" if direct else "Review in App", url=via_bot))
    return buttons


def check_review_link_config() -> None:
    """Log what "Review in App" links will look like, so a wrong short name is visible at boot.

    A link like https://t.me/<bot>/<short_name>?startapp=... only opens the Mini App when
    <short_name> is registered (BotFather -> /newapp) on the SAME bot. Otherwise Telegram
    silently opens the bot chat instead, which is easy to mistake for an app bug.
    """
    sample = get_admin_review_url("tutor_1")
    if not sample:
        logger.warning("[TMA WARNING] Admin review URL could not be generated. Check MINI_APP_URL.")
        return  # get_admin_review_url already logged why
    segments = [part for part in urlsplit(sample).path.split("/") if part]
    if len(segments) < 2:
        logger.warning(
            "[TMA WARNING] MINI_APP_URL has no Mini App short name (%s). Such a link only opens an app if the bot's "
            "*Main* Mini App is configured; otherwise it opens the bot chat. Use the direct link of the "
            "admin app from @BotFather -> /myapps, e.g. https://t.me/<bot>/admin",
            sample,
        )
    else:
        logger.info("[TMA READY] 'Review in App' links will look like: %s", sample)
        logger.info(
            "[TMA READY] Check in @BotFather -> /myapps that '%s' is the short name of the ADMIN app and that its "
            "Web App URL ends with /admin.html (otherwise the button opens the bot chat or the wrong app).",
            segments[1],
        )


def build_parent_request_keyboard(request_id: int) -> InlineKeyboardMarkup:
    """Builds inline keyboard for dedicated parent request management topic."""
    buttons = []
    review_buttons = get_admin_review_buttons(f"request_{request_id}")
    if review_buttons:
        buttons.append(review_buttons)
    buttons.append([
        InlineKeyboardButton("🔍 Match Radar", callback_data=f"match_parent:{request_id}"),
        InlineKeyboardButton("❌ Close Request", callback_data=f"close_parent:{request_id}"),
    ])
    return InlineKeyboardMarkup(buttons)


def build_parent_index_keyboard(request_id: int, topic_url: Optional[str] = None) -> InlineKeyboardMarkup:
    """Builds inline keyboard for parent directory index badge."""
    row = []
    if topic_url:
        row.append(InlineKeyboardButton("🔗 Open Workspace", url=topic_url))
    row.extend(get_admin_review_buttons(f"request_{request_id}"))
    return InlineKeyboardMarkup([row] if row else [])


def build_tutor_registration_keyboard(tutor_id: int, has_doc: bool = False) -> InlineKeyboardMarkup:
    """Builds inline keyboard for tutor verification card."""
    buttons = []
    if has_doc:
        buttons.append([InlineKeyboardButton("📎 View Document", callback_data=f"view_doc:{tutor_id}")])
    review_buttons = get_admin_review_buttons(f"tutor_{tutor_id}")
    if review_buttons:
        buttons.append(review_buttons)
    return InlineKeyboardMarkup(buttons)


def build_tutor_assignment_keyboard(request_id: int) -> InlineKeyboardMarkup:
    """Builds inline keyboard for tutor assignment DM notification."""
    buttons = []
    review_url = get_admin_review_url(f"request_{request_id}")
    if review_url:
        buttons.append([InlineKeyboardButton("Review in App", url=review_url)])
    return InlineKeyboardMarkup(buttons)


def build_parent_assignment_keyboard(request_id: int) -> InlineKeyboardMarkup:
    """Builds inline keyboard for parent assignment DM notification."""
    buttons = []
    review_url = get_admin_review_url(f"request_{request_id}")
    if review_url:
        buttons.append([InlineKeyboardButton("Review in App", url=review_url)])
    return InlineKeyboardMarkup(buttons)


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
                prefix = f"PAR-{parent_req.id:04d} — "
                max_name_len = 128 - len(prefix)
                name_clean = parent_req.parent_name or "Parent"
                name_part = name_clean[:max_name_len] if max_name_len > 5 else name_clean[:20]
                topic_name = f"{prefix}{name_part}"[:128]

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
        keyboard = build_parent_request_keyboard(parent_req.id)

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

            # 2. Post Ticket Notification to the Index Topic ("Parent")
            clean_id = get_clean_chat_id(settings.ADMIN_GROUP_ID)
            topic_url = f"https://t.me/c/{clean_id}/{topic.message_thread_id}"

            index_text = format_parent_directory_badge(parent_req)
            index_keyboard = build_parent_index_keyboard(parent_req.id, topic_url=topic_url)

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
    - [📎 View Document] (if uploaded to /uploads/)
    - [Review in App] (deep-link to admin miniapp)
    Phase 3: approve/reject buttons removed — approval requires the verification checklist.
    Routes to get_tutor_topic_id() if configured (Telegram Forum Supergroup).
    """
    if not bot_app or not settings.ADMIN_GROUP_ID:
        logger.debug("Bot or ADMIN_GROUP_ID not configured; skipping tutor notification.")
        return None

    try:
        card_text = format_tutor_card(tutor)
        has_doc = bool(tutor.id_document_url and "/uploads/" in tutor.id_document_url)
        keyboard = build_tutor_registration_keyboard(tutor.id, has_doc=has_doc)

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
