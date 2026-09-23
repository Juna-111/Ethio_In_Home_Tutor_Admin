import html
import logging
import re
from typing import Optional

from sqlalchemy import select
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


def _update_card_status(text: str, new_status_line: str) -> str:
    """Replaces or appends status line in an admin card text."""
    lines = text.split("\n")
    updated = False
    new_lines = []
    for line in lines:
        if "Status:" in line:
            new_lines.append(new_status_line)
            updated = True
        else:
            new_lines.append(line)
    if not updated:
        new_lines.append(new_status_line)
    return "\n".join(new_lines)


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
    """Approves tutor, updates DB, updates admin card, and DMs tutor."""
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

    # Update admin card message
    if query.message:
        try:
            curr_text = query.message.text or ""
            new_status_line = f"📊 Status: ✅ Approved by {admin_name}"
            updated_text = _update_card_status(curr_text, new_status_line)
            await query.message.edit_text(
                text=updated_text,
                reply_markup=None  # Remove buttons to prevent duplicate actions
            )
        except Exception as exc:
            logger.error("Failed to edit tutor card for #%s: %s", tutor_id, exc)

    # DM tutor if telegram_user_id is available
    if tutor.telegram_user_id:
        try:
            dm_text = (
                f"🎉 Congratulations, {tutor.full_name}!\n\n"
                "Your MentorLink tutor profile has been verified and approved. "
                "You are now eligible to receive student matching alerts!"
            )
            await context.bot.send_message(chat_id=tutor.telegram_user_id, text=dm_text)
        except Exception as exc:
            logger.warning("Could not send approval DM to tutor %s (tg_id: %s): %s", tutor.full_name, tutor.telegram_user_id, exc)


async def handle_reject_tutor(update: Update, context: ContextTypes.DEFAULT_TYPE, data: str):
    """Rejects tutor, updates DB, updates admin card, and DMs tutor."""
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

    # Update admin card message
    if query.message:
        try:
            curr_text = query.message.text or ""
            new_status_line = f"📊 Status: ❌ Rejected by {admin_name}"
            updated_text = _update_card_status(curr_text, new_status_line)
            await query.message.edit_text(
                text=updated_text,
                reply_markup=None
            )
        except Exception as exc:
            logger.error("Failed to edit tutor card for #%s: %s", tutor_id, exc)

    # DM tutor if telegram_user_id is available
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
    """Closes parent request, updates DB, and updates admin card."""
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

    if query.message:
        try:
            curr_text = query.message.text or ""
            new_status_line = f"📊 Status: ❌ Closed by {admin_name}"
            updated_text = _update_card_status(curr_text, new_status_line)
            await query.message.edit_text(
                text=updated_text,
                reply_markup=None
            )
        except Exception as exc:
            logger.error("Failed to edit parent card for #%s: %s", parent_id, exc)


async def handle_match_parent(update: Update, context: ContextTypes.DEFAULT_TYPE, data: str):
    """Runs the matching engine for a parent request and replies in thread with top candidates."""
    query = update.callback_query
    parent_id_str = data.split(":", 1)[1]

    try:
        parent_id = int(parent_id_str)
    except ValueError:
        await query.answer("Invalid Request ID.")
        return

    await query.answer("Finding best matches...")

    async with AsyncSessionLocal() as session:
        parent, top_matches = await find_top_matches(parent_id, session)

    if not parent:
        if query.message:
            await query.message.reply_text(f"❌ Parent Request #{parent_id} was not found in database.")
        return

    if not top_matches:
        if query.message:
            await query.message.reply_text(
                f"⚠️ No verified tutors currently match all criteria (Subject/Location/Gender) for Request #{parent_id}."
            )
        return

    # Send matching results
    num_emojis = ["1️⃣", "2️⃣", "3️⃣"]
    for idx, match in enumerate(top_matches):
        tutor = match["tutor"]
        matched_subjs = ", ".join(match["matched_subjects"])
        emoji = num_emojis[idx] if idx < len(num_emojis) else f"{idx + 1}️⃣"

        card = (
            f"🎯 <b>MATCH RESULT FOR REQUEST #{parent_id}</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"{emoji} <b>{html.escape(tutor.full_name)}</b> ({html.escape(tutor.gender)})\n"
            f"🏛 <b>Uni:</b> {html.escape(tutor.university)} - {html.escape(tutor.department)}\n"
            f"📍 <b>Base:</b> {html.escape(tutor.base_subcity)} | ⭐ <b>Exp:</b> {tutor.years_of_experience:g} yrs\n"
            f"💵 <b>Rate:</b> {tutor.expected_fee_etb:,.2f} ETB\n"
            f"📚 <b>Matches:</b> {html.escape(matched_subjs)}\n"
            f"📞 <b>Phone:</b> {html.escape(tutor.phone_number)}"
        )

        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton(
                    f"📲 Assign Tutor",
                    callback_data=f"assign_match:{parent_id}:{tutor.id}"
                )
            ]
        ])

        if query.message:
            await query.message.reply_text(
                text=card,
                parse_mode=ParseMode.HTML,
                reply_markup=keyboard
            )


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

    # Update button on the match message to show assigned
    if query.message:
        try:
            await query.message.edit_reply_markup(
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton(f"✅ Assigned to @{admin_name.lstrip('@')}", callback_data="assigned")]
                ])
            )
            await query.message.reply_text(
                f"✅ Successfully assigned <b>{html.escape(tutor.full_name)}</b> to Parent Request #{parent_id} by {admin_name}.",
                parse_mode=ParseMode.HTML
            )
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
