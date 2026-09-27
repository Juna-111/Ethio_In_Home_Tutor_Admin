# MentorLink Admin Mini App — Full Implementation Spec (Final)

**Project:** standalone repo, copied from `Juna-111/Ethio_In_Home_Tutor` (see §0)
**Relationship to client's live app:** none at runtime — separate bot, separate database, separate hosting. Safe to break.
**Audience:** the coding agent building this, phase by phase.

---

## 0. Project Setup (do this before Phase 1)

1. Mirror-copy the original repo into a new, independent GitHub repo (not a fork) — full history, no ongoing link to `Juna-111/Ethio_In_Home_Tutor`.
2. Create a **new Telegram bot** via @BotFather (own `BOT_TOKEN`, own username).
3. Create a **new Telegram group** for admin notifications; add the new bot; recreate the forum topics the app expects (see `backend/app/bot/topics.py`).
4. Provision a **new Postgres database** (Render/Neon) — never point this project at the client's DB.
5. Deploy backend to a **new Render service** and frontend to a **new Vercel project**, using the new bot token, new DB URL, and this project's own `.env` values (copy `.env.example` in both `backend/` and `frontend/` and fill with the new credentials).
6. Confirm the copied app runs end-to-end as-is (submit a test parent request, register a test tutor, see the cards land in the new group) **before** writing any new code. This is your baseline — if something's broken here, it's not something Phase 1 introduced.

**Exit criteria for §0:** existing `pytest` suite passes against the new backend; a manual parent-request + tutor-registration round trip works in the new Telegram group.

---

## 1. Division of Labor (applies to every phase below)

| Concern | Surface |
|---|---|
| New tutor registered / new parent request | Group card, **"Review in App"** deep-link button |
| Tutor approve/reject | **Miniapp only**, gated by verification checklist (Phase 3+) |
| Matching a parent to tutors | **Miniapp** (Matching Workbench) |
| Red flags, duplicate phone, low entrance score | Group alert (auto-posted) → resolved in **Miniapp** |
| Waitlist match found | Group alert → assign in **Miniapp** |
| Re-verification / probation check-in due | Group reminder → action in **Miniapp** |
| Post-session rating | **Bot DM to the parent**, result viewed in **Miniapp** |
| Quick complaint capture on the go | `/complaint` bot command (fallback) → full record in **Miniapp** |
| Analytics, funnels, coverage gaps, scorecards | **Miniapp only** |
| Audit log | Invisible; written server-side regardless of trigger source |

---

## 2. Data Model (introduced across phases, all additive)

```python
class SessionFeedback(Base):
    __tablename__ = "session_feedback"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    assignment_id: Mapped[int] = mapped_column(Integer, ForeignKey("assignments.id"), nullable=False, index=True)
    rating: Mapped[int] = mapped_column(Integer, nullable=False)  # 1-5
    comment: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    submitted_by: Mapped[str] = mapped_column(String(20), nullable=False, default="parent")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

class TutorIncident(Base):
    __tablename__ = "tutor_incidents"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tutor_id: Mapped[int] = mapped_column(Integer, ForeignKey("tutors.id"), nullable=False, index=True)
    request_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    severity: Mapped[str] = mapped_column(String(20), nullable=False, default="low")  # low|medium|high
    description: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="open", index=True)
    reported_by: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

class TutorVerification(Base):
    __tablename__ = "tutor_verifications"
    tutor_id: Mapped[int] = mapped_column(Integer, ForeignKey("tutors.id"), primary_key=True)
    id_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    entrance_result_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    phone_confirmed: Mapped[bool] = mapped_column(Boolean, default=False)
    claims_plausible: Mapped[bool] = mapped_column(Boolean, default=False)
    last_verified_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    verified_by: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)

class AuditLog(Base):
    __tablename__ = "audit_log"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    actor_telegram_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    target_type: Mapped[str] = mapped_column(String(30), nullable=False)
    target_id: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    source: Mapped[str] = mapped_column(String(20), nullable=False, default="miniapp")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
```

**Existing model changes (value-range only, no migration):** `Tutor.status` gains `probation`; `ParentRequest.status` gains `waitlisted`.

Use Alembic for every schema change — no reliance on `create_all` beyond local dev.

## Pre-Phase 1 Resolutions

### Tutor status vocabulary

Use exactly these persisted `Tutor.status` values: `pending`, `verified`, `probation`, and `rejected`. `verified` is the one approved-and-eligible state; do not persist `approved` as a second synonym. Phase 3 verification sets status to `verified` only after all checklist items pass. `probation` is not eligible for new matches. `is_paused` remains an independent availability flag, not a status value. Existing matching, bot approval/assignment, and analytics code already use `verified`; new admin routes, scorecards, and exports must preserve this vocabulary.

### Baseline verification

The current workspace is not yet the independent deployment described in section 0, so this is a local code baseline, not proof of the new deployment or its Telegram round trip. The backend suite ran with its in-memory SQLite fixtures: initially 54 passed and 5 failed. The five failures were stale output assertions: the current public button says `Register`; the access-denied callback includes a trailing space; tutor cards intentionally omit credential URLs; parent topics use `PAR-{id} — {name}` and current card/button labels; and the assignment DM ends with `Thank you for trusting Us.`. Only those test assertions were aligned to current handler behavior; no application behavior changed. The suite then passed: 59 passed. Section 0's separate-deployment and manual Telegram checks remain required before Phase 1 feature work.

### Durable scheduled work

Do not run per-process timers. Use one external scheduler (for example, a Render Cron Job) to call an authenticated cron endpoint. Each check occurrence must be claimed transactionally in PostgreSQL using a persisted event key with a unique constraint, scoped to the entity, check type, and scheduled occurrence. Persist check state and create a durable notification outbox record in that same transaction; only the winning claim creates the event, and the endpoint drains pending outbox rows. This prevents concurrent instances or overlapping cron calls from generating duplicate alerts and supports recovery after process restarts. Test concurrent calls for the same occurrence and assert one claimed event/outbox row. Telegram does not provide an idempotency key for message sends, so the outbox guarantees one durable event and one concurrent dispatch claim; absolute exactly-once delivery across a network failure between Telegram accepting a message and the database recording success cannot be guaranteed.

---

## PHASE 1 — Foundation

**Goal:** auth, skeleton API, and a miniapp shell that opens and identifies the admin — nothing feature-rich yet.

**Tasks:**
- `backend/app/admin_auth.py`: `require_admin` dependency (wraps existing `get_current_telegram_user`, checks `AdminUser.is_active`) and `require_role(*roles)` factory.
- Alembic migration: `AuditLog`, `TutorVerification` tables (needed early since every later phase logs to them).
- `backend/app/routes/admin.py`: mount at `/api/v1/admin`; implement `GET /admin/dashboard` returning pending tutor/request counts, active assignments, requests-today.
- `app/services/audit.py`: `log_action(db, actor_id, action, target_type, target_id, reason, source)` helper — used by every mutating route from Phase 2 onward.
- Frontend: new Vite entry `frontend/admin.html` + `frontend/src/admin/AdminApp.jsx`; update `vite.config.js` `build.rollupOptions.input`.
- Deep-link routing: read `Telegram.WebApp.initDataUnsafe.start_param`, parse `tutor_{id}` / `request_{id}` format (wired up now, used from Phase 2).
- Register the new miniapp URL with the new bot via BotFather.

**Deliverables:** admin can open the miniapp inside Telegram, see a dashboard with real counts, and a non-admin sees a clean "not authorized" screen instead of a crash.

**Test checklist:**
- [ ] `require_admin` returns 401 with no `initData`, 403 for a valid but non-admin Telegram user.
- [ ] `GET /admin/dashboard` numbers match a manual DB count.
- [ ] Opening the miniapp with a fabricated `startapp=tutor_1` deep link is at least parsed correctly client-side (target screen can be a placeholder for now).
- [ ] Existing `pytest` suite still passes untouched.

---

## PHASE 2 — Supply Core

**Goal:** fix the matching workflow and give visibility into where tutor supply is short.

**Tasks:**
- Extend `matcher.py` to return **per-factor scores** (subject match, distance, budget fit, schedule overlap, experience) per candidate, not just a single ranked pick.
- `GET /admin/requests?status=&subcity=&subject=&page=`, `GET /admin/requests/{id}`, `GET /admin/requests/{id}/candidates`.
- `POST /admin/requests/{id}/ping` (bulk), `POST /admin/requests/{id}/assign`, `POST /admin/requests/{id}/close`, `POST /admin/requests/{id}/waitlist` — all call `log_action`.
- `GET /admin/analytics/coverage-gaps` → `[{subcity, subject, pending_requests, approved_tutors, gap_ratio}]`.
- `GET /admin/tutors/idle?days=14` + `POST /admin/tutors/{id}/reactivate-nudge` (triggers bot DM via existing `bot_instance.py` send utilities).
- Bot: update `send_tutor_registration_card` / `send_parent_request_card` to add the "Review in App" deep-link button (keep existing inline buttons active in parallel for now — do not remove yet).
- Frontend: Requests list, Request detail, **Matching Workbench** (side-by-side candidate comparison with score breakdown, multi-select ping, one-click assign), Coverage Gap Board.

**Deliverables:** an admin can open a pending request, see ranked candidates with *why* they rank that way, ping several at once, and assign — entirely in the app. The Coverage Gap Board answers "where do I need tutors" at a glance.

**Test checklist:**
- [ ] Candidate scoring returns a deterministic, explainable breakdown for a known fixture request/tutor pair.
- [ ] Assign creates exactly one `Assignment` row and one `AuditLog` row.
- [ ] Coverage gap numbers match a manual query against seeded test data.
- [ ] Deep-link `startapp=request_{id}` now opens directly to that request's detail view.
- [ ] Full `pytest` suite passes; existing bot approve/reject buttons still work unmodified.

---

## PHASE 3 — Quality Core

**Goal:** make tutor approval mean something, and start collecting real outcome data.

**Tasks:**
- `PATCH /admin/tutors/{id}/verification` — upserts `TutorVerification`; sets `Tutor.status` to `verified` only when all four checklist flags are true.
- `POST /admin/tutors/{id}/reject` (role: `verifier`+), with required `reason`.
- `GET /admin/tutors/{id}/document` — stream uploaded ID/CV (reuse validation from `routes/tutors.py`).
- `SessionFeedback` migration; bot job (`bot/feedback.py`) that DMs the parent a 1–5 rating request N days after `Assignment.assigned_at` (N configurable via `SystemSetting`); on response, writes `SessionFeedback`.
- `GET /admin/tutors/{id}/scorecard` → avg rating, response rate (from `MatchInvite` timestamps), incident count.
- Frontend: Verification Checklist UI (on tutor detail, blocks approve until complete, with inline document viewer/zoom), Tutor Scorecard panel.
- Bot: **now remove** the inline approve/reject buttons from the tutor registration card, replacing with "Review in App" only (per §1 — approval now requires the checklist, which chat buttons can't do).

**Deliverables:** tutor approval is no longer a single click; it requires a completed checklist. Post-session ratings start flowing in and show up on the tutor's profile.

**Test checklist:**
- [ ] Approving with an incomplete checklist is rejected by the API (not just hidden in the UI).
- [ ] Feedback DM round-trip creates one `SessionFeedback` row per response.
- [ ] Scorecard numbers match manual aggregation over seeded feedback/invite data.
- [ ] Confirm the bot no longer exposes one-click approve/reject on new cards; old already-sent cards in the group don't error if tapped (graceful "use the app" message).
- [ ] Full `pytest` suite passes.

---

## PHASE 4 — Ops Layer

**Goal:** catch problems automatically instead of relying on an admin noticing.

**Tasks:**
- `TutorIncident` migration; `GET/POST/PATCH /admin/incidents`.
- `/complaint` bot command as a fast-capture fallback, writing directly into `TutorIncident`.
- `GET /admin/flags` — red-flag detector: missing document, entrance score below a `SystemSetting`-configured threshold, duplicate phone across `Tutor` rows, fee outlier vs. experience band. The external cron-triggered check posts a group alert when a new flag occurrence is claimed.
- Waitlist auto-backfill: on tutor approval, check `ParentRequest.status='waitlisted'` for matches and post a group alert ("3 waitlisted requests match this tutor") with a deep link into the Matching Workbench.
- Roles: enforce `verifier` / `matcher` / `super_admin` on the routes from Phases 2–3 (they were built for `require_admin` generically; now scope them).
- `GET/POST/DELETE /admin/admins` (super_admin only) — CRUD on `AdminUser`.
- `GET /admin/audit?target_type=&actor=&page=` (super_admin only).
- Frontend: Red-Flag Queue, Waitlist view, Incident log (per-tutor + standalone), Admin management screen, Audit log viewer (nav items hidden per role).

**Deliverables:** the system proactively surfaces problems in the group chat, admins resolve them in-app, and every action is attributable and reviewable.

**Test checklist:**
- [ ] Each red-flag condition triggers exactly one alert per occurrence (no duplicate spam on repeated checks).
- [ ] A `verifier`-role admin gets 403 on matcher-only and super_admin-only routes.
- [ ] Waitlist backfill alert fires only when a genuinely matching new tutor is approved (no false positives against a fixture set).
- [ ] Audit log contains a row for every mutating action performed anywhere in Phases 1–4.
- [ ] Full `pytest` suite passes.

---

## PHASE 5 — Analytics & Polish

**Goal:** the strategic view — is the business healthy, not just what's pending today.

**Tasks:**
- Track tutor registration funnel stages (started/submitted/approved) — requires a lightweight "registration started" ping from the frontend form (`TutorForm.jsx`) if not already inferable from partial data.
- `GET /admin/analytics/funnel`, `GET /admin/analytics/availability-mismatch` (cross-tabulate `availability_schedule` vs. `time_slot`).
- Re-verification cadence: `last_verified_at` check on the external cron-triggered job, posts a group reminder when tutors cross the configured interval; persisted occurrence claims prevent duplicate reminders.
- Probation check-in reminders: for tutors in `probation` status with an active assignment, remind at a configured interval.
- Frontend: Funnel chart, availability mismatch view, re-verification/probation reminders surfaced in-app (mirroring the group alert).
- Final CSV export parity check: `GET /admin/export` output matches the existing bot `/export` flow byte-for-byte on the same dataset.

**Deliverables:** full parity with the original idea — a dashboard that tells you where the business is winning or stuck, not just a to-do list.

**Test checklist:**
- [ ] Funnel counts add up consistently (submitted ≤ started, approved ≤ submitted) against seeded data.
- [ ] Re-verification/probation reminders fire on schedule in a time-mocked test, not just "eventually."
- [ ] Export parity test passes against `export_service.py` output.
- [ ] Full `pytest` suite passes — this is the final gate before considering porting anything back toward the client's real repo.

---

## 3. Final Sign-off Checklist (before calling this "done")

- [ ] All five phases' test checklists pass on the standalone project's own bot/DB/deploy.
- [ ] A full manual walkthrough: submit a parent request and a tutor registration on the public intake app → see both land as group alerts with "Review in App" → verify the tutor via checklist → run the Matching Workbench → assign → receive the (test-triggered) feedback DM → confirm the scorecard updates → trigger a red flag on purpose (e.g. duplicate phone) and confirm the alert + resolution flow.
- [ ] Decide, per §4 below, what (if anything) gets ported back into the client's live repo, and do that as a normal reviewed PR — never a direct push to their `main`.

## 4. Open Decisions (yours, not the agent's)

1. Red-flag thresholds (entrance score cutoff, fee outlier range) — initial values to seed in `SystemSetting`.
2. Feedback DM timing: fixed N days after assignment vs. a manual "mark session complete" trigger.
3. Whether the finished admin miniapp becomes a permanent second project or gets merged back into the client's repo as a feature.
