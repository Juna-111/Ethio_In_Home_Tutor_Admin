# MentorLink Operations Runbook

## Telegram bot mode

Use polling locally:

```env
BOT_MODE=polling
```

Use webhook mode on Render or any environment that may run more than one instance:

```env
BOT_MODE=webhook
WEBHOOK_URL=https://api.example.com/telegram/webhook/<long-random-secret>
WEBHOOK_SECRET=<same-long-random-secret>
```

The webhook URL must be HTTPS. Telegram must send the matching `X-Telegram-Bot-Api-Secret-Token` header. The backend rejects requests unless both the path secret and header secret match.

If Telegram reports a polling conflict (`409 Conflict`), stop all polling instances, set `BOT_MODE=webhook`, deploy, and verify the webhook with Telegram's `getWebhookInfo` API.

## Database migrations

From `backend/`, apply migrations with:

```powershell
alembic upgrade head
```

Run this on **every release**, not just once. Production never creates tables by itself (only `ENVIRONMENT=development` does), so shipping new code without migrating makes admin actions fail with a 500. Phases 3-5 add the tables `audit_log`, `tutor_verifications`, `session_feedback`, `tutor_incidents`, `scheduled_event_claims`, `notification_outbox` and `registration_funnel_events`; on Render, put `alembic upgrade head` in the service's **Pre-Deploy Command**.

After deploying, open `https://<backend>/api/v1/health`. You want `"status": "healthy"` and `"schema_state": "current"`. `"degraded"` / `"behind"` means migrations are missing; the backend also logs a `DATABASE SCHEMA IS BEHIND` error at startup.

The Phase 2 migrations add match-invite uniqueness and tutor pause state. Before applying to an existing database, inspect duplicate `(request_id, tutor_id)` invite pairs. The uniqueness migration intentionally stops instead of deleting historical records.

## Administrator management

Set `SUPER_ADMIN_ID` once as the bootstrap owner. In Telegram, the Super Admin opens `/start` and chooses **Manage Admins** to list active administrators, add an `admin` or `super_admin` by numeric Telegram user ID, or deactivate an administrator.

The database registry survives restarts and deployments. `ADMIN_IDS` remains supported as a legacy emergency fallback, but normal administrator changes should use the Super Admin console.

## Health and request tracing

Use `/api/v1/health` for database health. API responses include an `X-Request-ID` header. Supply your own `X-Request-ID` when tracing a request across logs.

## Admin Mini App environment

| Variable | Value |
|---|---|
| `WEBAPP_URL` | Frontend origin, e.g. `https://my-admin.vercel.app` (also the CORS-allowed origin) |
| `CORS_EXTRA_ORIGINS` | Optional, comma-separated extra origins if the admin app lives on another domain |
| `MINI_APP_URL` | BotFather direct link of the admin app, e.g. `https://t.me/MyBot/admin` (**not** the Vercel URL) |
| `ADMIN_MINI_APP_SHORT_NAME` | Optional, no default. Short name of the admin app, used only if `MINI_APP_URL` is not a t.me link |
| `CRON_SECRET` | Long random value, identical to the `CRON_SECRET` GitHub Actions secret. No default. |

If "Review in App" buttons are missing from admin cards, the backend logs `Cannot build 'Review in App' links` at startup; fix `MINI_APP_URL` as above.

If the button is there but **opens the bot chat instead of the app**, the short name in `MINI_APP_URL` does not match an app registered on that bot. The startup log prints the exact link (`'Review in App' links will look like: ...`). In @BotFather send `/myapps`, pick the bot, and compare: the short name must be the admin app's, and its Web App URL must end in `/admin.html`.

## Troubleshooting: "Could not reach the MentorLink server"

The message shows the API host and the app's own origin. Work through these in order:

1. Open `https://<backend>/api/v1/health` in a browser. If it does not load, the server is down or cold-starting (free Render instances sleep); check the Render logs and wait a minute.
2. If health loads but reports `"schema_state": "behind"`, run `alembic upgrade head`.
3. If health is fine, the browser is refusing the request (CORS). Set `WEBAPP_URL` or `CORS_EXTRA_ORIGINS` to exactly the origin printed in the error (scheme + host, no path or trailing slash), then redeploy. Startup logs list the allowed origins (`CORS allowed origins: ...`).
4. If the error says `Internal server error. Reference: <id>`, search the backend logs for that id to find the traceback.

## Common recovery actions

- `TOPIC_CLOSED`: post confirmation messages before closing the forum topic.
- Missing webhook updates: verify `BOT_MODE`, `WEBHOOK_URL`, `WEBHOOK_SECRET`, Render routing, and Telegram webhook status.
- Startup configuration failure: inspect the first settings validation error; webhook mode requires both webhook variables and HTTPS.
- Stale admin wizard: state expires after 30 minutes and is removed when next read.
