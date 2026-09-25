from unittest.mock import AsyncMock, MagicMock
import pytest
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from telegram.error import TelegramError

from app.bot.topics import (
    TOPIC_CACHE,
    ensure_forum_topics,
    get_parent_topic_id,
    get_tutor_topic_id
)
from app.config import settings
from app.models import SystemSetting
from tests.conftest import TestingSessionLocal


@pytest.mark.asyncio
async def test_ensure_forum_topics_creates_and_persists_new_topics(db_session: AsyncSession, monkeypatch):
    """Verifies that on first startup, topics are created via Telegram API and stored in system_settings."""
    # Ensure empty settings and clean cache
    await db_session.execute(delete(SystemSetting))
    await db_session.commit()
    TOPIC_CACHE["parent_requests_topic_id"] = None
    TOPIC_CACHE["tutor_verifications_topic_id"] = None

    monkeypatch.setattr(settings, "ADMIN_GROUP_ID", -1001234567890)
    monkeypatch.setattr(settings, "PARENT_REQUESTS_TOPIC_ID", None)
    monkeypatch.setattr(settings, "TUTOR_REGISTRATION_TOPIC_ID", None)

    # Mock Telegram Bot create_forum_topic
    async def mock_create_topic(chat_id, name, **kwargs):
        if "Parent" in name:
            return MagicMock(message_thread_id=501)
        return MagicMock(message_thread_id=502)

    mock_bot = MagicMock()
    mock_bot.create_forum_topic = AsyncMock(side_effect=mock_create_topic)

    await ensure_forum_topics(mock_bot, TestingSessionLocal)

    # Verify Telegram API was called for both topics
    assert mock_bot.create_forum_topic.call_count == 2

    # Verify runtime getters return created IDs
    assert get_parent_topic_id() == 501
    assert get_tutor_topic_id() == 502

    # Verify persisted in database
    res = await db_session.execute(select(SystemSetting))
    db_items = {s.key: s.value for s in res.scalars().all()}
    assert db_items["parent_requests_topic_id"] == "501"
    assert db_items["tutor_verifications_topic_id"] == "502"


@pytest.mark.asyncio
async def test_ensure_forum_topics_loads_from_db_without_calling_telegram_again(monkeypatch):
    """Verifies that on restart, topics are loaded from system_settings without re-calling Telegram API."""
    TOPIC_CACHE["parent_requests_topic_id"] = None
    TOPIC_CACHE["tutor_verifications_topic_id"] = None

    # Seed DB with existing topic settings from previous run
    async with TestingSessionLocal() as session:
        session.add(SystemSetting(key="parent_requests_topic_id", value="501"))
        session.add(SystemSetting(key="tutor_verifications_topic_id", value="502"))
        await session.commit()

    monkeypatch.setattr(settings, "ADMIN_GROUP_ID", -1001234567890)
    monkeypatch.setattr(settings, "PARENT_REQUESTS_TOPIC_ID", None)
    monkeypatch.setattr(settings, "TUTOR_REGISTRATION_TOPIC_ID", None)

    mock_bot = MagicMock()
    mock_bot.create_forum_topic = AsyncMock()

    await ensure_forum_topics(mock_bot, TestingSessionLocal)

    # Since already in DB, Telegram API should NOT be called
    assert not mock_bot.create_forum_topic.called
    assert get_parent_topic_id() == 501
    assert get_tutor_topic_id() == 502


@pytest.mark.asyncio
async def test_ensure_forum_topics_graceful_fallback_when_topics_not_enabled(db_session: AsyncSession, monkeypatch):
    """Verifies that if topics are disabled or permissions are missing, it falls back cleanly to None without crashing."""
    await db_session.execute(delete(SystemSetting))
    await db_session.commit()
    TOPIC_CACHE["parent_requests_topic_id"] = None
    TOPIC_CACHE["tutor_verifications_topic_id"] = None

    monkeypatch.setattr(settings, "ADMIN_GROUP_ID", -1001234567890)
    monkeypatch.setattr(settings, "PARENT_REQUESTS_TOPIC_ID", None)
    monkeypatch.setattr(settings, "TUTOR_REGISTRATION_TOPIC_ID", None)

    mock_bot = MagicMock()
    mock_bot.create_forum_topic = AsyncMock(side_effect=TelegramError("Chat is not a forum or missing rights"))

    # Must not raise an exception
    await ensure_forum_topics(mock_bot, TestingSessionLocal)

    assert get_parent_topic_id() is None
    assert get_tutor_topic_id() is None
