import logging
from telegram import Update
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes

logger = logging.getLogger("mentorlink.bot.handlers")


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Replies to /start command."""
    if update.effective_message:
        await update.effective_message.reply_text(
            "👋 Welcome to MentorLink Admin & Notification Bot!\n\n"
            "This bot forwards incoming tutoring requests and registrations to the Admin Group."
        )


async def placeholder_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Temporary handler acknowledging button clicks in Phase 2.
    Full action execution (approval, rejection, matching) is executed in Phase 3.
    """
    query = update.callback_query
    if not query:
        return
    
    await query.answer(f"Action received: {query.data}. Processing...")
    logger.info("Admin callback clicked: %s by user %s", query.data, query.from_user.id)


def register_handlers(application: Application):
    """Registers command and callback query handlers on the Telegram application."""
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CallbackQueryHandler(placeholder_callback_handler))
