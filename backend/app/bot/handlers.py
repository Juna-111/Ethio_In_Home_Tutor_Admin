import asyncio
import html
import logging
from typing import Dict, List, Optional

from sqlalchemy import func, select
from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
    Update,
    WebAppInfo,
)
from telegram.constants import ParseMode
from telegram.error import TelegramError
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from app.bot.bot_instance import format_parent_card, format_tutor_card
from app.bot.topics import get_parent_topic_id
from app.config import settings
from app.database import AsyncSessionLocal
from app.models import ParentRequest, SystemSetting, Tutor
from app.services.matcher import find_top_matches, get_tiered_matches

logger = logging.getLogger("mentorlink.bot.handlers")

# In-memory admin session state (e.g. broadcast wizard, CMS edit)
admin_states: Dict[int, dict] = {}


def is_super_admin(update: Update) -> bool:
    """Checks whether the effective user is the configured SUPER_ADMIN_ID."""
    if not settings.SUPER_ADMIN_ID or not update.effective_user:
        return False
    return update.effective_user.id == settings.SUPER_ADMIN_ID


def get_public_reply_keyboard() -> ReplyKeyboardMarkup:
    """Constructs public reply keyboard safely with WebApp button and customer options."""
    keyboard = []

    # Row 1: Only attach WebApp button if MINI_APP_URL is valid HTTPS
    if settings.MINI_APP_URL and settings.MINI_APP_URL.startswith("https://"):
        keyboard.append([
            KeyboardButton("🚀 Open MentorLink", web_app=WebAppInfo(url=settings.MINI_APP_URL))
        ])
    elif settings.WEBAPP_URL and settings.WEBAPP_URL.startswith("https://"):
        keyboard.append([
            KeyboardButton("🚀 Open MentorLink", web_app=WebAppInfo(url=settings.WEBAPP_URL))
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
        [KeyboardButton("📝 Manage \"About Us\"")]
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

    # Construct public keyboard safely
    keyboard = []

    # Row 1: Only attach WebApp button if MINI_APP_URL is valid HTTPS
    if settings.MINI_APP_URL and settings.MINI_APP_URL.startswith("https://"):
        keyboard.append([
            KeyboardButton("🚀 Open MentorLink", web_app=WebAppInfo(url=settings.MINI_APP_URL))
        ])
    elif settings.WEBAPP_URL and settings.WEBAPP_URL.startswith("https://"):
        keyboard.append([
            KeyboardButton("🚀 Open MentorLink", web_app=WebAppInfo(url=settings.WEBAPP_URL))
        ])

    # Row 2: Customer buttons (ALWAYS present)
    keyboard.append([
        KeyboardButton("ℹ️ About Us"),
        KeyboardButton("📞 Contact")
    ])

    reply_markup = ReplyKeyboardMarkup(
        keyboard,
        resize_keyboard=True,
        is_persistent=True,
        one_time_keyboard=False
    )

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

    if data.startswith("approve_tutor:"):
        await handle_approve_tutor(update, context, data)
    elif data.startswith("reject_tutor:"):
        await handle_reject_tutor(update, context, data)
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
    elif data in ("noop", "assigned"):
        await query.answer("This action has already been processed.")
    else:
        await query.answer("Unrecognized action.")


async def handle_approve_tutor(update: Update, context: ContextTypes.DEFAULT_TYPE, data: str):
    """Approves tutor, updates DB, edits top line in-place, and DMs tutor."""
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

        tutor.status = "verified"
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
                f"🎉 Congratulations, {tutor.full_name}!\n\n"
                "Your MentorLink tutor profile has been approved. "
                "You will now receive student match alerts."
            )
            await context.bot.send_message(chat_id=tutor.telegram_user_id, text=dm_text)
        except Exception as exc:
            logger.warning("Could not send approval DM to tutor %s (tg_id: %s): %s", tutor.full_name, tutor.telegram_user_id, exc)


async def handle_reject_tutor(update: Update, context: ContextTypes.DEFAULT_TYPE, data: str):
    """Rejects tutor, updates DB, edits top line in-place, and DMs tutor."""
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

        tutor.status = "rejected"
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
                f"Hello {tutor.full_name},\n\n"
                "Thank you for your interest in MentorLink. After review, we are unable to approve "
                "your tutor profile at this time. If you have any questions, please contact our support team."
            )
            await context.bot.send_message(chat_id=tutor.telegram_user_id, text=dm_text)
        except Exception as exc:
            logger.warning("Could not send rejection DM to tutor %s: %s", tutor.full_name, exc)


async def handle_close_parent(update: Update, context: ContextTypes.DEFAULT_TYPE, data: str):
    """Closes parent request, updates DB, and edits top line in-place."""
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

        parent_req.status = "closed"
        await session.commit()

    # Dedicated topic auto-closing on completion
    if parent_req.telegram_topic_id and hasattr(context.bot, "close_forum_topic"):
        try:
            await context.bot.close_forum_topic(
                chat_id=settings.ADMIN_GROUP_ID,
                message_thread_id=parent_req.telegram_topic_id
            )
        except Exception as exc:
            logger.warning("Could not close forum topic %s for Request #%s: %s", parent_req.telegram_topic_id, parent_id, exc)

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

    total_matches = len(tiered["tier1"]) + len(tiered["tier2"]) + len(tiered["tier3"])

    # Zero-regression anti-spam: Popup alert for 0 matches
    if total_matches == 0:
        await query.answer(
            text="⚠️ No eligible verified tutors found for this request.",
            show_alert=True
        )
        return

    await query.answer("🎯 Match Radar populated!")

    # Format Tiered Match Radar
    subjects_str = _format_subjects(parent.subjects)
    lines = [
        f"🎯 <b>MATCH RADAR FOR REQUEST #{parent_id}</b>",
        f"📍 {html.escape(parent.location_subcity)} • 📚 {subjects_str} • 💰 {parent.budget_etb:,.2f} ETB/hr",
        "━━━━━━━━━━━━━━━━━━━━━━"
    ]

    all_matched_tutors = []

    # Tier 1: Perfect Fit
    if tiered["tier1"]:
        lines.append("\n🟢 <b>PERFECT FIT</b>")
        for match in tiered["tier1"]:
            t = match["tutor"]
            all_matched_tutors.append(t)
            matched_subs = ", ".join(match.get("matched_subjects", []))
            lines.append(
                f"• <b>{html.escape(t.full_name)}</b> ({html.escape(t.university)} {html.escape(t.department)}, {html.escape(t.education_year)}) — {t.expected_fee_etb:,.0f} ETB/hr | ⭐ {t.years_of_experience:g} yrs\n"
                f"  📍 Base: {html.escape(t.base_subcity)} | 📚 {html.escape(matched_subs)}"
            )

    # Tier 2: Commute / Proximity
    if tiered["tier2"]:
        lines.append("\n🟡 <b>COMMUTE / PROXIMITY</b>")
        for match in tiered["tier2"]:
            t = match["tutor"]
            all_matched_tutors.append(t)
            cov_str = _format_subjects(t.coverage_areas)
            lines.append(
                f"• <b>{html.escape(t.full_name)}</b> ({html.escape(t.university)} {html.escape(t.department)}) — {t.expected_fee_etb:,.0f} ETB/hr | ⭐ {t.years_of_experience:g} yrs\n"
                f"  📍 Covers: {cov_str}"
            )

    # Tier 3: Flexible Alternatives
    if tiered["tier3"]:
        lines.append("\n⚪ <b>FLEX ALTERNATIVES</b>")
        for match in tiered["tier3"]:
            t = match["tutor"]
            all_matched_tutors.append(t)
            note = match.get("flex_note", "Flex match")
            lines.append(
                f"• <b>{html.escape(t.full_name)}</b> — {t.expected_fee_etb:,.0f} ETB/hr ({note})"
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

    if query.message:
        reply_kwargs = {
            "text": "\n".join(lines).strip(),
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
    Deduplicates the button in-place to avoid race conditions and double sends.
    """
    query = update.callback_query
    parent_id_str = data.split(":", 1)[1]

    try:
        parent_id = int(parent_id_str)
    except ValueError:
        await query.answer("Invalid Request ID.")
        return

    # In-place button deduplication
    if query.message and query.message.reply_markup:
        new_keyboard = []
        for row in query.message.reply_markup.inline_keyboard:
            new_row = []
            for btn in row:
                if btn.callback_data and btn.callback_data.startswith("ping_candidates:"):
                    new_row.append(InlineKeyboardButton("⏳ Ping Sent to Top Candidates", callback_data="noop"))
                else:
                    new_row.append(btn)
            new_keyboard.append(new_row)
        try:
            await query.message.edit_reply_markup(reply_markup=InlineKeyboardMarkup(new_keyboard))
        except Exception as exc:
            logger.debug("Failed to update ping button in-place: %s", exc)

    async with AsyncSessionLocal() as session:
        parent, tiered = await get_tiered_matches(parent_id, session)

    if not parent:
        await query.answer(f"Parent request #{parent_id} not found.", show_alert=True)
        return

    all_matched = tiered["tier1"] + tiered["tier2"] + tiered["tier3"]
    tutors_with_tg = [c["tutor"] for c in all_matched if c["tutor"].telegram_user_id][:5]

    if not tutors_with_tg:
        await query.answer("None of the matched tutors have registered Telegram user IDs.", show_alert=True)
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
    for tutor in tutors_with_tg:
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
        except Exception as exc:
            logger.warning("Failed to send ping DM to tutor %s (tg_id: %s): %s", tutor.full_name, tutor.telegram_user_id, exc)

    await query.answer(f"📡 Availability ping dispatched to {sent_count} candidate(s)!")


async def handle_tutor_avail_yes(update: Update, context: ContextTypes.DEFAULT_TYPE, data: str):
    """Handles tutor confirming availability, updates tutor DM, and alerts Admin Group."""
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

    async with AsyncSessionLocal() as session:
        parent = await session.get(ParentRequest, parent_id)
        tutor = await session.get(Tutor, tutor_id)

    if not parent or not tutor:
        await query.answer("Record not found.", show_alert=True)
        return

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
            admin_alert_text = (
                f"🔔 <b>AVAILABILITY CONFIRMED!</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━━━\n"
                f"🧑‍🏫 <b>{html.escape(tutor.full_name)}</b> (<code>{html.escape(tutor.phone_number)}</code>) is available for Request #{parent_id}!\n"
                f"📍 Base: {html.escape(tutor.base_subcity)} | 💰 Rate: {tutor.expected_fee_etb:,.2f} ETB/hr"
            )
            confirm_btn = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton(
                        "🤝 Confirm & Finalize Match",
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
    """Handles tutor declining availability gracefully."""
    query = update.callback_query
    if query.message:
        try:
            await query.message.edit_text(
                text="Thank you for letting us know! We will send you future opportunities that fit your schedule.",
                reply_markup=None
            )
        except Exception as exc:
            logger.debug("Failed to edit tutor DM on avail no: %s", exc)
    await query.answer("Response recorded.")


async def handle_assign_match(update: Update, context: ContextTypes.DEFAULT_TYPE, data: str):
    """Assigns a tutor to a parent request, marks request matched, and notifies tutor."""
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

        parent.status = "matched"
        await session.commit()
        await session.refresh(parent)

    # Dedicated topic auto-closing on completion
    if parent.telegram_topic_id and hasattr(context.bot, "close_forum_topic"):
        try:
            await context.bot.close_forum_topic(
                chat_id=settings.ADMIN_GROUP_ID,
                message_thread_id=parent.telegram_topic_id
            )
        except Exception as exc:
            logger.warning("Could not close forum topic %s for Request #%s: %s", parent.telegram_topic_id, parent.id, exc)

    await query.answer(f"Assigned {tutor.full_name} to Request #{parent_id}!")

    # Lock button on match card and post thread confirmation
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

    # Direct Notification to Parent upon Assignment
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

    # DM tutor with job details
    if tutor.telegram_user_id:
        try:
            landmark = f" ({parent.location_landmark})" if parent.location_landmark else ""
            subjects_str = _format_subjects(parent.subjects)
            days_str = _format_schedule(parent.schedule_days)

            job_alert = (
                f"📢 <b>New Tutoring Opportunity Assigned!</b>\n\n"
                f"Hello {tutor.full_name}, you have been assigned to Parent Request #{parent_id}:\n\n"
                f"👤 <b>Parent:</b> {parent.parent_name}\n"
                f"📞 <b>Contact:</b> {parent.phone_number}\n"
                f"🎓 <b>Student Level:</b> {parent.student_level}\n"
                f"📚 <b>Subjects:</b> {subjects_str}\n"
                f"📍 <b>Location:</b> {parent.location_subcity}{landmark}\n"
                f"📅 <b>Schedule:</b> {days_str} | {parent.time_slot} ({parent.session_duration})\n"
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


async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Direct shortcut command to access the Super Admin Console."""
    msg = update.message or update.effective_message
    if not msg:
        return

    if not is_super_admin(update):
        await msg.reply_text("⛔ Access denied. This console is restricted to the Super Admin.")
        return

    admin_keyboard = get_admin_reply_keyboard()
    await msg.reply_text(
        text="👑 <b>MentorLink — SUPER ADMIN CONSOLE</b>\n\n"
             "Welcome, Super Admin! Select an action from the menu below or tap an inline option.",
        reply_markup=admin_keyboard,
        parse_mode=ParseMode.HTML
    )


async def handle_about_us(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Renders the About Us bio from SystemSetting or default fallback."""
    msg = update.message or update.effective_message
    if not msg:
        return

    async with AsyncSessionLocal() as session:
        setting = await session.get(SystemSetting, "about_us_text")
        bio_text = setting.value if setting and setting.value else None

    if not bio_text:
        bio_text = (
            "🌟 <b>About MentorLink</b>\n\n"
            "MentorLink is Addis Ababa's premier home tutoring network connecting university "
            "scholars and verified educators with students across all grade levels.\n\n"
            "✨ <b>Our Standards:</b>\n"
            "• Rigorous credential & ID verification\n"
            "• University-vetted mentors from top institutions\n"
            "• Tailored matching based on proximity, curriculum & student learning goals"
        )

    await msg.reply_text(bio_text, parse_mode=ParseMode.HTML)


async def handle_support_contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Renders customer support & coordination contact info from SystemSetting or fallback."""
    msg = update.message or update.effective_message
    if not msg:
        return

    async with AsyncSessionLocal() as session:
        setting = await session.get(SystemSetting, "support_contact")
        contact_text = setting.value if setting and setting.value else None

    if not contact_text:
        contact_text = (
            "📞 <b>Support & Coordination</b>\n\n"
            "Need help finding a mentor or have questions about our tutoring programs?\n\n"
            "💬 <b>Telegram:</b> @MentorLinkSupport\n"
            "📱 <b>Phone:</b> +251 91 100 2233\n"
            "🕒 <b>Hours:</b> Mon – Sat, 8:30 AM – 6:30 PM (EAT)\n"
            "📍 Addis Ababa, Ethiopia"
        )

    await msg.reply_text(contact_text, parse_mode=ParseMode.HTML)


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
        await msg.reply_text("⛔ Restricted to Super Admin.")
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
        await msg.reply_text("⛔ Restricted to Super Admin.")
        return

    await msg.reply_text(
        "📢 <b>Segmented Broadcast Dispatcher</b>\n\n"
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
    admin_states[admin_id] = {
        "state": "AWAITING_BROADCAST_TEXT",
        "target": target
    }

    target_labels = {
        "all": "👥 All Users",
        "tutors_verified": "🧑‍🏫 Verified Tutors",
        "tutors_pending": "⏳ Pending Tutors",
        "parents": "📋 Parents Only"
    }

    await query.message.edit_text(
        f"Target selected: <b>{target_labels.get(target, target)}</b>\n\n"
        "✍️ Please send the broadcast announcement message now.\n"
        "<i>(HTML formatting is supported: &lt;b&gt;, &lt;i&gt;, &lt;code&gt;, links)</i>",
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("❌ Cancel", callback_data="admin_bcast_cancel")]
        ])
    )
    await query.answer()


async def handle_bcast_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    admin_id = update.effective_user.id
    if not is_super_admin(update):
        await query.answer("⛔ Access denied.", show_alert=True)
        return

    state_data = admin_states.pop(admin_id, None)
    if not state_data or state_data.get("state") != "AWAITING_BROADCAST_CONFIRM":
        await query.answer("No broadcast awaiting confirmation.", show_alert=True)
        return

    target = state_data["target"]
    message_text = state_data["text"]
    recipient_ids = await get_broadcast_recipient_ids(target)

    await query.message.edit_text(
        f"⏳ Dispatching broadcast to {len(recipient_ids)} recipients at rate ~25 msg/s...",
        reply_markup=None
    )

    success_count = 0
    fail_count = 0

    for uid in recipient_ids:
        try:
            await context.bot.send_message(
                chat_id=uid,
                text=message_text,
                parse_mode=ParseMode.HTML
            )
            success_count += 1
        except Exception:
            # Fallback to plain text on formatting error
            try:
                await context.bot.send_message(
                    chat_id=uid,
                    text=message_text
                )
                success_count += 1
            except Exception as exc:
                logger.warning("Failed to send broadcast to user %s: %s", uid, exc)
                fail_count += 1
        await asyncio.sleep(0.04)

    await query.message.reply_text(
        f"✅ <b>Broadcast Completed!</b>\n\n"
        f"• Sent: {success_count}\n"
        f"• Failed/Blocked: {fail_count}\n"
        f"• Total Audience: {len(recipient_ids)}",
        parse_mode=ParseMode.HTML
    )
    await query.answer()


async def handle_bcast_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    admin_id = update.effective_user.id
    admin_states.pop(admin_id, None)
    await query.message.edit_text("❌ Broadcast cancelled.")
    await query.answer("Cancelled.")


async def handle_bcast_retype(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    admin_id = update.effective_user.id
    state_data = admin_states.get(admin_id)
    if state_data:
        state_data["state"] = "AWAITING_BROADCAST_TEXT"
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
        await msg.reply_text("⛔ Restricted to Super Admin.")
        return

    await msg.reply_text(
        "📝 <b>Content Management (CMS)</b>\n\n"
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
        f"📄 <b>Current content for <code>{setting_key}</code>:</b>\n\n{current_val}",
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
    admin_states[admin_id] = {
        "state": "AWAITING_CMS_INPUT",
        "key": setting_key
    }

    label = "About Us" if setting_key == "about_us_text" else "Contact"

    async with AsyncSessionLocal() as session:
        setting = await session.get(SystemSetting, setting_key)
        current_val = setting.value if setting and setting.value else "(Default platform copy)"

    await query.message.edit_text(
        f"✏️ <b>Edit Content — {label}</b>\n\n"
        f"<b>Current Content:</b>\n"
        f"<blockquote>{current_val}</blockquote>\n"
        f"✍️ Please send the new text for <b>{label}</b> now:\n"
        "<i>(HTML formatting is supported: &lt;b&gt;, &lt;i&gt;, &lt;code&gt;, links)</i>",
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("↩️ Keep Existing / Cancel", callback_data="admin_cms_cancel")]
        ])
    )
    await query.answer()


async def handle_cms_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    admin_id = update.effective_user.id
    admin_states.pop(admin_id, None)
    await query.message.edit_text("↩️ CMS editing cancelled. Existing content preserved.")
    await query.answer("Cancelled.")


async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Allows Super Admin to cancel any active broadcast wizard or CMS edit session."""
    msg = update.message or update.effective_message
    user_id = update.effective_user.id if update.effective_user else None
    if user_id and user_id in admin_states:
        admin_states.pop(user_id, None)
        if msg:
            await msg.reply_text("❌ Action cancelled. Returned to main menu.")
    else:
        if msg:
            await msg.reply_text("ℹ️ No active action to cancel.")


async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Processes incoming non-command text messages for keyboard buttons & admin wizard states."""
    msg = update.message or update.effective_message
    if not msg or not msg.text:
        return

    text = msg.text.strip()
    user_id = update.effective_user.id if update.effective_user else None

    # Cancel escape
    if text.lower() in ("/cancel", "cancel"):
        if user_id and user_id in admin_states:
            admin_states.pop(user_id, None)
            await msg.reply_text("❌ Action cancelled. Returned to main menu.")
            return

    # Public Reply Keyboard buttons
    if text == "ℹ️ About Us":
        if user_id in admin_states:
            admin_states.pop(user_id, None)
        await handle_about_us(update, context)
        return
    elif text == "📞 Contact":
        if user_id in admin_states:
            admin_states.pop(user_id, None)
        await handle_support_contact(update, context)
        return

    # Super Admin Reply Keyboard buttons
    if is_super_admin(update):
        if text in ("📊 Analytics", "📢 Broadcast", "📝 Manage \"About Us\"", "📝 Manage 'About Us'"):
            admin_states.pop(user_id, None)

        if text == "📊 Analytics":
            await handle_admin_analytics(update, context)
            return
        elif text == "📢 Broadcast":
            await handle_broadcast_menu(update, context)
            return
        elif text in ("📝 Manage \"About Us\"", "📝 Manage 'About Us'"):
            await handle_cms_menu(update, context)
            return

    # Super Admin Interactive Wizard States
    if user_id and user_id in admin_states and is_super_admin(update):
        state_data = admin_states[user_id]
        current_state = state_data.get("state")

        if current_state == "AWAITING_BROADCAST_TEXT":
            state_data["text"] = text
            state_data["state"] = "AWAITING_BROADCAST_CONFIRM"
            target = state_data.get("target", "all")
            recipient_ids = await get_broadcast_recipient_ids(target)

            preview_card = (
                "📢 <b>BROADCAST PREVIEW</b>\n\n"
                f"🎯 <b>Target:</b> <code>{target}</code> ({len(recipient_ids)} recipients)\n"
                f"━━━━━━━━━━━━━━━━━━━━━━\n"
                f"{text}\n"
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
            await msg.reply_text(preview_card, parse_mode=ParseMode.HTML, reply_markup=confirm_keyboard)
            return

        elif current_state == "AWAITING_CMS_INPUT":
            setting_key = state_data.get("key")
            admin_states.pop(user_id, None)

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
                f"✅ <b>{label}</b> content updated successfully! Public users will now see this update immediately.",
                parse_mode=ParseMode.HTML
            )
            return


def register_handlers(application: Application):
    """Registers command, callback query, and message handlers on the Telegram application."""
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("admin", admin_command))
    application.add_handler(CommandHandler("cancel", cancel_command))
    application.add_handler(CallbackQueryHandler(handle_callback_query))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_message))
