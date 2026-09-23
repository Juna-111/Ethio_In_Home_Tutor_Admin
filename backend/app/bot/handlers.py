import html
import logging
from typing import Optional

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes

from app.bot.topics import get_parent_topic_id
from app.config import settings
from app.database import AsyncSessionLocal
from app.models import ParentRequest, Tutor
from app.services.matcher import find_top_matches, get_tiered_matches

logger = logging.getLogger("mentorlink.bot.handlers")


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
    """Replies to /start command."""
    if update.effective_message:
        await update.effective_message.reply_text(
            "👋 Welcome to MentorLink!\n\n"
            "This bot powers notifications and admin matching for Ethiopian In-Home Tutors & Parents."
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

    # In-place top line update
    if query.message:
        try:
            curr_text = query.message.text or ""
            new_header = f"🧑‍🏫 <b>TUTOR PROFILE #{tutor_id}</b> • 🟢 <b>Approved by {admin_name}</b>"
            updated_text = _replace_card_header(curr_text, new_header)
            await query.message.edit_text(
                text=updated_text,
                parse_mode=ParseMode.HTML,
                reply_markup=None
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

    # In-place top line update
    if query.message:
        try:
            curr_text = query.message.text or ""
            new_header = f"🧑‍🏫 <b>TUTOR PROFILE #{tutor_id}</b> • 🔴 <b>Rejected by {admin_name}</b>"
            updated_text = _replace_card_header(curr_text, new_header)
            await query.message.edit_text(
                text=updated_text,
                parse_mode=ParseMode.HTML,
                reply_markup=None
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

    await query.answer(f"Request #{parent_id} closed.")

    # In-place top line update
    if query.message:
        try:
            curr_text = query.message.text or ""
            new_header = f"📋 <b>PARENT REQUEST #{parent_id}</b> • ⚪ <b>Closed by {admin_name}</b>"
            updated_text = _replace_card_header(curr_text, new_header)
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
            topic_id = get_parent_topic_id()
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
            thread_id = getattr(query.message, "message_thread_id", None)
            if thread_id:
                assign_reply_kwargs["message_thread_id"] = thread_id

            await query.message.reply_text(**assign_reply_kwargs)
        except Exception as exc:
            logger.error("Error updating match assignment message: %s", exc)

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


def register_handlers(application: Application):
    """Registers command and callback query handlers on the Telegram application."""
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CallbackQueryHandler(handle_callback_query))
