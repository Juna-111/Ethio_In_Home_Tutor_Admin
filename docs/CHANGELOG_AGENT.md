# Agent Change Log

## Phase 1 hardening update

Date: 2026-09-25

Implemented in the current working tree:

- Required explicit `ALLOW_UNVERIFIED_WEB_PREVIEW` opt-in; development mode no longer implicitly bypasses Telegram authentication.
- Ignored client-supplied `telegram_user_id` values in parent and tutor registration routes.
- Rejected missing and future-dated Telegram `auth_date` values.
- Added admin authorization coverage for broadcast, CMS, analytics, and export callbacks while preserving private Super Admin console actions.
- Required verified tutors with a confirmed availability response before assignment.
- Required an existing `sent` invite before recording tutor availability responses.
- Added a composite `MatchInvite(request_id, tutor_id)` uniqueness constraint to the SQLAlchemy model.
- Replaced admin-authored About Us, Contact, and broadcast content with plain Telegram text. Existing stored markup is displayed literally and is not parsed.
- Replaced unsafe document path prefix checking with resolved path containment and regular-file validation.
- Added regression coverage for literal CMS content and non-HTML broadcast delivery.
- Added server-side Ethiopian mobile normalization to both registration schemas.
- Added a 30-minute TTL for persisted and in-memory admin wizard state.
- Added Alembic configuration and a reversible `MatchInvite` uniqueness migration that refuses unresolved duplicate historical rows.
- Added a lightweight per-user/IP upload rate limit.

## Remaining Phase 1 work

- Apply the Alembic migration against the production database after reviewing any duplicate invite pairs.
- Replace local uploads with configured durable private object storage for production deployments.
- Run the backend test suite once the terminal interpreter uses the installed test environment.

The frontend production build passed. Python compilation and editor diagnostics passed. The persistent terminal could not see the Python packages reported by the managed environment, so pytest and the Alembic CLI could not be executed there. No commit was created by this agent.

## Phase 2 foundation

- Added typed `BOT_MODE`, `WEBHOOK_URL`, and `WEBHOOK_SECRET` settings with production validation.
- Added secure Telegram webhook ingestion at `/telegram/webhook/{webhook_secret}` using both path and `X-Telegram-Bot-Api-Secret-Token` validation.
- Preserved polling for local development and registered webhooks through PTB's update queue.
- Added request IDs to API responses and structured request start/finish logs.
- Normalized CORS entries to browser origins rather than full URL paths.
- Added `Tutor.is_paused`, an Alembic migration, and deterministic matcher exclusion for paused tutors.
- Added focused webhook/config regression tests.
- Added a persistent `admin_users` registry and Super Admin console controls to list, add, assign roles, and deactivate administrators without editing Render variables.
