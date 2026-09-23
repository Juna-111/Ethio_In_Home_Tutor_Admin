import logging
from typing import Optional
from sqlalchemy import select
from telegram import Bot
from telegram.error import TelegramError

from app.config import settings
from app.models import SystemSetting

logger = logging.getLogger("mentorlink.bot.topics")

# In-memory runtime cache for verified topic thread IDs
TOPIC_CACHE = {
    "parent_requests_topic_id": None,
    "tutor_verifications_topic_id": None
}


def get_parent_topic_id() -> Optional[int]:
    """Returns manual override from settings if present, otherwise returns cached auto-created topic ID."""
    if settings.PARENT_REQUESTS_TOPIC_ID is not None:
        return settings.PARENT_REQUESTS_TOPIC_ID
    return TOPIC_CACHE.get("parent_requests_topic_id")


def get_tutor_topic_id() -> Optional[int]:
    """Returns manual override from settings if present, otherwise returns cached auto-created topic ID."""
    if settings.TUTOR_REGISTRATION_TOPIC_ID is not None:
        return settings.TUTOR_REGISTRATION_TOPIC_ID
    return TOPIC_CACHE.get("tutor_verifications_topic_id")


async def ensure_forum_topics(bot: Optional[Bot], session_factory) -> None:
    """
    Checks database for existing topic IDs or creates dedicated forum topics
    ('📥 Parent Requests' and '🧑‍🏫 Tutor Profiles') in the Admin Group on startup.
    Gracefully falls back to main chat if forum topics are not enabled or permissions are missing.
    """
    if not bot or not settings.ADMIN_GROUP_ID:
        logger.debug("Bot or ADMIN_GROUP_ID not configured; skipping forum topics check.")
        return

    # If both are manually configured in .env, no need to auto-create
    if settings.PARENT_REQUESTS_TOPIC_ID and settings.TUTOR_REGISTRATION_TOPIC_ID:
        logger.info("Topic IDs provided via environment variables. Skipping automatic creation.")
        return

    try:
        async with session_factory() as session:
            # Query existing settings
            stmt = select(SystemSetting).where(
                SystemSetting.key.in_(["parent_requests_topic_id", "tutor_verifications_topic_id"])
            )
            result = await session.execute(stmt)
            saved_settings = {s.key: s.value for s in result.scalars().all()}

            # 1. Parent Requests Topic
            if "parent_requests_topic_id" in saved_settings:
                try:
                    TOPIC_CACHE["parent_requests_topic_id"] = int(saved_settings["parent_requests_topic_id"])
                    logger.info("Loaded cached Parent Requests topic ID: %s", TOPIC_CACHE["parent_requests_topic_id"])
                except ValueError:
                    TOPIC_CACHE["parent_requests_topic_id"] = None
            elif settings.PARENT_REQUESTS_TOPIC_ID is None:
                try:
                    topic = await bot.create_forum_topic(
                        chat_id=settings.ADMIN_GROUP_ID,
                        name="📥 Parent Requests"
                    )
                    thread_id = topic.message_thread_id
                    TOPIC_CACHE["parent_requests_topic_id"] = thread_id
                    session.add(SystemSetting(key="parent_requests_topic_id", value=str(thread_id)))
                    await session.commit()
                    logger.info("Auto-created forum topic '📥 Parent Requests' with ID: %s", thread_id)
                except (TelegramError, Exception) as exc:
                    logger.info("Forum topics not active or permission missing for Parent Requests; defaulting to main chat (%s)", exc)

            # 2. Tutor Verifications Topic
            if "tutor_verifications_topic_id" in saved_settings:
                try:
                    TOPIC_CACHE["tutor_verifications_topic_id"] = int(saved_settings["tutor_verifications_topic_id"])
                    logger.info("Loaded cached Tutor Verifications topic ID: %s", TOPIC_CACHE["tutor_verifications_topic_id"])
                except ValueError:
                    TOPIC_CACHE["tutor_verifications_topic_id"] = None
            elif settings.TUTOR_REGISTRATION_TOPIC_ID is None:
                try:
                    topic = await bot.create_forum_topic(
                        chat_id=settings.ADMIN_GROUP_ID,
                        name="🧑‍🏫 Tutor Profiles"
                    )
                    thread_id = topic.message_thread_id
                    TOPIC_CACHE["tutor_verifications_topic_id"] = thread_id
                    session.add(SystemSetting(key="tutor_verifications_topic_id", value=str(thread_id)))
                    await session.commit()
                    logger.info("Auto-created forum topic '🧑‍🏫 Tutor Profiles' with ID: %s", thread_id)
                except (TelegramError, Exception) as exc:
                    logger.info("Forum topics not active or permission missing for Tutor Profiles; defaulting to main chat (%s)", exc)

    except Exception as exc:
        logger.warning("Error while checking or provisioning forum topics: %s", exc)
