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

The Phase 2 migrations add match-invite uniqueness and tutor pause state. Before applying to an existing database, inspect duplicate `(request_id, tutor_id)` invite pairs. The uniqueness migration intentionally stops instead of deleting historical records.

## Administrator management

Set `SUPER_ADMIN_ID` once as the bootstrap owner. In Telegram, the Super Admin opens `/start` and chooses **Manage Admins** to list active administrators, add an `admin` or `super_admin` by numeric Telegram user ID, or deactivate an administrator.

The database registry survives restarts and deployments. `ADMIN_IDS` remains supported as a legacy emergency fallback, but normal administrator changes should use the Super Admin console.

## Health and request tracing

Use `/api/v1/health` for database health. API responses include an `X-Request-ID` header. Supply your own `X-Request-ID` when tracing a request across logs.

## Common recovery actions

- `TOPIC_CLOSED`: post confirmation messages before closing the forum topic.
- Missing webhook updates: verify `BOT_MODE`, `WEBHOOK_URL`, `WEBHOOK_SECRET`, Render routing, and Telegram webhook status.
- Startup configuration failure: inspect the first settings validation error; webhook mode requires both webhook variables and HTTPS.
- Stale admin wizard: state expires after 30 minutes and is removed when next read.
