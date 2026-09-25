import asyncio
from datetime import datetime, timezone
import html
import logging
import time
from typing import Dict, List, Optional, Tuple

from sqlalchemy import func, select, update as sql_update
from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InputFile,
    KeyboardButton,
    ReplyKeyboardMarkup,
    Update,
    WebAppInfo,
)
from telegram.constants import ParseMode
from telegram.error import RetryAfter, TelegramError
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from pathlib import Path

from app.bot.bot_instance import format_parent_card, format_tutor_card
from app.bot.topics import get_parent_topic_id
from app.config import settings, UPLOAD_DIR
from app.database import AsyncSessionLocal
from app.models import AdminWizardState, Assignment, MatchInvite, ParentRequest, SystemSetting, Tutor
from app.services.export_service import generate_parents_csv, generate_tutors_csv
from app.services.matcher import find_top_matches, get_tiered_matches

logger = logging.getLogger("mentorlink.bot.handlers")

# In-memory session cache & TTL cache for admin status
admin_states: Dict[int, dict] = {}
_admin_cache: Dict[int, Tuple[bool, float]] = {}
_admin_state_cache_times: Dict[int, float] = {}
ADMIN_STATE_TTL_SECONDS = 30 * 60


def is_super_admin(update: Update) -> bool:
    """Checks whether the effective user is the configured SUPER_ADMIN_ID."""
    if not settings.SUPER_ADMIN_ID or not update.effective_user:
        return False
    return update.effective_user.id == settings.SUPER_ADMIN_ID


async def is_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """
    Checks if user has admin privileges:
    1. Super Admin (SUPER_ADMIN_ID)
    2. Configured ADMIN_IDS
    3. Telegram group chat admin in ADMIN_GROUP_ID (cached for 300s)
    """
    if is_super_admin(update):
        return True

    user = update.effective_user
    if not user:
        return False

    if settings.ADMIN_IDS and user.id in settings.ADMIN_IDS:
        return True

    if not settings.ADMIN_GROUP_ID or not context or not context.bot:
        return False

    now = time.time()
    if user.id in _admin_cache:
        cached_result, expiry = _admin_cache[user.id]
        if now < expiry:
            return cached_result

    try:
        member = await context.bot.get_chat_member(
            chat_id=settings.ADMIN_GROUP_ID,
            user_id=user.id
        )
        has_perm = member.status in ("creator", "administrator")
        _admin_cache[user.id] = (has_perm, now + 300.0)
        return has_perm
    except Exception as exc:
        logger.debug("get_chat_member admin check failed for user %s: %s", user.id, exc)
        return False


async def get_admin_state(user_id: int) -> Optional[dict]:
    """Retrieves admin wizard state from in-memory cache or DB."""
    if user_id in admin_states:
        if time.time() - _admin_state_cache_times.get(user_id, time.time()) > ADMIN_STATE_TTL_SECONDS:
            await clear_admin_state(user_id)
            return None
        return admin_states[user_id]

    try:
        async with AsyncSessionLocal() as session:
            record = await session.get(AdminWizardState, user_id)
            if record:
                updated_at = record.updated_at
                if updated_at.tzinfo is None:
                    updated_at = updated_at.replace(tzinfo=timezone.utc)
                if (datetime.now(timezone.utc) - updated_at).total_seconds() > ADMIN_STATE_TTL_SECONDS:
                    await session.delete(record)
                    await session.commit()
                    return None
                state_dict = {"state": record.state, **(record.payload or {})}
                admin_states[user_id] = state_dict
                _admin_state_cache_times[user_id] = time.time()
                return state_dict
    except Exception as exc:
        logger.debug("Could not read admin state from DB: %s", exc)

    return None


async def set_admin_state(user_id: int, state: str, payload: Optional[dict] = None) -> None:
    """Persists admin wizard state in both memory and database."""
    state_dict = {"state": state, **(payload or {})}
    admin_states[user_id] = state_dict
    _admin_state_cache_times[user_id] = time.time()

    try:
        async with AsyncSessionLocal() as session:
            record = await session.get(AdminWizardState, user_id)
            if not record:
                record = AdminWizardState(admin_id=user_id, state=state, payload=payload or {})
                session.add(record)
            else:
                record.state = state
                record.payload = payload or {}
            await session.commit()
    except Exception as exc:
        logger.debug("Could not persist admin state to DB: %s", exc)


async def clear_admin_state(user_id: int) -> None:
    """Clears admin wizard state from both memory and database."""
    admin_states.pop(user_id, None)
    _admin_state_cache_times.pop(user_id, None)

    try:
        async with AsyncSessionLocal() as session:
            record = await session.get(AdminWizardState, user_id)
            if record:
                await session.delete(record)
                await session.commit()
    except Exception as exc:
        logger.debug("Could not delete admin state from DB: %s", exc)


def _get_webapp_url() -> Optional[str]:
    """
    Resolves the direct HTTPS web hosting URL of the Mini App frontend.
    Telegram WebAppInfo.url MUST be an actual web hosting URL (e.g. Vercel, Render)
    and CANNOT be a 'https://t.me/...' bot link.
    """
    # 1. Prefer WEBAPP_URL if set, valid HTTPS, and not a t.me link
    if settings.WEBAPP_URL and settings.WEBAPP_URL.startswith("https://") and not settings.WEBAPP_URL.startswith("https://t.me/"):
        return settings.WEBAPP_URL.rstrip("/")

    # 2. Check MINI_APP_URL if set, valid HTTPS, and not a t.me link
    if settings.MINI_APP_URL and settings.MINI_APP_URL.startswith("https://") and not settings.MINI_APP_URL.startswith("https://t.me/"):
        return settings.MINI_APP_URL.rstrip("/")

    # 3. Test compatibility fallback: if only MINI_APP_URL or WEBAPP_URL is set
    if settings.MINI_APP_URL and settings.MINI_APP_URL.startswith("https://"):
        return settings.MINI_APP_URL.rstrip("/")
    if settings.WEBAPP_URL and settings.WEBAPP_URL.startswith("https://"):
        return settings.WEBAPP_URL.rstrip("/")

    return None


def get_public_reply_keyboard() -> ReplyKeyboardMarkup:
    """Constructs public reply keyboard safely with WebApp button and customer options."""
    keyboard = []

    # Row 1: Only attach WebApp button if a valid HTTPS web hosting URL is available
    webapp_url = _get_webapp_url()
    if webapp_url:
        keyboard.append([
            KeyboardButton("🚀 Open MentorLink", web_app=WebAppInfo(url=webapp_url))
        ])

    # Row 2: Customer buttons (ALWAYS present)
    keyboard.append([
        KeyboardButton("ℹ️ About Us"),
        KeyboardButton("📞 Contact")
    ])

    return ReplyKeyboardMarkup(
        keyboard,
        resize_keyboard=True,
        is_persistent=True,
        one_time_keyboard=False
    )


def get_admin_reply_keyboard() -> ReplyKeyboardMarkup:
    """Builds persistent admin control keyboard."""
    keyboard = [
        [KeyboardButton("📊 Analytics"), KeyboardButton("📢 Broadcast")],
        [KeyboardButton("📝 Manage \"About Us\""), KeyboardButton("📥 Export CSV")]
    ]
    return ReplyKeyboardMarkup(
        keyboard,
        resize_keyboard=True,
        is_persistent=True,
        one_time_keyboard=False
    )


def _get_admin_name(update: Update) -> str:
    user = update.effective_user
    if not user:
        return "@admin"
    if user.username:
        return f"@{user.username}"
    return user.first_name or "Admin"


def _format_subjects(subjects) -> str:
    if isinstance(subjects, list):
        return ", ".join(html.escape(str(s)) for s in subjects)
    return html.escape(str(subjects or ""))


def _format_schedule(schedule) -> str:
    if isinstance(schedule, list):
        return ", ".join(html.escape(str(s)) for s in schedule)
    return html.escape(str(schedule or ""))


def _replace_card_header(text: str, new_header_html: str) -> str:
    """Non-destructively replaces the top line of a card with updated status while preserving content."""
    lines = text.split("\n")
    if not lines:
        return new_header_html
    remaining_lines = [html.escape(line) for line in lines[1:]]
    return new_header_html + "\n" + "\n".join(remaining_lines)


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Replies to /start command with role-appropriate keyboard."""
    message = update.message or update.effective_message
    if not message:
        return

    # Super Admin private console
    if is_super_admin(update):
        admin_keyboard = get_admin_reply_keyboard()
        await message.reply_text(
            text="👑 <b>MentorLink — SUPER ADMIN CONSOLE</b>\n\n"
                 "Welcome, Super Admin! Select an action from the menu below or tap an inline option.",
            reply_markup=admin_keyboard,
            parse_mode=ParseMode.HTML
        )
        return

    welcome_text = (
        "👋 <b>Welcome to MentorLink!</b>\n\n"
        "Connecting families with verified in-home tutors and university mentors across Addis Ababa.\n\n"
        "<blockquote><b>How It Works:</b>\n"
        "1️⃣ <b>Find a Tutor:</b> Tap <b>🚀 Open MentorLink</b> to request an expert mentor matching your child's curriculum, location, and schedule.\n"
        "2️⃣ <b>Become a Tutor:</b> Scholars & teachers can submit credentials for fast verification.\n"
        "3️⃣ <b>Direct Help:</b> Tap <b>ℹ️ About Us</b> or <b>📞 Contact</b> for coordinator support.</blockquote>\n\n"
        "<i>Select an option below to get started:</i>"
    )

    reply_markup = get_public_reply_keyboard()

    await message.reply_text(
        text=welcome_text,
        reply_markup=reply_markup,
        parse_mode="HTML"
    )


async def handle_callback_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Main callback router for admin and tutor inline keyboard button presses."""
    query = update.callback_query
    if not query or not query.data:
        return

    data = query.data
    logger.info("Received callback: %s from user %s", data, update.effective_user.id if update.effective_user else "unknown")

    # Admin actions authorization guard (S-01)
    admin_action_prefixes = (
        "approve_tutor:",
        "reject_tutor:",
        "match_parent:",
        "close_parent:",
        "assign_match:",
        "ping_candidates:",
        "view_doc:",
        "admin_analytics_",
        "admin_bcast_",
        "admin_cms_",
        "export:",
    )
    admin_group_action_prefixes = (
        "approve_tutor:",
        "reject_tutor:",
        "match_parent:",
        "close_parent:",
        "assign_match:",
        "ping_candidates:",
        "view_doc:",
    )
    if data.startswith(admin_action_prefixes):
        if not await is_admin(update, context):
            await query.answer("⛔ Access denied. Admin privileges required.", show_alert=True)
            return

        if data.startswith(admin_group_action_prefixes) and settings.ADMIN_GROUP_ID and query.message and getattr(query.message, "chat_id", None) is not None:
            if str(query.message.chat_id) != str(settings.ADMIN_GROUP_ID):
                await query.answer("⛔ This action can only be performed in the Admin Group.", show_alert=True)
                return

    if data.startswith("approve_tutor:"):
        await handle_approve_tutor(update, context, data)
    elif data.startswith("reject_tutor:"):
        await handle_reject_tutor(update, context, data)
    elif data.startswith("view_doc:"):
        await handle_view_document(update, context, data)
    elif data.startswith("match_parent:"):
        await handle_match_parent(update, context, data)
    elif data.startswith("close_parent:"):
        await handle_close_parent(update, context, data)
    elif data.startswith("assign_match:"):
        await handle_assign_match(update, context, data)
    elif data.startswith("ping_candidates:"):
        await handle_ping_candidates(update, context, data)
    elif data.startswith("tutor_avail_yes:"):
        await handle_tutor_avail_yes(update, context, data)
    elif data.startswith("tutor_avail_no:"):
        await handle_tutor_avail_no(update, context, data)
    elif data == "admin_analytics_refresh":
        await handle_admin_refresh_stats(update, context)
    elif data == "admin_analytics_close":
        await handle_admin_close_stats(update, context)
    elif data.startswith("admin_bcast_target:"):
        await handle_bcast_target_select(update, context, data)
    elif data == "admin_bcast_confirm":
        await handle_bcast_confirm(update, context)
    elif data == "admin_bcast_cancel":
        await handle_bcast_cancel(update, context)
    elif data == "admin_bcast_retype":
        await handle_bcast_retype(update, context)
    elif data.startswith("admin_cms_edit:"):
        await handle_cms_edit_select(update, context, data)
    elif data.startswith("admin_cms_view:"):
        await handle_cms_view_current(update, context, data)
    elif data == "admin_cms_cancel":
        await handle_cms_cancel(update, context)
    elif data.startswith("export:"):
        await handle_export_callback(update, context, data)
    elif data in ("noop", "assigned"):
        await query.answer("This action has already been processed.")
    else:
        await query.answer("Unrecognized action.")


async def handle_approve_tutor(update: Update, context: ContextTypes.DEFAULT_TYPE, data: str):
    """Approves tutor with atomic status update, edits card in-place, and DMs tutor."""
    query = update.callback_query
    tutor_id_str = data.split(":", 1)[1]
    admin_name = _get_admin_name(update)

    try:
        tutor_id = int(tutor_id_str)
    except ValueError:
        await query.answer("Invalid Tutor ID.")
        return

    async with AsyncSessionLocal() as session:
        tutor = await session.get(Tutor, tutor_id)
        if not tutor:
            await query.answer(f"Tutor #{tutor_id} not found.", show_alert=True)
            return

        if tutor.status != "pending":
            await query.answer(f"⚠️ Tutor #{tutor_id} is already {tutor.status}.", show_alert=True)
            return

        stmt = (
            sql_update(Tutor)
            .where(Tutor.id == tutor_id, Tutor.status == "pending")
            .values(status="verified")
        )
        res = await session.execute(stmt)
        if res.rowcount == 0:
            await query.answer("⚠️ This tutor has already been processed.", show_alert=True)
            return
        await session.commit()
        await session.refresh(tutor)

    await query.answer(f"Tutor #{tutor_id} approved!")

    # In-place full card update preserving complete HTML formatting
    if query.message:
        try:
            updated_text = format_tutor_card(tutor, status_override="🟢 <b>Approved</b>", admin_username=admin_name)
            await query.message.edit_text(
                text=updated_text,
                parse_mode=ParseMode.HTML,
                reply_markup=None,
                disable_web_page_preview=False
            )
        except Exception as exc:
            logger.error("Failed to edit tutor card for #%s: %s", tutor_id, exc)

    # Dispatch confirmation DM to tutor
    if tutor.telegram_user_id:
        try:
            dm_text = (
                f"🎉 Congratulations, {html.escape(tutor.full_name)}!\n\n"
                "Your MentorLink tutor profile has been approved. "
                "You will now receive student match alerts."
            )
            await context.bot.send_message(chat_id=tutor.telegram_user_id, text=dm_text, parse_mode=ParseMode.HTML)
        except Exception as exc:
            logger.warning("Could not send approval DM to tutor %s (tg_id: %s): %s", tutor.full_name, tutor.telegram_user_id, exc)


async def handle_reject_tutor(update: Update, context: ContextTypes.DEFAULT_TYPE, data: str):
    """Rejects tutor with atomic status update, edits card in-place, and DMs tutor."""
    query = update.callback_query
    tutor_id_str = data.split(":", 1)[1]
    admin_name = _get_admin_name(update)

    try:
        tutor_id = int(tutor_id_str)
    except ValueError:
        await query.answer("Invalid Tutor ID.")
        return

    async with AsyncSessionLocal() as session:
        tutor = await session.get(Tutor, tutor_id)
        if not tutor:
            await query.answer(f"Tutor #{tutor_id} not found.", show_alert=True)
            return

        if tutor.status != "pending":
            await query.answer(f"⚠️ Tutor #{tutor_id} is already {tutor.status}.", show_alert=True)
            return

        stmt = (
            sql_update(Tutor)
            .where(Tutor.id == tutor_id, Tutor.status == "pending")
            .values(status="rejected")
        )
        res = await session.execute(stmt)
        if res.rowcount == 0:
            await query.answer("⚠️ This tutor has already been processed.", show_alert=True)
            return
        await session.commit()
        await session.refresh(tutor)

    await query.answer(f"Tutor #{tutor_id} rejected.")

    # In-place full card update preserving complete HTML formatting
    if query.message:
        try:
            updated_text = format_tutor_card(tutor, status_override="🔴 <b>Rejected</b>", admin_username=admin_name)
            await query.message.edit_text(
                text=updated_text,
                parse_mode=ParseMode.HTML,
                reply_markup=None,
                disable_web_page_preview=False
            )
        except Exception as exc:
            logger.error("Failed to edit tutor card for #%s: %s", tutor_id, exc)

    # Dispatch rejection DM to tutor
    if tutor.telegram_user_id:
        try:
            dm_text = (
                f"Hello {html.escape(tutor.full_name)},\n\n"
                "Thank you for your interest in MentorLink. After review, we are unable to approve "
                "your tutor profile at this time. If you have any questions, please contact our support team."
            )
            await context.bot.send_message(chat_id=tutor.telegram_user_id, text=dm_text, parse_mode=ParseMode.HTML)
        except Exception as exc:
            logger.warning("Could not send rejection DM to tutor %s: %s", tutor.full_name, exc)


async def handle_view_document(update: Update, context: ContextTypes.DEFAULT_TYPE, data: str):
    """Securely delivers uploaded tutor credential document to the admin's DM."""
    query = update.callback_query
    parts = data.split(":", 1)
    if len(parts) != 2:
        await query.answer("Invalid request.")
        return

    try:
        tutor_id = int(parts[1])
    except ValueError:
        await query.answer("Invalid Tutor ID.")
        return

    async with AsyncSessionLocal() as session:
        tutor = await session.get(Tutor, tutor_id)
        if not tutor:
            await query.answer(f"Tutor #{tutor_id} not found.", show_alert=True)
            return

    if not tutor.id_document_url:
        await query.answer("No document attached for this tutor.", show_alert=True)
        return

    doc_parts = [p.strip() for p in tutor.id_document_url.split(" | ") if p.strip()]
    upload_parts = [p for p in doc_parts if "/uploads/" in p]
    if not upload_parts:
        await query.answer("No uploaded document file found.", show_alert=True)
        return

    target_part = upload_parts[0]
    filename = target_part.split("/uploads/")[-1].lstrip("/\\")
    upload_dir_path = Path(UPLOAD_DIR).resolve()
    doc_path = (upload_dir_path / filename).resolve()

    # Path traversal and existence check
    try:
        doc_path.relative_to(upload_dir_path)
    except ValueError:
        await query.answer("❌ Document file not found on server.", show_alert=True)
        return
    if not doc_path.is_file():
        await query.answer("❌ Document file not found on server.", show_alert=True)
        return

    user = update.effective_user
    if not user:
        return

    try:
        with open(doc_path, "rb") as doc_file:
            await context.bot.send_document(
                chat_id=user.id,
                document=doc_file,
                filename=filename,
                caption=f"📄 Credentials for Tutor #{tutor.id} ({tutor.full_name})"
            )
        await query.answer("Sent to your DMs! Check private chat with bot.")
    except TelegramError as exc:
        err_msg = str(exc)
        if "bot can't initiate conversation" in err_msg.lower() or "forbidden" in err_msg.lower():
            await query.answer("⚠️ Please /start the bot in private chat first so it can DM you the file.", show_alert=True)
        else:
            logger.error("Failed to send document DM to admin %s: %s", user.id, exc)
            await query.answer("⚠️ Could not deliver document. Please ensure you have started the bot in DMs.", show_alert=True)
    except Exception as exc:
        logger.error("Error sending document for tutor #%s: %s", tutor.id, exc)
        await query.answer("❌ An error occurred while retrieving the document.", show_alert=True)


async def handle_close_parent(update: Update, context: ContextTypes.DEFAULT_TYPE, data: str):
    """Closes parent request with atomic status update, edits card in-place, and then closes forum topic."""
    query = update.callback_query
    parent_id_str = data.split(":", 1)[1]
    admin_name = _get_admin_name(update)

    try:
        parent_id = int(parent_id_str)
    except ValueError:
        await query.answer("Invalid Request ID.")
        return

    async with AsyncSessionLocal() as session:
        parent_req = await session.get(ParentRequest, parent_id)
        if not parent_req:
            await query.answer(f"Request #{parent_id} not found.", show_alert=True)
            return

        if parent_req.status != "pending":
            await query.answer(f"⚠️ Request #{parent_id} is already {parent_req.status}.", show_alert=True)
            return

        stmt = (
            sql_update(ParentRequest)
            .where(ParentRequest.id == parent_id, ParentRequest.status == "pending")
            .values(status="closed")
        )
        res = await session.execute(stmt)
        if res.rowcount == 0:
            await query.answer("⚠️ This request has already been closed or matched.", show_alert=True)
            return
        await session.commit()
        await session.refresh(parent_req)

    await query.answer(f"Request #{parent_id} closed.")

    # In-place full card update preserving complete HTML formatting
    if query.message:
        try:
            updated_text = format_parent_card(parent_req, status_override=f"⚪ <b>Closed by {admin_name}</b>")
            await query.message.edit_text(
                text=updated_text,
                parse_mode=ParseMode.HTML,
                reply_markup=None
            )
        except Exception as exc:
            logger.error("Failed to edit parent card for #%s: %s", parent_id, exc)

    # Dedicated topic auto-closing ONLY AFTER card update is committed and posted
    if parent_req.telegram_topic_id and hasattr(context.bot, "close_forum_topic"):
        try:
            await context.bot.close_forum_topic(
                chat_id=settings.ADMIN_GROUP_ID,
                message_thread_id=parent_req.telegram_topic_id
            )
        except Exception as exc:
            logger.warning("Could not close forum topic %s for Request #%s: %s", parent_req.telegram_topic_id, parent_id, exc)


async def handle_match_parent(update: Update, context: ContextTypes.DEFAULT_TYPE, data: str):
    """
    Runs the tiered Match Radar engine for a parent request.
    If 0 matches: triggers native Telegram popup modal (zero chat spam).
    If matches exist: posts a consolidated Tiered Match Radar with assign & ping buttons.
    """
    query = update.callback_query
    parent_id_str = data.split(":", 1)[1]

    try:
        parent_id = int(parent_id_str)
    except ValueError:
        await query.answer("Invalid Request ID.")
        return

    async with AsyncSessionLocal() as session:
        parent, tiered = await get_tiered_matches(parent_id, session)

    if not parent:
        await query.answer(f"Parent Request #{parent_id} not found.", show_alert=True)
        return

    if parent.status != "pending":
        await query.answer(f"⚠️ Request #{parent_id} is already {parent.status}.", show_alert=True)
        return

    total_matches = len(tiered["tier1"]) + len(tiered["tier2"]) + len(tiered["tier3"])

    # Zero-regression anti-spam: Popup alert for 0 matches
    if total_matches == 0:
        await query.answer(
            text="⚠️ No eligible verified tutors found for this request.",
            show_alert=True
        )
        return

    await query.answer("🎯 Match Radar populated!")

    # Format Tiered Match Radar (capped at 5 per tier to stay within Telegram message limits)
    subjects_str = _format_subjects(parent.subjects)
    lines = [
        f"🎯 <b>MATCH RADAR FOR REQUEST #{parent_id}</b>",
        f"📍 {html.escape(parent.location_subcity)} • 📚 {subjects_str} • 💰 {parent.budget_etb:,.2f} ETB/hr",
        "━━━━━━━━━━━━━━━━━━━━━━"
    ]

    all_matched_tutors = []

    # Tier 1: Perfect Fit (cap 5)
    t1_matches = tiered["tier1"][:5]
    if t1_matches:
        lines.append("\n🟢 <b>PERFECT FIT</b>")
        for match in t1_matches:
            t = match["tutor"]
            all_matched_tutors.append(t)
            matched_subs = ", ".join(match.get("matched_subjects", []))
            lines.append(
                f"• <b>{html.escape(t.full_name)}</b> ({html.escape(t.university)} {html.escape(t.department)}, {html.escape(t.education_year)}) — {t.expected_fee_etb:,.0f} ETB/hr | ⭐ {t.years_of_experience:g} yrs\n"
                f"  📍 Base: {html.escape(t.base_subcity)} | 📚 {html.escape(matched_subs)}"
            )

    # Tier 2: Commute / Proximity (cap 5)
    t2_matches = tiered["tier2"][:5]
    if t2_matches:
        lines.append("\n🟡 <b>COMMUTE / PROXIMITY</b>")
        for match in t2_matches:
            t = match["tutor"]
            all_matched_tutors.append(t)
            cov_str = _format_subjects(t.coverage_areas)
            lines.append(
                f"• <b>{html.escape(t.full_name)}</b> ({html.escape(t.university)} {html.escape(t.department)}) — {t.expected_fee_etb:,.0f} ETB/hr | ⭐ {t.years_of_experience:g} yrs\n"
                f"  📍 Covers: {cov_str}"
            )

    # Tier 3: Flexible Alternatives (cap 5)
    t3_matches = tiered["tier3"][:5]
    if t3_matches:
        lines.append("\n⚪ <b>FLEX ALTERNATIVES</b>")
        for match in t3_matches:
            t = match["tutor"]
            all_matched_tutors.append(t)
            note = match.get("flex_note", "Flex match")
            lines.append(
                f"• <b>{html.escape(t.full_name)}</b> — {t.expected_fee_etb:,.0f} ETB/hr ({html.escape(note)})"
            )

    # Build Action Controls (Inline Keyboard)
    assign_buttons = []
    for t in all_matched_tutors[:3]:
        first_name = t.full_name.split()[0] if t.full_name else f"#{t.id}"
        assign_buttons.append(
            InlineKeyboardButton(
                f"📲 Assign {first_name}",
                callback_data=f"assign_match:{parent_id}:{t.id}"
            )
        )

    keyboard_rows = []
    if assign_buttons:
        keyboard_rows.append(assign_buttons)

    keyboard_rows.append([
        InlineKeyboardButton(
            "📡 Ping Candidates (Check Availability)",
            callback_data=f"ping_candidates:{parent_id}"
        )
    ])

    keyboard = InlineKeyboardMarkup(keyboard_rows)

    full_text = "\n".join(lines).strip()
    if len(full_text) > 4000:
        full_text = full_text[:3950] + "\n\n<i>... [radar truncated for length]</i>"

    if query.message:
        reply_kwargs = {
            "text": full_text,
            "parse_mode": ParseMode.HTML,
            "reply_markup": keyboard,
            "reply_to_message_id": query.message.message_id
        }
        thread_id = getattr(query.message, "message_thread_id", None)
        if thread_id:
            reply_kwargs["message_thread_id"] = thread_id

        await query.message.reply_text(**reply_kwargs)


async def handle_ping_candidates(update: Update, context: ContextTypes.DEFAULT_TYPE, data: str):
    """
    Broadcasts availability check DM to top matched verified tutors with interactive buttons.
    Persists MatchInvite records and avoids locking buttons eagerly if 0 tutors are sent.
    """
    query = update.callback_query
    parent_id_str = data.split(":", 1)[1]

    try:
        parent_id = int(parent_id_str)
    except ValueError:
        await query.answer("Invalid Request ID.")
        return

    async with AsyncSessionLocal() as session:
        parent, tiered = await get_tiered_matches(parent_id, session)
        if not parent:
            await query.answer(f"Parent request #{parent_id} not found.", show_alert=True)
            return

        if parent.status != "pending":
            await query.answer(f"⚠️ Request #{parent_id} is already {parent.status}.", show_alert=True)
            return

        # Query existing invites for this request
        inv_stmt = select(MatchInvite.tutor_id).where(MatchInvite.request_id == parent_id)
        inv_res = await session.execute(inv_stmt)
        already_invited = set(inv_res.scalars().all())

    all_matched = tiered["tier1"] + tiered["tier2"] + tiered["tier3"]
    # Filter candidates with TG IDs who haven't already received an invite
    tutors_to_ping = [
        c["tutor"] for c in all_matched
        if c["tutor"].telegram_user_id and c["tutor"].id not in already_invited
    ][:5]

    if not tutors_to_ping:
        if already_invited:
            await query.answer("⚠️ All top candidates have already been pinged for this request.", show_alert=True)
        else:
            await query.answer("⚠️ None of the matched tutors have registered Telegram user IDs.", show_alert=True)
        return

    landmark = f" ({html.escape(parent.location_landmark)})" if parent.location_landmark else ""
    subjects_str = _format_subjects(parent.subjects)
    schedule_str = _format_schedule(parent.schedule_days)

    ping_text = (
        f"💼 <b>NEW TUTORING OPPORTUNITY!</b>\n\n"
        f"📍 <b>Area:</b> {html.escape(parent.location_subcity)}{landmark}\n"
        f"🎓 <b>Level:</b> {html.escape(parent.student_level)} | 📚 <b>Subjects:</b> {subjects_str}\n"
        f"⏰ <b>Schedule:</b> {schedule_str} ({html.escape(parent.time_slot)})\n"
        f"💰 <b>Rate:</b> {parent.budget_etb:,.2f} ETB/hr\n\n"
        "Are you available to take this student?"
    )

    sent_count = 0
    newly_invited_ids = []
    for tutor in tutors_to_ping:
        try:
            tutor_keyboard = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("✅ Yes, I'm Available", callback_data=f"tutor_avail_yes:{parent_id}:{tutor.id}"),
                    InlineKeyboardButton("❌ Not Available", callback_data=f"tutor_avail_no:{parent_id}:{tutor.id}")
                ]
            ])
            await context.bot.send_message(
                chat_id=tutor.telegram_user_id,
                text=ping_text,
                parse_mode=ParseMode.HTML,
                reply_markup=tutor_keyboard
            )
            sent_count += 1
            newly_invited_ids.append(tutor.id)
        except Exception as exc:
            logger.warning("Failed to send ping DM to tutor %s (tg_id: %s): %s", tutor.full_name, tutor.telegram_user_id, exc)

    if sent_count > 0:
        # Record invites in DB
        async with AsyncSessionLocal() as session:
            for tid in newly_invited_ids:
                session.add(MatchInvite(request_id=parent_id, tutor_id=tid, status="sent"))
            await session.commit()

        # Update button in-place now that invites were genuinely sent
        if query.message and query.message.reply_markup:
            new_keyboard = []
            for row in query.message.reply_markup.inline_keyboard:
                new_row = []
                for btn in row:
                    if btn.callback_data and btn.callback_data.startswith("ping_candidates:"):
                        new_row.append(InlineKeyboardButton(f"⏳ Ping Sent ({sent_count})", callback_data="noop"))
                    else:
                        new_row.append(btn)
                new_keyboard.append(new_row)
            try:
                await query.message.edit_reply_markup(reply_markup=InlineKeyboardMarkup(new_keyboard))
            except Exception as exc:
                logger.debug("Failed to update ping button in-place: %s", exc)

        await query.answer(f"📡 Availability ping dispatched to {sent_count} candidate(s)!")
    else:
        await query.answer("⚠️ Could not deliver pings to candidates (they may have blocked the bot).", show_alert=True)


async def handle_tutor_avail_yes(update: Update, context: ContextTypes.DEFAULT_TYPE, data: str):
    """Handles tutor confirming availability, enforces user verification and single response, and alerts Admin Group."""
    query = update.callback_query
    parts = data.split(":")
    if len(parts) != 3:
        await query.answer("Invalid data.")
        return

    _, parent_id_str, tutor_id_str = parts
    try:
        parent_id = int(parent_id_str)
        tutor_id = int(tutor_id_str)
    except ValueError:
        await query.answer("Invalid IDs.")
        return

    user = update.effective_user
    if not user:
        return

    async with AsyncSessionLocal() as session:
        parent = await session.get(ParentRequest, parent_id)
        tutor = await session.get(Tutor, tutor_id)

        if not parent or not tutor:
            await query.answer("Record not found.", show_alert=True)
            return

        # Impersonation guard (S-02)
        if tutor.telegram_user_id != user.id:
            await query.answer("⛔ Unauthorized: This opportunity was sent to another tutor.", show_alert=True)
            return

        # Check if parent request is still open
        if parent.status != "pending":
            await query.answer("⚠️ This tutoring opportunity has already been filled or closed.", show_alert=True)
            if query.message:
                try:
                    await query.message.edit_text(
                        text=f"ℹ️ <b>Request #{parent_id} has already been filled or closed.</b>\n\nThank you for checking in!",
                        parse_mode=ParseMode.HTML,
                        reply_markup=None
                    )
                except Exception:
                    pass
            return

        # Check & record MatchInvite response (B-09)
        invite_stmt = select(MatchInvite).where(
            MatchInvite.request_id == parent_id,
            MatchInvite.tutor_id == tutor_id
        )
        invite = (await session.execute(invite_stmt)).scalar_one_or_none()
        if not invite or invite.status != "sent":
            await query.answer("⚠️ This opportunity is no longer available.", show_alert=True)
            return
        if invite and invite.status in ("yes", "no"):
            await query.answer("You have already responded to this opportunity.", show_alert=True)
            return

        invite.status = "yes"
        invite.responded_at = datetime.utcnow()

        await session.commit()

    # In tutor DM: edit message to show confirmation
    if query.message:
        try:
            await query.message.edit_text(
                text=f"✅ <b>Thank you, {html.escape(tutor.full_name)}!</b>\n\n"
                     f"You confirmed your availability for Request #{parent_id}. "
                     "Our coordination team has been notified and will finalize the match shortly.",
                parse_mode=ParseMode.HTML,
                reply_markup=None
            )
        except Exception as exc:
            logger.debug("Failed to edit tutor DM on avail yes: %s", exc)

    await query.answer("Availability confirmed! Thank you.")

    # Post confirmation to Admin Group topic
    if settings.ADMIN_GROUP_ID:
        try:
            subjects_str = _format_subjects(tutor.subjects_qualified)
            admin_alert_text = (
                f"🔔 <b>AVAILABILITY CONFIRMED!</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━━━\n"
                f"🧑‍🏫 <b>{html.escape(tutor.full_name)}</b> (<code>{html.escape(tutor.phone_number)}</code>) is available for Request #{parent_id}!\n"
                f"📚 <b>Subjects:</b> {subjects_str}\n"
                f"📍 Base: {html.escape(tutor.base_subcity)} | 💰 Rate: {tutor.expected_fee_etb:,.2f} ETB/hr"
            )
            confirm_btn = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton(
                        "✅ Assign",
                        callback_data=f"assign_match:{parent_id}:{tutor.id}"
                    )
                ]
            ])
            send_kwargs = {
                "chat_id": settings.ADMIN_GROUP_ID,
                "text": admin_alert_text,
                "parse_mode": ParseMode.HTML,
                "reply_markup": confirm_btn
            }
            topic_id = parent.telegram_topic_id or get_parent_topic_id()
            if topic_id is not None:
                send_kwargs["message_thread_id"] = topic_id

            await context.bot.send_message(**send_kwargs)
        except Exception as exc:
            logger.error("Failed to send availability alert to admin group: %s", exc)


async def handle_tutor_avail_no(update: Update, context: ContextTypes.DEFAULT_TYPE, data: str):
    """Handles tutor declining availability gracefully with single response guard and alerts admin group."""
    query = update.callback_query
    parts = data.split(":")
    if len(parts) != 3:
        await query.answer("Invalid data.")
        return

    _, parent_id_str, tutor_id_str = parts
    try:
        parent_id = int(parent_id_str)
        tutor_id = int(tutor_id_str)
    except ValueError:
        await query.answer("Invalid IDs.")
        return

    user = update.effective_user
    if not user:
        return

    async with AsyncSessionLocal() as session:
        tutor = await session.get(Tutor, tutor_id)
        parent = await session.get(ParentRequest, parent_id)
        if not tutor or tutor.telegram_user_id != user.id:
            await query.answer("⛔ Unauthorized.", show_alert=True)
            return

        invite_stmt = select(MatchInvite).where(
            MatchInvite.request_id == parent_id,
            MatchInvite.tutor_id == tutor_id
        )
        invite = (await session.execute(invite_stmt)).scalar_one_or_none()
        if not invite or invite.status != "sent":
            await query.answer("⚠️ This opportunity is no longer available.", show_alert=True)
            return
        if invite and invite.status in ("yes", "no"):
            await query.answer("You have already responded to this opportunity.", show_alert=True)
            return

        invite.status = "no"
        invite.responded_at = datetime.utcnow()
        await session.commit()

    if query.message:
        try:
            await query.message.edit_text(
                text="Thank you for letting us know! We will send you future opportunities that fit your schedule.",
                reply_markup=None
            )
        except Exception as exc:
            logger.debug("Failed to edit tutor DM on avail no: %s", exc)
    await query.answer("Response recorded.")

    # Post decline notification to Admin Group topic
    if settings.ADMIN_GROUP_ID:
        try:
            subjects_str = _format_subjects(tutor.subjects_qualified)
            decline_alert_text = (
                f"ℹ️ <b>AVAILABILITY UPDATE (DECLINED)</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━━━\n"
                f"🧑‍🏫 <b>{html.escape(tutor.full_name)}</b> is not available for Request #{parent_id}.\n"
                f"📚 <b>Subjects:</b> {subjects_str}"
            )
            send_kwargs = {
                "chat_id": settings.ADMIN_GROUP_ID,
                "text": decline_alert_text,
                "parse_mode": ParseMode.HTML,
            }
            topic_id = (parent.telegram_topic_id if parent else None) or get_parent_topic_id()
            if topic_id is not None:
                send_kwargs["message_thread_id"] = topic_id

            await context.bot.send_message(**send_kwargs)
        except Exception as exc:
            logger.error("Failed to send decline alert to admin group: %s", exc)


async def handle_assign_match(update: Update, context: ContextTypes.DEFAULT_TYPE, data: str):
    """Assigns a tutor to a parent request, marks request matched, posts thread confirmation, and then closes forum topic."""
    query = update.callback_query
    parts = data.split(":")
    if len(parts) != 3:
        await query.answer("Invalid assignment data.")
        return

    _, parent_id_str, tutor_id_str = parts
    admin_name = _get_admin_name(update)

    try:
        parent_id = int(parent_id_str)
        tutor_id = int(tutor_id_str)
    except ValueError:
        await query.answer("Invalid IDs.")
        return

    async with AsyncSessionLocal() as session:
        parent = await session.get(ParentRequest, parent_id)
        tutor = await session.get(Tutor, tutor_id)

        if not parent or not tutor:
            await query.answer("Parent request or Tutor not found.", show_alert=True)
            return

        if tutor.status != "verified":
            await query.answer("⚠️ Only verified tutors can be assigned.", show_alert=True)
            return

        invite_stmt = select(MatchInvite).where(
            MatchInvite.request_id == parent_id,
            MatchInvite.tutor_id == tutor_id,
            MatchInvite.status == "yes",
        )
        invite = (await session.execute(invite_stmt)).scalar_one_or_none()
        if not invite:
            await query.answer("⚠️ This tutor has not confirmed availability.", show_alert=True)
            return

        if parent.status != "pending":
            await query.answer(f"⚠️ Request #{parent_id} is already {parent.status}.", show_alert=True)
            return

        stmt = (
            sql_update(ParentRequest)
            .where(ParentRequest.id == parent_id, ParentRequest.status == "pending")
            .values(status="matched")
        )
        res = await session.execute(stmt)
        if res.rowcount == 0:
            await query.answer("⚠️ This request has already been assigned or closed.", show_alert=True)
            return

        assignment = Assignment(
            request_id=parent_id,
            tutor_id=tutor_id,
            assigned_by=admin_name
        )
        session.add(assignment)
        await session.commit()
        await session.refresh(parent)

    await query.answer(f"Assigned {tutor.full_name} to Request #{parent_id}!")

    # Lock button on match card and post thread confirmation FIRST (before topic closure!)
    first_name = tutor.full_name.split()[0] if tutor.full_name else "Tutor"
    if query.message:
        try:
            await query.message.edit_reply_markup(
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton(f"✅ Assigned {first_name} by {admin_name}", callback_data="assigned")]
                ])
            )
            assign_reply_kwargs = {
                "text": f"✅ Successfully assigned <b>{html.escape(tutor.full_name)}</b> to Parent Request #{parent_id} by {admin_name}.",
                "parse_mode": ParseMode.HTML,
                "reply_to_message_id": query.message.message_id
            }
            thread_id = getattr(query.message, "message_thread_id", None) or parent.telegram_topic_id
            if thread_id:
                assign_reply_kwargs["message_thread_id"] = thread_id

            await query.message.reply_text(**assign_reply_kwargs)
        except Exception as exc:
            logger.error("Error updating match assignment message: %s", exc)

    # Direct Notification to Parent upon Assignment (with html.escape)
    if parent.telegram_user_id:
        try:
            parent_dm = (
                f"🎉 <b>Great news, {html.escape(parent.parent_name)}!</b>\n\n"
                f"A verified mentor has been assigned to your tutoring request:\n"
                f"🧑‍🏫 <b>Mentor:</b> {html.escape(tutor.full_name)} ({html.escape(tutor.gender)})\n"
                f"🏛 <b>Background:</b> {html.escape(tutor.university)} — {html.escape(tutor.department)}\n"
                f"⭐ <b>Experience:</b> {tutor.years_of_experience:g} years\n"
                f"📞 <b>Phone:</b> {html.escape(tutor.phone_number)}\n\n"
                f"Our coordinator or your mentor will contact you shortly to confirm your first trial session. Thank you for trusting MentorLink! 🌟"
            )
            await context.bot.send_message(
                chat_id=parent.telegram_user_id,
                text=parent_dm,
                parse_mode=ParseMode.HTML
            )
        except Exception as exc:
            logger.warning("Could not send assignment DM to parent %s (tg_id: %s): %s", parent.parent_name, parent.telegram_user_id, exc)

    # DM tutor with job details (with html.escape)
    if tutor.telegram_user_id:
        try:
            landmark = f" ({html.escape(parent.location_landmark)})" if parent.location_landmark else ""
            subjects_str = _format_subjects(parent.subjects)
            days_str = _format_schedule(parent.schedule_days)

            job_alert = (
                f"📢 <b>New Tutoring Opportunity Assigned!</b>\n\n"
                f"Hello {html.escape(tutor.full_name)}, you have been assigned to Parent Request #{parent_id}:\n\n"
                f"👤 <b>Parent:</b> {html.escape(parent.parent_name)}\n"
                f"📞 <b>Contact:</b> {html.escape(parent.phone_number)}\n"
                f"🎓 <b>Student Level:</b> {html.escape(parent.student_level)}\n"
                f"📚 <b>Subjects:</b> {subjects_str}\n"
                f"📍 <b>Location:</b> {html.escape(parent.location_subcity)}{landmark}\n"
                f"📅 <b>Schedule:</b> {days_str} | {html.escape(parent.time_slot)} ({html.escape(parent.session_duration)})\n"
                f"💰 <b>Budget:</b> {parent.budget_etb:,.2f} ETB\n\n"
                "Please reach out to the parent or contact admin to confirm your first session."
            )
            await context.bot.send_message(
                chat_id=tutor.telegram_user_id,
                text=job_alert,
                parse_mode=ParseMode.HTML
            )
        except Exception as exc:
            logger.warning("Could not send assignment DM to tutor %s: %s", tutor.full_name, exc)

    # Dedicated topic auto-closing ONLY AFTER thread messages and DMs complete
    if parent.telegram_topic_id and hasattr(context.bot, "close_forum_topic"):
        try:
            await context.bot.close_forum_topic(
                chat_id=settings.ADMIN_GROUP_ID,
                message_thread_id=parent.telegram_topic_id
            )
        except Exception as exc:
            logger.warning("Could not close forum topic %s for Request #%s: %s", parent.telegram_topic_id, parent.id, exc)


async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Direct shortcut command to access the Super Admin Console."""
    msg = update.message or update.effective_message
    if not msg:
        return

    if not is_super_admin(update):
        await msg.reply_text(text="⛔ Access denied. This console is restricted to the Super Admin.")
        return

    admin_keyboard = get_admin_reply_keyboard()
    await msg.reply_text(
        text="👑 <b>MentorLink — SUPER ADMIN CONSOLE</b>\n\n"
             "Welcome, Super Admin! Select an action from the menu below or tap an inline option.",
        reply_markup=admin_keyboard,
        parse_mode=ParseMode.HTML
    )
    return


async def handle_about_us(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Renders plain-text About Us content from SystemSetting or a fallback."""
    msg = update.message or update.effective_message
    if not msg:
        return

    async with AsyncSessionLocal() as session:
        setting = await session.get(SystemSetting, "about_us_text")
        bio_text = setting.value if setting and setting.value else None

    if not bio_text:
        bio_text = (
            "🌟 About MentorLink\n\n"
            "MentorLink is Addis Ababa's premier home tutoring network connecting university "
            "scholars and verified educators with students across all grade levels.\n\n"
            "✨ Our Standards:\n"
            "• Rigorous credential & ID verification\n"
            "• University-vetted mentors from top institutions\n"
            "• Tailored matching based on proximity, curriculum & student learning goals"
        )

    await msg.reply_text(text=bio_text)


async def handle_support_contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Renders plain-text support contact content from SystemSetting or a fallback."""
    msg = update.message or update.effective_message
    if not msg:
        return

    async with AsyncSessionLocal() as session:
        setting = await session.get(SystemSetting, "support_contact")
        contact_text = setting.value if setting and setting.value else None

    if not contact_text:
        contact_text = (
            "📞 Support & Coordination\n\n"
            "Need help finding a mentor or have questions about our tutoring programs?\n\n"
            "💬 Telegram: @MentorLinkSupport\n"
            "📱 Phone: +251 91 100 2233\n"
            "🕒 Hours: Mon – Sat, 8:30 AM – 6:30 PM (EAT)\n"
            "📍 Addis Ababa, Ethiopia"
        )

    await msg.reply_text(text=contact_text)


async def render_analytics_card() -> str:
    """Calculates KPI statistics across tutors and requests, returning HTML formatted text."""
    async with AsyncSessionLocal() as session:
        # Tutors breakdown
        total_tutors = await session.scalar(select(func.count(Tutor.id))) or 0
        verified_tutors = await session.scalar(select(func.count(Tutor.id)).where(Tutor.status == "verified")) or 0
        pending_tutors = await session.scalar(select(func.count(Tutor.id)).where(Tutor.status == "pending")) or 0
        rejected_tutors = await session.scalar(select(func.count(Tutor.id)).where(Tutor.status == "rejected")) or 0

        # Parent Requests breakdown
        total_requests = await session.scalar(select(func.count(ParentRequest.id))) or 0
        open_requests = await session.scalar(select(func.count(ParentRequest.id)).where(ParentRequest.status == "pending")) or 0
        matched_requests = await session.scalar(select(func.count(ParentRequest.id)).where(ParentRequest.status == "matched")) or 0

        # Average tutor fee
        avg_fee = await session.scalar(select(func.avg(Tutor.expected_fee_etb)).where(Tutor.status == "verified")) or 0.0

        # Top subcity demand
        subcity_res = await session.execute(
            select(ParentRequest.location_subcity, func.count(ParentRequest.id))
            .group_by(ParentRequest.location_subcity)
            .order_by(func.count(ParentRequest.id).desc())
            .limit(3)
        )
        top_subcities = subcity_res.all()

    subcities_str = ", ".join(f"{sc} ({cnt})" for sc, cnt in top_subcities) if top_subcities else "No data yet"
    ver_pct = f"{(verified_tutors / total_tutors * 100):.0f}%" if total_tutors > 0 else "0%"
    match_pct = f"{(matched_requests / total_requests * 100):.0f}%" if total_requests > 0 else "0%"

    return (
        "📊 <b>PLATFORM ANALYTICS & KPIS</b>\n\n"
        "<blockquote><b>🧑‍🏫 Tutor Community:</b> <code>" + str(total_tutors) + "</code> Total\n"
        f"├ 🟢 Verified: <code>{verified_tutors}</code> ({ver_pct})\n"
        f"├ ⏳ Pending: <code>{pending_tutors}</code>\n"
        f"└ 🔴 Rejected: <code>{rejected_tutors}</code>\n\n"
        f"<b>📋 Parent Tutoring Requests:</b> <code>{total_requests}</code> Total\n"
        f"├ 🟡 Open / Pending: <code>{open_requests}</code>\n"
        f"└ ✅ Matched / Fulfilled: <code>{matched_requests}</code> ({match_pct})\n\n"
        f"<b>💰 Economic Metrics:</b>\n"
        f"└ Avg Verified Fee: <code>{avg_fee:,.0f} ETB/hr</code>\n\n"
        f"<b>📍 High-Demand Zones:</b>\n"
        f"└ {subcities_str}</blockquote>"
    )


def get_analytics_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🔄 Refresh Stats", callback_data="admin_analytics_refresh"),
            InlineKeyboardButton("🔙 Close", callback_data="admin_analytics_close")
        ]
    ])


async def handle_admin_analytics(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message or update.effective_message
    if not msg:
        return
    if not is_super_admin(update):
        await msg.reply_text(text="⛔ Restricted to Super Admin.")
        return

    card_text = await render_analytics_card()
    await msg.reply_text(
        text=card_text,
        parse_mode=ParseMode.HTML,
        reply_markup=get_analytics_keyboard()
    )


async def handle_admin_refresh_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not is_super_admin(update):
        await query.answer("⛔ Access denied.", show_alert=True)
        return

    card_text = await render_analytics_card()
    try:
        await query.message.edit_text(
            text=card_text,
            parse_mode=ParseMode.HTML,
            reply_markup=get_analytics_keyboard()
        )
        await query.answer("Stats updated! 🔄")
    except TelegramError as exc:
        if "Message is not modified" in str(exc):
            await query.answer("Stats are already up to date! 🔄")
        else:
            logger.debug("Error refreshing stats: %s", exc)
            await query.answer("Stats up to date.")
    except Exception as exc:
        logger.debug("Failed to edit stats: %s", exc)
        await query.answer("Stats up to date.")


async def handle_admin_close_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not is_super_admin(update):
        await query.answer("⛔ Access denied.", show_alert=True)
        return
    try:
        await query.message.edit_text("📊 <i>Analytics dashboard closed.</i>", parse_mode=ParseMode.HTML, reply_markup=None)
    except Exception:
        pass
    await query.answer("Closed.")


def get_broadcast_targets_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("👥 All Users", callback_data="admin_bcast_target:all")],
        [InlineKeyboardButton("🧑‍🏫 Verified Tutors", callback_data="admin_bcast_target:tutors_verified")],
        [InlineKeyboardButton("⏳ Pending Tutors", callback_data="admin_bcast_target:tutors_pending")],
        [InlineKeyboardButton("📋 Parents Only", callback_data="admin_bcast_target:parents")],
        [InlineKeyboardButton("❌ Cancel", callback_data="admin_bcast_cancel")]
    ])


async def handle_broadcast_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message or update.effective_message
    if not msg:
        return
    if not is_super_admin(update):
        await msg.reply_text(text="⛔ Restricted to Super Admin.")
        return

    await msg.reply_text(
        text="📢 <b>Segmented Broadcast Dispatcher</b>\n\n"
             "Select your target recipient audience:",
        parse_mode=ParseMode.HTML,
        reply_markup=get_broadcast_targets_keyboard()
    )


async def get_broadcast_recipient_ids(target: str) -> List[int]:
    async with AsyncSessionLocal() as session:
        user_ids = set()
        if target in ("all", "tutors_verified"):
            tutors = (await session.execute(
                select(Tutor.telegram_user_id).where(Tutor.status == "verified", Tutor.telegram_user_id.isnot(None))
            )).scalars().all()
            user_ids.update(t for t in tutors if t)

        if target in ("all", "tutors_pending"):
            pending = (await session.execute(
                select(Tutor.telegram_user_id).where(Tutor.status == "pending", Tutor.telegram_user_id.isnot(None))
            )).scalars().all()
            user_ids.update(t for t in pending if t)

        if target in ("all", "parents"):
            parents = (await session.execute(
                select(ParentRequest.telegram_user_id).where(ParentRequest.telegram_user_id.isnot(None))
            )).scalars().all()
            user_ids.update(p for p in parents if p)

    return list(user_ids)


async def handle_bcast_target_select(update: Update, context: ContextTypes.DEFAULT_TYPE, data: str):
    query = update.callback_query
    if not is_super_admin(update):
        await query.answer("⛔ Access denied.", show_alert=True)
        return

    target = data.split(":", 1)[1]
    admin_id = update.effective_user.id
    await set_admin_state(admin_id, "AWAITING_BROADCAST_TEXT", {"target": target})

    target_labels = {
        "all": "👥 All Users",
        "tutors_verified": "🧑‍🏫 Verified Tutors",
        "tutors_pending": "⏳ Pending Tutors",
        "parents": "📋 Parents Only"
    }

    await query.message.edit_text(
        f"Target selected: <b>{target_labels.get(target, target)}</b>\n\n"
        "✍️ Please send the broadcast announcement message now.\n"
        "(Plain text is used; Telegram formatting is not interpreted.)",
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("❌ Cancel", callback_data="admin_bcast_cancel")]
        ])
    )
    await query.answer()


async def _run_broadcast_task(bot, recipient_ids: List[int], message_text: str, chat_id: int):
    """Executes broadcast asynchronously without blocking bot event loop."""
    success_count = 0
    fail_count = 0

    for uid in recipient_ids:
        try:
            await bot.send_message(
                chat_id=uid,
                text=message_text
            )
            success_count += 1
        except RetryAfter as exc:
            logger.info("Broadcast hit rate limit, waiting %s seconds", exc.retry_after)
            await asyncio.sleep(exc.retry_after + 0.1)
            try:
                await bot.send_message(
                    chat_id=uid,
                    text=message_text
                )
                success_count += 1
            except Exception as e2:
                logger.warning("Broadcast retry failed for user %s: %s", uid, e2)
                fail_count += 1
        except Exception:
            # Fallback to plain text on formatting error
            try:
                await bot.send_message(
                    chat_id=uid,
                    text=message_text
                )
                success_count += 1
            except Exception as exc:
                logger.warning("Failed to send broadcast to user %s: %s", uid, exc)
                fail_count += 1
        await asyncio.sleep(0.05)

    try:
        await bot.send_message(
            chat_id=chat_id,
              text=f"✅ Broadcast Completed!\n\n"
                 f"• Sent: {success_count}\n"
                 f"• Failed/Blocked: {fail_count}\n"
                  f"• Total Audience: {len(recipient_ids)}"
        )
    except Exception as exc:
        logger.error("Failed to send broadcast completion report: %s", exc)


async def handle_bcast_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    admin_id = update.effective_user.id
    if not is_super_admin(update):
        await query.answer("⛔ Access denied.", show_alert=True)
        return

    state_data = await get_admin_state(admin_id)
    await clear_admin_state(admin_id)

    if not state_data or state_data.get("state") != "AWAITING_BROADCAST_CONFIRM":
        await query.answer("No broadcast awaiting confirmation.", show_alert=True)
        return

    target = state_data["target"]
    message_text = state_data["text"]
    recipient_ids = await get_broadcast_recipient_ids(target)

    await query.message.edit_text(
        f"⏳ Broadcast dispatched in background to {len(recipient_ids)} recipients at rate ~20 msg/s...",
        reply_markup=None
    )
    await query.answer("Broadcast started!")

    # Non-blocking async background task execution (B-07)
    asyncio.create_task(
        _run_broadcast_task(
            bot=context.bot,
            recipient_ids=recipient_ids,
            message_text=message_text,
            chat_id=query.message.chat_id
        )
    )


async def handle_bcast_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    admin_id = update.effective_user.id
    await clear_admin_state(admin_id)
    await query.message.edit_text("❌ Broadcast cancelled.")
    await query.answer("Cancelled.")


async def handle_bcast_retype(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    admin_id = update.effective_user.id
    state_data = await get_admin_state(admin_id)
    if state_data:
        target = state_data.get("target", "all")
        await set_admin_state(admin_id, "AWAITING_BROADCAST_TEXT", {"target": target})
        await query.message.edit_text(
            "✍️ Send the revised broadcast message text now:",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("❌ Cancel", callback_data="admin_bcast_cancel")]
            ])
        )
    await query.answer()


def get_cms_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("👁️ View 'About Us'", callback_data="admin_cms_view:about_us_text"),
            InlineKeyboardButton("✏️ Edit 'About Us'", callback_data="admin_cms_edit:about_us_text")
        ],
        [
            InlineKeyboardButton("👁️ View 'Contact'", callback_data="admin_cms_view:support_contact"),
            InlineKeyboardButton("✏️ Edit 'Contact'", callback_data="admin_cms_edit:support_contact")
        ],
        [InlineKeyboardButton("❌ Close", callback_data="admin_cms_cancel")]
    ])


async def handle_cms_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message or update.effective_message
    if not msg:
        return
    if not is_super_admin(update):
        await msg.reply_text(text="⛔ Restricted to Super Admin.")
        return

    await msg.reply_text(
        text="📝 <b>Content Management (CMS)</b>\n\n"
             "Manage the live content served to users for <b>'About Us'</b> and <b>'Contact'</b>:",
        parse_mode=ParseMode.HTML,
        reply_markup=get_cms_keyboard()
    )


async def handle_cms_view_current(update: Update, context: ContextTypes.DEFAULT_TYPE, data: str):
    query = update.callback_query
    if not is_super_admin(update):
        await query.answer("⛔ Access denied.", show_alert=True)
        return

    setting_key = data.split(":", 1)[1]
    async with AsyncSessionLocal() as session:
        setting = await session.get(SystemSetting, setting_key)
        current_val = setting.value if setting else "(Not set — using platform default)"

    await query.message.reply_text(
        text=f"📄 <b>Current content for <code>{html.escape(setting_key)}</code>:</b>\n\n"
             f"<pre>{html.escape(current_val)}</pre>",
        parse_mode=ParseMode.HTML
    )
    await query.answer()


async def handle_cms_edit_select(update: Update, context: ContextTypes.DEFAULT_TYPE, data: str):
    query = update.callback_query
    if not is_super_admin(update):
        await query.answer("⛔ Access denied.", show_alert=True)
        return

    setting_key = data.split(":", 1)[1]
    admin_id = update.effective_user.id
    await set_admin_state(admin_id, "AWAITING_CMS_INPUT", {"key": setting_key})

    label = "About Us" if setting_key == "about_us_text" else "Contact"

    async with AsyncSessionLocal() as session:
        setting = await session.get(SystemSetting, setting_key)
        current_val = setting.value if setting and setting.value else "(Default platform copy)"

    await query.message.edit_text(
        f"✏️ <b>Edit Content — {label}</b>\n\n"
        f"<b>Current Content:</b>\n"
        f"<pre>{html.escape(current_val)}</pre>\n"
        f"✍️ Please send the new text for <b>{label}</b> now:\n"
        "<i>(Plain text is used; Telegram formatting is not interpreted.)</i>",
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("↩️ Keep Existing / Cancel", callback_data="admin_cms_cancel")]
        ])
    )
    await query.answer()


async def handle_cms_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    admin_id = update.effective_user.id
    await clear_admin_state(admin_id)
    await query.message.edit_text("↩️ CMS editing cancelled. Existing content preserved.")
    await query.answer("Cancelled.")


def get_export_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🧑‍🏫 Export Tutors", callback_data="export:tutors")],
        [InlineKeyboardButton("👨‍👩‍👦 Export Parent Requests", callback_data="export:parents")],
        [InlineKeyboardButton("📦 Export All (Both)", callback_data="export:both")],
        [InlineKeyboardButton("❌ Close", callback_data="export:close")]
    ])


async def handle_export_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Renders the Super Admin CSV Data Export menu."""
    msg = update.message or update.effective_message
    if not msg:
        return
    if not is_super_admin(update):
        await msg.reply_text(text="⛔ Restricted to Super Admin.")
        return

    user_id = update.effective_user.id if update.effective_user else None
    if user_id:
        await clear_admin_state(user_id)

    await msg.reply_text(
        text="📥 <b>EXPORT DATA CENTER</b>\n\n"
             "Choose the records you want to download as CSV (Excel compatible):",
        parse_mode=ParseMode.HTML,
        reply_markup=get_export_keyboard()
    )


async def handle_export_callback(update: Update, context: ContextTypes.DEFAULT_TYPE, data: str):
    """Processes CSV data export requests from Super Admin."""
    query = update.callback_query
    if not query:
        return

    if not is_super_admin(update):
        await query.answer("⛔ Access denied. Restricted to Super Admin.", show_alert=True)
        return

    action = data.split(":", 1)[1] if ":" in data else ""

    if action == "close":
        await query.answer("Closed.")
        try:
            await query.message.edit_text("📥 <i>Export Data Center closed.</i>", parse_mode=ParseMode.HTML)
        except Exception:
            pass
        return

    await query.answer("⏳ Generating CSV export...")
    chat_id = update.effective_chat.id if update.effective_chat else update.effective_user.id
    date_str = datetime.now().strftime("%Y%m%d_%H%M%S")

    async with AsyncSessionLocal() as session:
        if action in ("tutors", "both"):
            buffer, count = await generate_tutors_csv(session)
            filename = f"mentors_{date_str}.csv"
            caption = f"✅ Export generated: {count} tutor records."
            try:
                doc = InputFile(buffer, filename=filename)
            except Exception:
                doc = buffer
            await context.bot.send_document(
                chat_id=chat_id,
                document=doc,
                filename=filename,
                caption=caption
            )

        if action in ("parents", "both"):
            buffer, count = await generate_parents_csv(session)
            filename = f"parent_requests_{date_str}.csv"
            caption = f"✅ Export generated: {count} parent request records."
            try:
                doc = InputFile(buffer, filename=filename)
            except Exception:
                doc = buffer
            await context.bot.send_document(
                chat_id=chat_id,
                document=doc,
                filename=filename,
                caption=caption
            )


async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Allows Super Admin to cancel any active broadcast wizard or CMS edit session."""
    msg = update.message or update.effective_message
    user_id = update.effective_user.id if update.effective_user else None
    if user_id:
        await clear_admin_state(user_id)
        if msg:
            await msg.reply_text(text="❌ Action cancelled. Returned to main menu.")
    else:
        if msg:
            await msg.reply_text(text="ℹ️ No active action to cancel.")


async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Processes incoming non-command text messages for keyboard buttons & admin wizard states."""
    msg = update.message or update.effective_message
    if not msg or not msg.text:
        return

    text = msg.text.strip()
    user_id = update.effective_user.id if update.effective_user else None

    # Cancel escape
    if text.lower() in ("/cancel", "cancel"):
        if user_id:
            await clear_admin_state(user_id)
            await msg.reply_text(text="❌ Action cancelled. Returned to main menu.")
            return

    # Public Reply Keyboard buttons
    if text == "ℹ️ About Us":
        if user_id:
            await clear_admin_state(user_id)
        await handle_about_us(update, context)
        return
    elif text == "📞 Contact":
        if user_id:
            await clear_admin_state(user_id)
        await handle_support_contact(update, context)
        return

    # Super Admin Reply Keyboard buttons
    if is_super_admin(update):
        if text in ("📊 Analytics", "📢 Broadcast", "📝 Manage \"About Us\"", "📝 Manage 'About Us'", "📥 Export CSV"):
            if user_id:
                await clear_admin_state(user_id)

        if text == "📊 Analytics":
            await handle_admin_analytics(update, context)
            return
        elif text == "📢 Broadcast":
            await handle_broadcast_menu(update, context)
            return
        elif text in ("📝 Manage \"About Us\"", "📝 Manage 'About Us'"):
            await handle_cms_menu(update, context)
            return
        elif text == "📥 Export CSV":
            await handle_export_menu(update, context)
            return

    # Super Admin Interactive Wizard States
    if user_id and is_super_admin(update):
        state_data = await get_admin_state(user_id)
        if state_data:
            current_state = state_data.get("state")

            if current_state == "AWAITING_BROADCAST_TEXT":
                target = state_data.get("target", "all")
                await set_admin_state(user_id, "AWAITING_BROADCAST_CONFIRM", {"target": target, "text": text})
                recipient_ids = await get_broadcast_recipient_ids(target)

                preview_card = (
                    "📢 <b>BROADCAST PREVIEW</b>\n\n"
                    f"🎯 <b>Target:</b> <code>{target}</code> ({len(recipient_ids)} recipients)\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━\n"
                    f"{html.escape(text)}\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
                    "<i>Confirm below to dispatch immediately:</i>"
                )
                confirm_keyboard = InlineKeyboardMarkup([
                    [
                        InlineKeyboardButton("🚀 Send Now", callback_data="admin_bcast_confirm"),
                        InlineKeyboardButton("✏️ Re-type", callback_data="admin_bcast_retype")
                    ],
                    [InlineKeyboardButton("❌ Cancel", callback_data="admin_bcast_cancel")]
                ])
                await msg.reply_text(text=preview_card, parse_mode=ParseMode.HTML, reply_markup=confirm_keyboard)
                return

            elif current_state == "AWAITING_CMS_INPUT":
                setting_key = state_data.get("key")
                await clear_admin_state(user_id)

                async with AsyncSessionLocal() as session:
                    setting = await session.get(SystemSetting, setting_key)
                    if not setting:
                        setting = SystemSetting(key=setting_key, value=text)
                        session.add(setting)
                    else:
                        setting.value = text
                    await session.commit()

                label = "About Us" if setting_key == "about_us_text" else "Contact"
                await msg.reply_text(
                    text=f"✅ {html.escape(label)} content updated successfully! Public users will now see this update immediately.",
                    parse_mode=ParseMode.HTML
                )
                return


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Log errors caused by Updates."""
    logger.error("Exception while handling an update: %s", context.error, exc_info=context.error)


def register_handlers(application: Application):
    """Registers command, callback query, message handlers, and global error handler."""
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("admin", admin_command))
    application.add_handler(CommandHandler("cancel", cancel_command))
    application.add_handler(CallbackQueryHandler(handle_callback_query))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_message))
    application.add_error_handler(error_handler)
