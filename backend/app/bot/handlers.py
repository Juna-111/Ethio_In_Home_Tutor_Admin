import html
import logging
from typing import Optional

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes

from app.database import AsyncSessionLocal
from app.models import ParentRequest, Tutor
from app.services.matcher import find_top_matches

logger = logging.getLogger("mentorlink.bot.handlers")


def _get_admin_name(update: Update) -> str:
    user = update.effective_user
    if not user:
        return "@admin"
    if user.username:
        return f"@{user.username}"
    return user.first_name or "Admin"


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
    """Main callback router for admin inline keyboard button presses."""
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

    # In-place top line update: 🧑‍🏫 <b>TUTOR PROFILE #{id}</b> • 🟢 <b>Approved by @{admin}</b>
    if query.message:
        try:
            curr_text = query.message.text or ""
            new_header = f"🧑‍🏫 <b>TUTOR PROFILE #{tutor_id}</b> • 🟢 <b>Approved by {admin_name}</b>"
            updated_text = _replace_card_header(curr_text, new_header)
            await query.message.edit_text(
                text=updated_text,
                parse_mode=ParseMode.HTML,
                reply_markup=None  # Remove all inline buttons
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

    # In-place top line update: 🧑‍🏫 <b>TUTOR PROFILE #{id}</b> • 🔴 <b>Rejected by @{admin}</b>
    if query.message:
        try:
            curr_text = query.message.text or ""
            new_header = f"🧑‍🏫 <b>TUTOR PROFILE #{tutor_id}</b> • 🔴 <b>Rejected by {admin_name}</b>"
            updated_text = _replace_card_header(curr_text, new_header)
            await query.message.edit_text(
                text=updated_text,
                parse_mode=ParseMode.HTML,
                reply_markup=None  # Remove all inline buttons
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

    # In-place top line update: 📋 <b>PARENT REQUEST #{id}</b> • ⚪ <b>Closed by @{admin}</b>
    if query.message:
        try:
            curr_text = query.message.text or ""
            new_header = f"📋 <b>PARENT REQUEST #{parent_id}</b> • ⚪ <b>Closed by {admin_name}</b>"
            updated_text = _replace_card_header(curr_text, new_header)
            await query.message.edit_text(
                text=updated_text,
                parse_mode=ParseMode.HTML,
                reply_markup=None  # Remove all inline buttons
            )
        except Exception as exc:
            logger.error("Failed to edit parent card for #%s: %s", parent_id, exc)


async def handle_match_parent(update: Update, context: ContextTypes.DEFAULT_TYPE, data: str):
    """
    Runs the tiered matching engine for a parent request.
    If 0 matches: triggers native Telegram popup modal (zero chat spam).
    If matches exist: posts a single consolidated summary card with assign buttons in topic thread.
    """
    query = update.callback_query
    parent_id_str = data.split(":", 1)[1]

    try:
        parent_id = int(parent_id_str)
    except ValueError:
        await query.answer("Invalid Request ID.")
        return

    async with AsyncSessionLocal() as session:
        parent, top_matches = await find_top_matches(parent_id, session)

    if not parent:
        await query.answer(f"Parent Request #{parent_id} not found.", show_alert=True)
        return

    # Popup Alert for Zero Matches (Zero Chat Spam)
    if not top_matches:
        await query.answer(
            text="⚠️ No eligible verified tutors found for this location/subject combination.",
            show_alert=True
        )
        return

    await query.answer("Found top matching tutors!")

    # Single-Card Compact Match Summary
    num_emojis = ["1️⃣", "2️⃣", "3️⃣"]
    summary_lines = [
        f"🎯 <b>TOP MATCHES FOR REQUEST #{parent_id}</b>",
        "━━━━━━━━━━━━━━━━━━━━━━"
    ]
    keyboard_buttons = []

    for idx, match in enumerate(top_matches, start=1):
        tutor = match["tutor"]
        score = match["match_score"]
        matched_str = ", ".join(match["matched_subjects"])
        emoji = num_emojis[idx - 1] if idx <= len(num_emojis) else f"{idx}️⃣"
        first_name = tutor.full_name.split()[0] if tutor.full_name else "Tutor"

        summary_lines.append(
            f"{emoji} <b>{html.escape(tutor.full_name)}</b> ({score:.0f}% Match)\n"
            f"   🎓 {html.escape(tutor.university)} ({html.escape(tutor.department)})\n"
            f"   📍 Base: {html.escape(tutor.base_subcity)} | ⭐ {tutor.years_of_experience:g} yrs | 💰 {tutor.expected_fee_etb:,.2f} ETB\n"
            f"   📚 Matched: {html.escape(matched_str)}\n"
        )

        keyboard_buttons.append([
            InlineKeyboardButton(
                f"📲 Assign {idx}. {first_name}",
                callback_data=f"assign_match:{parent_id}:{tutor.id}"
            )
        ])

    single_card_text = "\n".join(summary_lines).strip()
    keyboard = InlineKeyboardMarkup(keyboard_buttons)

    if query.message:
        reply_kwargs = {
            "text": single_card_text,
            "parse_mode": ParseMode.HTML,
            "reply_markup": keyboard,
            "reply_to_message_id": query.message.message_id
        }
        # Preserve thread context in Telegram Supergroups with Topics enabled
        thread_id = getattr(query.message, "message_thread_id", None)
        if thread_id:
            reply_kwargs["message_thread_id"] = thread_id

        await query.message.reply_text(**reply_kwargs)


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
            subjects_str = ", ".join(parent.subjects) if isinstance(parent.subjects, list) else str(parent.subjects)
            days_str = ", ".join(parent.schedule_days) if isinstance(parent.schedule_days, list) else str(parent.schedule_days)

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
