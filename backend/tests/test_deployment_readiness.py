"""Tests for failure modes that unit tests normally miss because they never behave like a browser.

Background: the admin Mini App showed "Network connection error" on every click even though
the whole suite was green. The suite calls the API directly (no CORS enforcement, schema built
by ``create_all``), so it could not see:
  * PATCH/DELETE being rejected at the CORS preflight,
  * unhandled 500s being returned without CORS headers (browser reports a network error),
  * a database that is behind the deployed migrations,
  * "Review in App" buttons silently disappearing when MINI_APP_URL is a web URL,
  * a publicly known default cron secret.
"""

from unittest.mock import MagicMock

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.main import app

ALLOWED_ORIGIN = "https://web.telegram.org"


def _preflight_headers(method: str, origin: str = ALLOWED_ORIGIN) -> dict:
    return {
        "Origin": origin,
        "Access-Control-Request-Method": method,
        "Access-Control-Request-Headers": "authorization,content-type",
    }


# --------------------------------------------------------------------------
# CORS
# --------------------------------------------------------------------------

@pytest.mark.asyncio
@pytest.mark.parametrize("method,path", [
    ("PATCH", "/api/v1/admin/tutors/1/verification"),
    ("PATCH", "/api/v1/admin/incidents/1"),
    ("DELETE", "/api/v1/admin/admins/123"),
    ("POST", "/api/v1/admin/requests/1/assign"),
    ("GET", "/api/v1/admin/dashboard"),
])
async def test_cors_preflight_allows_every_method_the_admin_app_uses(async_client: AsyncClient, method, path):
    response = await async_client.options(path, headers=_preflight_headers(method))

    assert response.status_code == 200, response.text
    allowed = [m.strip() for m in response.headers["access-control-allow-methods"].split(",")]
    assert method in allowed
    assert response.headers["access-control-allow-origin"] == ALLOWED_ORIGIN


@pytest.mark.asyncio
async def test_cors_preflight_rejects_unknown_origin(async_client: AsyncClient):
    response = await async_client.options(
        "/api/v1/admin/dashboard",
        headers=_preflight_headers("GET", origin="https://evil.example.com"),
    )

    assert response.status_code == 400
    assert "access-control-allow-origin" not in response.headers


# --------------------------------------------------------------------------
# Unhandled errors must stay readable in the browser
# --------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_unhandled_exception_returns_json_with_cors_headers():
    async def boom():
        raise RuntimeError("simulated crash")

    app.add_api_route("/api/v1/__boom", boom, methods=["GET"])
    try:
        transport = ASGITransport(app=app, raise_app_exceptions=False)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            response = await client.get("/api/v1/__boom", headers={"Origin": ALLOWED_ORIGIN})
    finally:
        app.router.routes = [r for r in app.router.routes if getattr(r, "path", None) != "/api/v1/__boom"]

    assert response.status_code == 500
    body = response.json()
    assert body["detail"].startswith("Internal server error. Reference: ")
    assert body["detail"].endswith(response.headers["x-request-id"])
    # Without these the browser hides the 500 behind a generic network error.
    assert response.headers["access-control-allow-origin"] == ALLOWED_ORIGIN
    assert "simulated crash" not in response.text  # never leak internals to the client


@pytest.mark.asyncio
async def test_unhandled_exception_does_not_grant_cors_to_unknown_origin():
    async def boom():
        raise RuntimeError("simulated crash")

    app.add_api_route("/api/v1/__boom", boom, methods=["GET"])
    try:
        transport = ASGITransport(app=app, raise_app_exceptions=False)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            response = await client.get("/api/v1/__boom", headers={"Origin": "https://evil.example.com"})
    finally:
        app.router.routes = [r for r in app.router.routes if getattr(r, "path", None) != "/api/v1/__boom"]

    assert response.status_code == 500
    assert "access-control-allow-origin" not in response.headers


# --------------------------------------------------------------------------
# Health reports migration state
# --------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_health_reports_untracked_when_no_alembic_table(async_client: AsyncClient):
    response = await async_client.get("/api/v1/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "healthy"
    assert body["schema_state"] == "untracked"


@pytest.mark.asyncio
async def test_health_reports_degraded_when_database_is_behind_migrations(
    async_client: AsyncClient, db_session: AsyncSession
):
    await db_session.execute(text("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL)"))
    await db_session.execute(text("INSERT INTO alembic_version (version_num) VALUES ('20260925_01')"))
    await db_session.commit()
    try:
        response = await async_client.get("/api/v1/health")
    finally:
        await db_session.execute(text("DROP TABLE alembic_version"))
        await db_session.commit()

    assert response.status_code == 200  # keep the instance up; just make the problem visible
    body = response.json()
    assert body["status"] == "degraded"
    assert body["schema_state"] == "behind"
    assert body["migration_current"] == "20260925_01"
    assert body["migration_head"]
    assert "alembic upgrade head" in body["detail"]


@pytest.mark.asyncio
async def test_health_reports_current_when_database_matches_head(
    async_client: AsyncClient, db_session: AsyncSession
):
    from app.services.schema_check import get_migration_head

    head = get_migration_head()
    assert head, "migration scripts should be readable from the backend directory"
    await db_session.execute(text("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL)"))
    await db_session.execute(text("INSERT INTO alembic_version (version_num) VALUES (:v)"), {"v": head})
    await db_session.commit()
    try:
        response = await async_client.get("/api/v1/health")
    finally:
        await db_session.execute(text("DROP TABLE alembic_version"))
        await db_session.commit()

    body = response.json()
    assert body["status"] == "healthy"
    assert body["schema_state"] == "current"
    assert body["migration_current"] == head


# --------------------------------------------------------------------------
# "Review in App" deep links
# --------------------------------------------------------------------------

def test_review_url_uses_configured_t_me_link(monkeypatch):
    import app.bot.bot_instance as bot_instance

    monkeypatch.setattr(settings, "MINI_APP_URL", "https://t.me/MentorLinkBot/admin")

    assert bot_instance.get_admin_review_url("tutor_7") == "https://t.me/MentorLinkBot/admin?startapp=tutor_7"


def test_review_url_falls_back_to_bot_username_when_mini_app_url_is_a_web_url(monkeypatch):
    """The common misconfiguration: MINI_APP_URL set to the Vercel URL instead of the t.me link."""
    import app.bot.bot_instance as bot_instance

    monkeypatch.setattr(settings, "MINI_APP_URL", "https://my-app.vercel.app/admin.html")
    monkeypatch.setattr(settings, "ADMIN_MINI_APP_SHORT_NAME", "admin")
    fake_app = MagicMock()
    fake_app.bot.username = "MentorLinkTestBot"
    monkeypatch.setattr(bot_instance, "bot_app", fake_app)

    assert bot_instance.get_admin_review_url("request_3") == "https://t.me/MentorLinkTestBot/admin?startapp=request_3"


def test_review_url_is_none_and_warns_once_when_nothing_can_be_resolved(monkeypatch, caplog):
    import logging
    import app.bot.bot_instance as bot_instance

    monkeypatch.setattr(settings, "MINI_APP_URL", "https://my-app.vercel.app/admin.html")
    monkeypatch.setattr(bot_instance, "bot_app", None)
    monkeypatch.setattr(bot_instance, "_review_url_warning_logged", False)

    with caplog.at_level(logging.WARNING, logger="mentorlink.bot"):
        assert bot_instance.get_admin_review_url("tutor_1") is None
        assert bot_instance.get_admin_review_url("tutor_2") is None

    warnings = [r for r in caplog.records if "Review in App" in r.getMessage()]
    assert len(warnings) == 1


def test_review_url_never_guesses_a_short_name(monkeypatch):
    """A guessed short name that isn't registered makes the button open the bot chat, not the app."""
    import app.bot.bot_instance as bot_instance

    monkeypatch.setattr(settings, "MINI_APP_URL", "https://my-app.vercel.app/admin.html")
    monkeypatch.setattr(settings, "ADMIN_MINI_APP_SHORT_NAME", None)
    fake_app = MagicMock()
    fake_app.bot.username = "MentorLinkTestBot"
    monkeypatch.setattr(bot_instance, "bot_app", fake_app)
    monkeypatch.setattr(bot_instance, "_review_url_warning_logged", False)

    assert bot_instance.get_admin_review_url("tutor_9") is None


def test_startup_check_tells_admin_which_short_name_to_verify(monkeypatch, caplog):
    """Reproduces the reported mix-up: registered app is 'admin' but MINI_APP_URL says 'app'."""
    import logging
    import app.bot.bot_instance as bot_instance

    monkeypatch.setattr(settings, "MINI_APP_URL", "https://t.me/MentorLinkProdBot/app")

    with caplog.at_level(logging.INFO, logger="mentorlink.bot"):
        bot_instance.check_review_link_config()

    text_out = " ".join(r.getMessage() for r in caplog.records)
    assert "https://t.me/MentorLinkProdBot/app?startapp=tutor_1" in text_out
    assert "/myapps" in text_out
    assert "'app'" in text_out


def test_startup_check_warns_when_link_has_no_short_name(monkeypatch, caplog):
    import logging
    import app.bot.bot_instance as bot_instance

    monkeypatch.setattr(settings, "MINI_APP_URL", "https://t.me/MentorLinkProdBot")

    with caplog.at_level(logging.WARNING, logger="mentorlink.bot"):
        bot_instance.check_review_link_config()

    assert any("no Mini App short name" in r.getMessage() for r in caplog.records)


# --------------------------------------------------------------------------
# Cron secret hardening
# --------------------------------------------------------------------------

def test_cron_secret_has_no_hardcoded_default():
    from app.config import Settings

    assert Settings.model_fields["CRON_SECRET"].default is None


@pytest.mark.asyncio
async def test_old_public_default_cron_secret_is_rejected(async_client: AsyncClient, monkeypatch):
    monkeypatch.setattr(settings, "CRON_SECRET", None)
    monkeypatch.setattr(settings, "SUPER_ADMIN_ID", None)
    monkeypatch.setattr(settings, "ALLOW_UNVERIFIED_WEB_PREVIEW", False)

    response = await async_client.post(
        "/api/v1/admin/cron/run",
        headers={"X-Cron-Secret": "mentorlink_cron_secret"},
    )

    assert response.status_code == 401


# --------------------------------------------------------------------------
# Review buttons: direct link + always-working bot fallback
# --------------------------------------------------------------------------

def _fake_bot(monkeypatch, username="MentorLinkTestBot"):
    import app.bot.bot_instance as bot_instance

    fake_app = MagicMock()
    fake_app.bot.username = username
    monkeypatch.setattr(bot_instance, "bot_app", fake_app)
    return bot_instance


def test_review_buttons_both_mode_gives_direct_and_bot_links(monkeypatch):
    bi = _fake_bot(monkeypatch)
    monkeypatch.setattr(settings, "MINI_APP_URL", "https://t.me/MentorLinkTestBot/admin")
    monkeypatch.setattr(settings, "ADMIN_REVIEW_LINK_MODE", "both")

    buttons = bi.get_admin_review_buttons("tutor_5")

    assert [b.text for b in buttons] == ["Review in App", "Open via bot"]
    assert buttons[0].url == "https://t.me/MentorLinkTestBot/admin?startapp=tutor_5"
    assert buttons[1].url == "https://t.me/MentorLinkTestBot?start=review_tutor_5"


def test_review_buttons_bot_mode_only_uses_bot_link(monkeypatch):
    bi = _fake_bot(monkeypatch)
    monkeypatch.setattr(settings, "MINI_APP_URL", "https://t.me/MentorLinkTestBot/admin")
    monkeypatch.setattr(settings, "ADMIN_REVIEW_LINK_MODE", "bot")

    buttons = bi.get_admin_review_buttons("request_7")

    assert [b.text for b in buttons] == ["Review in App"]
    assert buttons[0].url == "https://t.me/MentorLinkTestBot?start=review_request_7"


def test_review_buttons_fall_back_to_bot_link_when_direct_link_unavailable(monkeypatch):
    bi = _fake_bot(monkeypatch)
    monkeypatch.setattr(settings, "MINI_APP_URL", "https://my-app.vercel.app")
    monkeypatch.setattr(settings, "ADMIN_MINI_APP_SHORT_NAME", None)
    monkeypatch.setattr(settings, "ADMIN_REVIEW_LINK_MODE", "direct")

    buttons = bi.get_admin_review_buttons("tutor_1")

    assert [b.text for b in buttons] == ["Review in App"]
    assert buttons[0].url.startswith("https://t.me/MentorLinkTestBot?start=review_")


def test_review_buttons_ignore_uninitialised_bot(monkeypatch):
    import app.bot.bot_instance as bi

    monkeypatch.setattr(bi, "bot_app", None)
    monkeypatch.setattr(settings, "MINI_APP_URL", "https://t.me/MentorLinkTestBot/admin")
    monkeypatch.setattr(settings, "ADMIN_REVIEW_LINK_MODE", "both")

    assert [b.text for b in bi.get_admin_review_buttons("tutor_2")] == ["Review in App"]


@pytest.mark.asyncio
async def test_start_review_payload_gives_admin_a_web_app_button(monkeypatch):
    from unittest.mock import AsyncMock
    from app.bot import handlers as bh

    monkeypatch.setattr(settings, "SUPER_ADMIN_ID", 4242)
    monkeypatch.setattr(settings, "WEBAPP_URL", "https://admin-app.vercel.app")
    update = MagicMock()
    update.effective_user.id = 4242
    update.message.reply_text = AsyncMock()

    assert await bh._handle_review_deeplink(update, "tutor_12") is True

    markup = update.message.reply_text.await_args.kwargs["reply_markup"]
    button = markup.inline_keyboard[0][0]
    assert button.web_app.url == "https://admin-app.vercel.app/admin.html?start=tutor_12"


@pytest.mark.asyncio
async def test_start_review_payload_refuses_non_admins_and_bad_payloads(monkeypatch):
    from unittest.mock import AsyncMock
    from app.bot import handlers as bh

    monkeypatch.setattr(settings, "SUPER_ADMIN_ID", 4242)
    monkeypatch.setattr(settings, "WEBAPP_URL", "https://admin-app.vercel.app")
    update = MagicMock()
    update.effective_user.id = 999
    update.message.reply_text = AsyncMock()

    assert await bh._handle_review_deeplink(update, "tutor_12") is True
    assert "only for MentorLink admins" in update.message.reply_text.await_args.args[0]
    assert "reply_markup" not in update.message.reply_text.await_args.kwargs

    update.message.reply_text.reset_mock()
    assert await bh._handle_review_deeplink(update, "tutor_1;drop") is False
    update.message.reply_text.assert_not_awaited()
