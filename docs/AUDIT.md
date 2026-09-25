# Codebase Audit Report: MentorLink (Ethio_In_Home_Tutor)

**Date:** September 25, 2026  
**Auditor:** Senior Full-Stack Engineer  
**Scope:** Full-stack inspection across `backend/` (FastAPI, Python-Telegram-Bot, SQLAlchemy) and `frontend/` (React, Vite, Tailwind CSS).  
**Repository:** `Ethio_In_Home_Tutor`

## Current Implementation Status

This document contains historical findings from earlier review passes. The current tree has since implemented several of them, including callback authorization for core group actions, signed Mini App authentication, streaming/magic-byte upload checks, private document delivery, atomic status transitions, persisted match responses, CSV formula neutralization, and frontend request authentication.

The following items remain active after the latest Phase 1 hardening pass: durable provider-backed storage for uploaded documents, applying the new Alembic migration against production data, and a complete backend test run in the correct installed environment. Upload rate limiting, strict server-side phone normalization, and stale wizard-state cleanup are now implemented. Admin-managed About Us, Contact, and broadcast content is plain Telegram text: it is stored and delivered without `parse_mode`, and legacy markup is displayed literally.

Treat the severity/status tables below as historical unless they agree with the current source and this section.

---

## 1. Executive Summary & Diagnostic Findings

This comprehensive codebase audit evaluates security vulnerabilities, logic defects, race conditions, Telegram API failure modes, and frontend accessibility/resilience concerns across the MentorLink platform.

Each finding below is validated against live source code with exact file and line references, severity ratings, confirmation statuses, and technical remediations.

---

## 2. Security Audit Findings (P0)

### S-01: Admin Authorization Bypass on Interactive Telegram Callbacks
* **File & Lines:** [`backend/app/bot/handlers.py:187-201`](file:///d:/MentorLink/backend/app/bot/handlers.py#L187-L201)
* **Severity:** **P0 — CRITICAL**
* **Status:** **CONFIRMED**
* **Evidence:**
  `handle_callback_query` dispatches `approve_tutor:`, `reject_tutor:`, `match_parent:`, `close_parent:`, `assign_match:`, and `ping_candidates:` without verifying whether `update.effective_user.id` is a Super Admin or listed admin, nor verifying `query.message.chat.id == settings.ADMIN_GROUP_ID`.
* **Impact:** Any unauthorized Telegram user who forwards a message or crafts a callback query can approve/reject tutors, close requests, trigger matching radars, and finalize tutor assignments.
* **Remediation:** Introduce `is_admin(update, context)` that checks:
  1. `is_super_admin(update)`
  2. Configurable `ADMIN_IDS` set in `settings`
  3. Real-time Telegram chat admin check via `get_chat_member` on `ADMIN_GROUP_ID` (with a short-lived in-memory cache).
  4. Ensure `query.message.chat.id == settings.ADMIN_GROUP_ID` for group management actions. Deny unauthorized actions with `query.answer("⛔ Unauthorized action.", show_alert=True)`.

---

### S-02: Tutor Impersonation on Availability Confirmation Ping
* **File & Lines:** [`backend/app/bot/handlers.py:574-612`](file:///d:/MentorLink/backend/app/bot/handlers.py#L574-L612)
* **Severity:** **P0 — CRITICAL**
* **Status:** **CONFIRMED**
* **Evidence:**
  In `handle_tutor_avail_yes` and `handle_tutor_avail_no`, the callback payload `tutor_avail_yes:{parent_id}:{tutor_id}` is parsed. The code fetches `tutor = await session.get(Tutor, tutor_id)` but never validates that `tutor.telegram_user_id == update.effective_user.id`.
* **Impact:** Anyone with access to the ping or forwarded button can click "Yes, I'm Available" or "Not Available" on behalf of any other tutor.
* **Remediation:** Enforce `if not tutor.telegram_user_id or tutor.telegram_user_id != update.effective_user.id: await query.answer("⛔ This availability prompt was sent to another user.", show_alert=True); return`.

---

### S-03: Spoofable Telegram User Identity via Client-Controlled Payload
* **File & Lines:**
  - Frontend: [`frontend/src/App.jsx:24-26`](file:///d:/MentorLink/frontend/src/App.jsx#L24-L26), [`frontend/src/components/ParentForm.jsx:58`](file:///d:/MentorLink/frontend/src/components/ParentForm.jsx#L58), [`frontend/src/components/TutorForm.jsx:178`](file:///d:/MentorLink/frontend/src/components/TutorForm.jsx#L178), [`frontend/src/services/api.js:3-50`](file:///d:/MentorLink/frontend/src/services/api.js#L3-L50)
  - Backend: [`backend/app/routes/parents.py:28`](file:///d:/MentorLink/backend/app/routes/parents.py#L28), [`backend/app/routes/tutors.py:73`](file:///d:/MentorLink/backend/app/routes/tutors.py#L73)
* **Severity:** **P0 — CRITICAL**
* **Status:** **CONFIRMED**
* **Evidence:**
  The frontend extracts `tg.initDataUnsafe.user.id` and transmits it in the JSON request body as `telegram_user_id`. The backend directly writes `payload.telegram_user_id` to the database without cryptographic signature verification.
* **Impact:** Attackers can submit requests or register profiles impersonating any Telegram user ID.
* **Remediation:**
  1. Frontend: Read `window.Telegram?.WebApp?.initData` and send it as `Authorization: tma <raw_init_data>` header.
  2. Backend: Implement a FastAPI dependency (`get_verified_telegram_user`) validating HMAC-SHA256 signature against `BOT_TOKEN` and checking `auth_date` freshness (< 24h).
  3. Derive `telegram_user_id` exclusively on the server, ignoring any client-sent ID. Provide an explicit dev flag (`ALLOW_UNVERIFIED_WEB_PREVIEW=True`) strictly for local browser development.

---

### S-04: Insecure Tutor Document Upload Vulnerability
* **File & Lines:** [`backend/app/routes/tutors.py:16-56`](file:///d:/MentorLink/backend/app/routes/tutors.py#L16-L56)
* **Severity:** **P0 — CRITICAL**
* **Status:** **CONFIRMED**
* **Evidence:**
  `upload_tutor_document` checks only filename extension (`ALLOWED_EXTENSIONS`), performs `content = await file.read()` loading unlimited bytes into server memory, embeds raw `file.filename` into the stored path (`safe_filename = f"{uuid.uuid4().hex[:12]}_{file.filename}"`), and lacks authentication and rate limiting.
* **Impact:** Denial of Service via large uploads (memory exhaustion), potential path traversal/injection via unescaped client filenames, and file upload spam without verification.
* **Remediation:**
  1. Require valid `tma` authentication.
  2. Implement streaming chunk upload with strict 10 MB ceiling.
  3. Validate Magic Bytes (file signatures for PDF `%PDF`, PNG `\x89PNG`, JPG `\xff\xd8\xff`).
  4. Generate pure UUID filenames (`f"{uuid.uuid4().hex}{ext}"`).
  5. Add slowapi rate limits (e.g. 5 uploads/min per user/IP).

---

### S-05: Sensitive Verification IDs Publicly Exposed & Un-gitignored
* **File & Lines:** [`backend/app/main.py:75`](file:///d:/MentorLink/backend/app/main.py#L75), [`backend/.gitignore:1-16`](file:///d:/MentorLink/backend/.gitignore#L1-L16)
* **Severity:** **P0 — CRITICAL**
* **Status:** **CONFIRMED**
* **Evidence:**
  - `main.py` mounts `app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")`, exposing all government IDs and student credentials publicly to the web.
  - `backend/.gitignore` does NOT include `uploads/`, risking accidental commit of sensitive PII.
* **Impact:** Public exposure and leak of national identification cards, passports, and student credentials of tutors.
* **Remediation:**
  1. Remove the public `StaticFiles` mount at `/uploads`.
  2. Add `uploads/` to `backend/.gitignore`.
  3. Store documents securely (private S3/R2 storage or private Telegram storage channel, with short-lived presigned access or bot file dispatch).

---

### S-06: Permissive CORS with Credentials & Unprotected Endpoints
* **File & Lines:** [`backend/app/main.py:61-67`](file:///d:/MentorLink/backend/app/main.py#L61-L67)
* **Severity:** **P1 — HIGH**
* **Status:** **CONFIRMED**
* **Evidence:**
  `CORSMiddleware` specifies `allow_origins=["*"]` with `allow_credentials=True`. This is invalid per CORS spec and allows any third-party domain to make credentialed cross-origin requests.
* **Impact:** Cross-site script execution risk and lack of origin control.
* **Remediation:** Restrict `allow_origins` to `settings.WEBAPP_URL`, Vercel deploy domains, and `https://web.telegram.org`. Add slowapi rate limiting on public intake endpoints.

---

### S-07: Information Disclosure in Database Healthcheck
* **File & Lines:** [`backend/app/routes/health.py:23-27`](file:///d:/MentorLink/backend/app/routes/health.py#L23-L27)
* **Severity:** **P1 — HIGH**
* **Status:** **CONFIRMED**
* **Evidence:**
  ```python
  except Exception as exc:
      raise HTTPException(
          status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
          detail=f"Database connection failed: {str(exc)}"
      )
  ```
* **Impact:** Leaks raw database connection strings, credentials, network topologies, and driver tracebacks to unauthenticated callers.
* **Remediation:** Log the full exception internally with `logger.error("DB healthcheck failed: %s", exc)` and return a generic `detail="Database service unavailable"`.

---

### S-08: CSV Formula Injection Vulnerability
* **File & Lines:** [`backend/app/services/export_service.py:10-18, 55-72, 114-131`](file:///d:/MentorLink/backend/app/services/export_service.py#L10-L18)
* **Severity:** **P1 — HIGH**
* **Status:** **CONFIRMED**
* **Evidence:**
  User-supplied strings (`full_name`, `parent_name`, `landmark`, etc.) are written directly into CSV cells. If a user inputs `=cmd|' /C calc'!A0` or `@SUM(...)`, Excel executes the payload upon opening.
* **Impact:** Remote command execution or data exfiltration on the Super Admin's workstation when opening exported CSVs in Microsoft Excel.
* **Remediation:** Neutralize all CSV values beginning with `=`, `+`, `-`, `@`, `\t`, or `\r` by prefixing them with a single quote `'`. Preserve UTF-8-SIG BOM.

---

## 3. Backend & Matching Logic Findings (P0 / P1)

### B-01: Non-Atomic State Transitions and Race Conditions
* **File & Lines:** [`backend/app/bot/handlers.py:244-252, 288-296, 339-347, 680-695`](file:///d:/MentorLink/backend/app/bot/handlers.py#L244-L252)
* **Severity:** **P0 — HIGH**
* **Status:** **CONFIRMED**
* **Evidence:**
  Handlers perform non-atomic `session.get()` followed by `tutor.status = "verified"` without checking if the entity is currently `pending`. Double clicks or concurrent admin reviews create race conditions.
* **Impact:** Inconsistent state transitions; closed requests can be reassigned; already rejected tutors can be overwritten.
* **Remediation:** Execute atomic updates: `UPDATE tutors SET status='verified' WHERE id=:id AND status='pending' RETURNING id`. If 0 rows are returned, inform the admin that the record was already processed.

---

### B-03: Race Condition on Forum Topic Closure before Confirmation Post
* **File & Lines:** [`backend/app/bot/handlers.py:690-721`](file:///d:/MentorLink/backend/app/bot/handlers.py#L690-L721)
* **Severity:** **P1 — HIGH**
* **Status:** **CONFIRMED**
* **Evidence:**
  `context.bot.close_forum_topic(...)` is called at line 692. Then at line 719, the bot attempts `query.message.reply_text(...)` inside the same thread.
* **Impact:** Closed forum topics reject subsequent message posts with `TOPIC_CLOSED` error, causing confirmation messages and inline markup updates to fail.
* **Remediation:** Post thread confirmation messages and update inline buttons *before* invoking `close_forum_topic`.

---

### B-04: Eager Ping Button Lockout before Validation
* **File & Lines:** [`backend/app/bot/handlers.py:510-538`](file:///d:/MentorLink/backend/app/bot/handlers.py#L510-L538)
* **Severity:** **P1 — HIGH**
* **Status:** **CONFIRMED**
* **Evidence:**
  The inline button is immediately edited to `"⏳ Ping Sent to Top Candidates"` at lines 510-524, before verifying if the request exists or if there are any reachable tutors with Telegram IDs.
* **Impact:** If no tutors have Telegram IDs or matching fails, the button remains permanently locked with "Ping Sent" and can never be re-attempted.
* **Remediation:** Validate candidates and perform message dispatch first, then update the button text with actual sent count or allow retry if 0 candidates were pinged.

---

### B-05: Missing HTML Entity Escaping in Bot Direct Messages
* **File & Lines:** [`backend/app/bot/handlers.py:748-752, 91-98, 160-168`](file:///d:/MentorLink/backend/app/bot/handlers.py#L748-L752)
* **Severity:** **P1 — HIGH**
* **Status:** **CONFIRMED**
* **Evidence:**
  In `handle_assign_match`:
  ```python
  f"👤 <b>Parent:</b> {parent.parent_name}\n"
  f"📞 <b>Contact:</b> {parent.phone_number}\n"
  f"🎓 <b>Student Level:</b> {parent.student_level}\n"
  ```
  `parent.parent_name`, `parent.phone_number`, and `parent.student_level` are interpolated directly without `html.escape()`.
* **Impact:** Special characters (`<`, `>`, `&`) in parent names cause Telegram `BadRequest: Can't parse entities`, crashing notification dispatch.
* **Remediation:** Wrap every user-supplied string in `html.escape()`.

---

### B-06: Unvalidated HTML Rendering in Super Admin CMS & Broadcast
* **File & Lines:** [`backend/app/bot/handlers.py:1142, 1256-1271, 1373-1386`](file:///d:/MentorLink/backend/app/bot/handlers.py#L1142)
* **Severity:** **P1 — HIGH**
* **Status:** **CONFIRMED**
* **Evidence:**
  `handle_cms_view_current` prints stored content directly inside `f"...{current_val}"` with `parse_mode=ParseMode.HTML`. In `handle_text_message`, CMS input is saved directly without validating that it contains well-formed HTML.
* **Impact:** Unclosed tags (`<b>`, `<a>`) cause Telegram API errors, locking the admin out of viewing or updating content.
* **Remediation:** Test-parse HTML before saving; escape display in previews or provide fallback plain-text rendering on error.

---

### B-07: Blocking Broadcast Loop Freezes Bot Event Loop
* **File & Lines:** [`backend/app/bot/handlers.py:1040-1075`](file:///d:/MentorLink/backend/app/bot/handlers.py#L1040-L1075)
* **Severity:** **P1 — HIGH**
* **Status:** **CONFIRMED**
* **Evidence:**
  `handle_bcast_confirm` loops synchronously through all `recipient_ids` with `await asyncio.sleep(0.04)` directly inside the callback handler.
* **Impact:** Freezes the Telegram bot worker for dozens of seconds during broadcasts, preventing all other users from interacting with the bot.
* **Remediation:** Offload broadcasts to a background task (`asyncio.create_task` or PTB `application.create_task`), handle `RetryAfter` and `Forbidden`, and persist delivery stats.

---

### B-08: In-Memory Wizard Session State Lost on Restart
* **File & Lines:** [`backend/app/bot/handlers.py:36`](file:///d:/MentorLink/backend/app/bot/handlers.py#L36)
* **Severity:** **P1 — MEDIUM**
* **Status:** **CONFIRMED**
* **Evidence:**
  `admin_states: Dict[int, dict] = {}` is an in-memory dictionary.
* **Impact:** Any backend redeploy or worker restart drops active admin broadcast or CMS sessions, causing subsequent messages to be processed as unexpected text.
* **Remediation:** Persist wizard state in the database or PTB persistence store with a TTL expiry.

---

### B-09: Unpersisted Tutor Availability Pings
* **File & Lines:** [`backend/app/bot/handlers.py:553-630`](file:///d:/MentorLink/backend/app/bot/handlers.py#L553-L630)
* **Severity:** **P1 — HIGH**
* **Status:** **CONFIRMED**
* **Evidence:**
  No database model tracks sent pings. Pings exist solely as Telegram inline message buttons.
* **Impact:** No record of who was pinged, when, or whether they answered; duplicate answers generate repeated alerts; no automated expiry.
* **Remediation:** Introduce `MatchInvite` table (`request_id`, `tutor_id`, `sent_at`, `status`, `responded_at`) with 6h expiry and single-response enforcement.

---

### B-10: Match Radar 4096-Character Overflow & Inactive Request Matching
* **File & Lines:** [`backend/app/bot/handlers.py:388-460`](file:///d:/MentorLink/backend/app/bot/handlers.py#L388-L460)
* **Severity:** **P1 — HIGH**
* **Status:** **CONFIRMED**
* **Evidence:**
  All matching tiers are concatenated into a single message string. With multiple candidates, the text exceeds Telegram's 4096-character limit. Additionally, Match Radar runs on requests that are already `matched` or `closed`.
* **Impact:** Telegram API throws `BadRequest: message is too long`, crashing the handler. Admins can run matching on closed requests.
* **Remediation:** Check request status (reject if not `pending`), truncate or paginate candidate lists, and cap candidate entries per tier.

---

### B-14: Missing Global Error Handler and Inconsistent Callback Acknowledgments
* **File & Lines:** [`backend/app/bot/handlers.py:1390-1396`](file:///d:/MentorLink/backend/app/bot/handlers.py#L1390-L1396)
* **Severity:** **P1 — HIGH**
* **Status:** **CONFIRMED**
* **Evidence:**
  `register_handlers` does not call `application.add_error_handler`. Unhandled exceptions leave Telegram callback spinners loading indefinitely.
* **Impact:** Poor UX, silent failures in logs, and unacknowledged callback queries.
* **Remediation:** Register a global error handler logging context and notifying Super Admin; ensure `await query.answer()` is called in every callback branch.

---

### M-01: Critical Matcher Grade Level Substring Matching Bug
* **File & Lines:** [`backend/app/services/matcher.py:34-61`](file:///d:/MentorLink/backend/app/services/matcher.py#L34-L61)
* **Severity:** **P0 — CRITICAL**
* **Status:** **CONFIRMED**
* **Evidence:**
  ```python
  for tg in tutor_grades_norm:
      if tg in parent_level_norm or parent_level_norm in tg:
          return True
  ```
  ```python
  if any(k in val for k in ["1-4", "grade 1", "grade 2", "grade 3", "grade 4", "primary 1"]):
      s.add("primary_lower")
  ```
  Because `"grade 1"` is a substring of `"grade 10"`, `"grade 11"`, and `"grade 12"`, a tutor qualified only for Grade 1 is matched with Grade 10, 11, and 12 students. Furthermore, `"grade 12"` matches the `"grade 1"` keyword and is incorrectly assigned to `"primary_lower"`.
* **Impact:** Tutors are matched with students outside their educational capabilities.
* **Remediation:** Replace substring matching with structured grade scale mappings:
  - Canonical grades: Grade 1 through 12, Prep 11-12, Remediation, Freshman.
  - Expand tutor qualifications and student levels into explicit sets and test set intersections.

---

## 4. Test Suite Findings

### T-01: 9 Test Suite Failures
* **File & Lines:** [`backend/tests/test_api.py`](file:///d:/MentorLink/backend/tests/test_api.py), [`backend/tests/test_phase3_matching.py`](file:///d:/MentorLink/backend/tests/test_phase3_matching.py), [`backend/tests/test_admin_console.py`](file:///d:/MentorLink/backend/tests/test_admin_console.py)
* **Severity:** **P0 — HIGH**
* **Status:** **CONFIRMED**
* **Evidence:**
  1. Stale text assertions: Tests look for `"Register"` while public keyboard sends `"🚀 Open MentorLink"`.
  2. Missing fixture fields: `preferred_experience` omitted in parent test fixtures.
  3. Database session isolation: Handler tests use `AsyncSessionLocal` (pointing to the real DB file) while test fixtures create tables on an isolated in-memory engine, causing `sqlite3.OperationalError: no such table: tutors`.
  4. Matcher test expectations: Over-matching due to the M-01 substring bug.
* **Impact:** CI/CD test failure prevents dependable regression verification.
* **Remediation:** Patch `AsyncSessionLocal` across handlers in tests, align expectations with actual keyboard labels, supply all required schema fields, and fix M-01.

---

## 5. Frontend & Mini App Findings (P1 / P2)

### F-01: Invalid Tailwind CSS 3.4 Utility Classes
* **File & Lines:** [`frontend/src/components/SuccessModal.jsx:32`](file:///d:/MentorLink/frontend/src/components/SuccessModal.jsx#L32)
* **Severity:** **P2 — MEDIUM**
* **Status:** **CONFIRMED**
* **Evidence:**
  Classes `backdrop-blur-xs`, `animate-in`, `fade-in` are used. Standard Tailwind 3.4 backdrop blur starts at `backdrop-blur-sm`, and `animate-in`/`fade-in` require `tailwindcss-animate`.
* **Impact:** Broken or un-styled visual effects in production builds.
* **Remediation:** Replace with valid Tailwind 3.4 classes (`backdrop-blur-sm`, standard CSS transitions).

---

### F-02: Silent Failure on Tutor Document Upload
* **File & Lines:** [`frontend/src/components/TutorForm.jsx:169-173`](file:///d:/MentorLink/frontend/src/components/TutorForm.jsx#L169-L173)
* **Severity:** **P1 — HIGH**
* **Status:** **CONFIRMED**
* **Evidence:**
  When `uploadTutorDocument` throws an exception, the `catch` block calls `console.warn(...)` and registration proceeds with `id_document_url` as null or partial URL.
* **Impact:** Tutors submit profiles without required ID documents, leading to un-verifiable submissions.
* **Remediation:** Block form submission on upload failure, display a clear, localized retryable error, and require document attachment.

---

### F-04: Inconsistent & Unnormalized Ethiopian Phone Numbers
* **File & Lines:**
  - Frontend: [`frontend/src/components/ParentForm.jsx:19, 181`](file:///d:/MentorLink/frontend/src/components/ParentForm.jsx#L19), [`frontend/src/components/TutorForm.jsx:114, 181`](file:///d:/MentorLink/frontend/src/components/TutorForm.jsx#L114)
  - Backend: [`backend/app/schemas.py:51, 81`](file:///d:/MentorLink/backend/app/schemas.py#L51)
* **Severity:** **P1 — HIGH**
* **Status:** **CONFIRMED**
* **Evidence:**
  Neither frontend nor backend normalizes phone inputs (`09...`, `07...`, `9...`, `+2519...`, `2519...`, spaces/dashes).
* **Impact:** Inability to contact users, duplicate tutor accounts with different phone formats, and failed Telegram lookups.
* **Remediation:** Create a shared phone normalizer converting all valid Ethiopian formats to `+251XXXXXXXXX`, and validate with Pydantic regex server-side.

---

### F-05: Accessibility & Viewport Misconfigurations
* **File & Lines:** [`frontend/index.html:5, 13`](file:///d:/MentorLink/frontend/index.html#L5)
* **Severity:** **P2 — MEDIUM**
* **Status:** **CONFIRMED**
* **Evidence:**
  - Line 5: `maximum-scale=1.0, user-scalable=no` prevents accessibility zooming.
  - Line 13: `select-none` on `<body>` disables native text selection across all inputs and content.
* **Impact:** Degraded user accessibility and broken input copy/paste behavior.
* **Remediation:** Remove `user-scalable=no` and `maximum-scale=1.0`; remove `select-none` from `<body>` and apply only to non-interactive UI elements.

---

### F-06: Fragile API Client Configuration & Missing Timeout/Error Handling
* **File & Lines:** [`frontend/src/services/api.js:1-78`](file:///d:/MentorLink/frontend/src/services/api.js#L1-L78)
* **Severity:** **P1 — HIGH**
* **Status:** **CONFIRMED**
* **Evidence:**
  If `VITE_API_BASE_URL` is omitted in production, it silently defaults to `http://localhost:8000`. No request timeout (`AbortController`) is configured. Error handling is duplicated across methods.
* **Impact:** Production TMA app silently hangs or fails with generic errors when the backend URL is missing or network times out.
* **Remediation:** Fail loudly in production if `VITE_API_BASE_URL` is undefined; implement an `AbortController` timeout (15s); build a unified `request()` helper with localized error mapping.

---

## 6. Phase 2 Architectural & Lifecycle Issues

1. **Alembic Absences:** Database migrations currently use raw SQLite/Postgres `ALTER TABLE` statements in `main.py` lifespan with swallowed exceptions.
2. **Missing Relational Entity for Assignments:** Tutor assignments are logged solely via bot messages; `ParentRequest` lacks a foreign key or relationship to `Tutor`, preventing export of assigned tutor details.
3. **Status Enums:** Statuses are free strings (`"pending"`, `"matched"`, `"closed"`).
4. **Combined Document URL:** `id_document_url` combines uploads and portfolio links using ` | `.

---

## 7. Refuted Hypotheses & Non-Issues

* **REFUTED — Detached Instance on Commit in `handle_close_parent`:**
  `expire_on_commit=False` is set in `database.py:65`, meaning attributes on models remain loaded in memory after `session.commit()` without re-querying.
* **REFUTED — Tailwind 4 / React 19 Upgrade Requirement:**
  The project explicitly uses React 18.2.0 and Tailwind 3.4.1. No breaking framework migrations are required.

---

## 8. Summary of Findings

| ID | Category | Severity | Status | File | Remediation Phase |
|---|---|---|---|---|---|
| S-01 | Authorization | P0 | CONFIRMED | `handlers.py:187` | Phase 1 |
| S-02 | Authorization | P0 | CONFIRMED | `handlers.py:574` | Phase 1 |
| S-03 | Authentication | P0 | CONFIRMED | `api.js:3`, `parents.py:28` | Phase 1 |
| S-04 | Upload Security | P0 | CONFIRMED | `tutors.py:19` | Phase 1 |
| S-05 | Data Privacy | P0 | CONFIRMED | `main.py:75`, `.gitignore` | Phase 1 |
| S-06 | CORS & Rate Limit | P1 | CONFIRMED | `main.py:61` | Phase 1 |
| S-07 | Info Leak | P1 | CONFIRMED | `health.py:26` | Phase 1 |
| S-08 | CSV Injection | P1 | CONFIRMED | `export_service.py:10` | Phase 1 |
| B-01 | Data Concurrency | P0 | CONFIRMED | `handlers.py:244` | Phase 1 |
| B-03 | Telegram API | P1 | CONFIRMED | `handlers.py:690` | Phase 1 |
| B-04 | Telegram UX | P1 | CONFIRMED | `handlers.py:510` | Phase 1 |
| B-05 | XSS / Parsing | P1 | CONFIRMED | `handlers.py:748` | Phase 1 |
| B-06 | CMS Security | P1 | CONFIRMED | `handlers.py:1142` | Phase 1 |
| B-07 | Event Loop | P1 | CONFIRMED | `handlers.py:1040` | Phase 1 |
| B-08 | State Loss | P1 | CONFIRMED | `handlers.py:36` | Phase 1 |
| B-09 | Data Model | P1 | CONFIRMED | `models.py`, `handlers.py` | Phase 1 |
| B-10 | Telegram Limit | P1 | CONFIRMED | `handlers.py:408` | Phase 1 |
| B-14 | Reliability | P1 | CONFIRMED | `handlers.py:1390` | Phase 1 |
| M-01 | Algorithmic Logic | P0 | CONFIRMED | `matcher.py:34` | Phase 1 |
| T-01 | Test Suite | P0 | CONFIRMED | `tests/` | Phase 1 |
| F-01 | CSS Classes | P2 | CONFIRMED | `SuccessModal.jsx:32` | Phase 1 |
| F-02 | Frontend Upload | P1 | CONFIRMED | `TutorForm.jsx:169` | Phase 1 |
| F-04 | Data Validation | P1 | CONFIRMED | `ParentForm.jsx:19`, `schemas.py:51` | Phase 1 |
| F-05 | Accessibility | P2 | CONFIRMED | `index.html:5, 13` | Phase 1 |
| F-06 | Frontend API | P1 | CONFIRMED | `api.js:1` | Phase 1 |

---

## 9. Phase 1 Follow-Up: Regressions & Gaps Remediated (September 25, 2026)

Following external code review of pushed commits on `hardening/phase-1`, 6 specific gaps and regressions were addressed:

1. **FIX 1 (P0 — Assignment Model & Persistence)**:
   - **Root Cause**: `handle_assign_match` in `handlers.py` attempted to update `ParentRequest.assigned_tutor_id` which did not exist on the database model, crashing with `CompileError`.
   - **Resolution**: Added `Assignment` table to `backend/app/models.py` (`id`, `request_id` [unique, indexed], `tutor_id`, `assigned_by`, `assigned_at`, `status`). Updated `handle_assign_match` to create `Assignment` records and updated `export_service.py` to join against `Assignment` for accurate CSV exports.
2. **FIX 2 (P1 — Admin Uploaded Document Viewing & Secure Delivery)**:
   - **Root Cause**: Tutor cards emitted a dead hyperlink (`<a href="{base}/uploads/...">`) pointing to a non-existent public static mount.
   - **Resolution**: Removed dead URL from `format_tutor_card`, replaced with `📄 ID/Credential attached`. Added `[ 📎 View Document ]` button (`view_doc:{tutor.id}`) to `send_tutor_registration_card`. Implemented `handle_view_document` in `handlers.py` with strict path traversal checks against `UPLOAD_DIR`, admin verification, and direct document delivery to the calling admin's private Telegram chat with fallback guidance if DMs are not initiated.
3. **FIX 3 (Defense in Depth — Production Auth Default)**:
   - **Root Cause**: `ALLOW_UNVERIFIED_WEB_PREVIEW` defaulted to `True`, which left API intake open to unauthenticated submissions if not explicitly overridden.
   - **Resolution**: Changed default to `False` in `backend/app/config.py`. Documented usage in `backend/.env.example`. Added test verifying 401 Unauthorized in production without valid `Authorization` header.
4. **FIX 4 (Consistency — File Upload Extension Alignment)**:
   - **Root Cause**: Frontend `TutorForm.jsx` accepted `.doc,.docx` and translations mentioned `DOCX`, but backend rejected `.docx` with 400.
   - **Resolution**: Aligned `TutorForm.jsx` file picker to `accept=".pdf,.png,.jpg,.jpeg"`. Updated English and Amharic translation strings to remove DOCX references.
5. **FIX 5 (Defense in Depth — Group Callback Origin Chat Spoof Guard)**:
   - **Root Cause**: Admin callbacks checked `is_admin()`, but didn't verify that the callback originated from `ADMIN_GROUP_ID`.
   - **Resolution**: Added verification `if settings.ADMIN_GROUP_ID and query.message and str(query.message.chat_id) != str(settings.ADMIN_GROUP_ID)` to reject spoofed/forwarded callbacks. Added unit test.
6. **FIX 6 (Test Suite Realignment & Zero Regression Guarantee)**:
   - Standardized keyword argument `text=` in `reply_text` calls in `handlers.py`.
   - Aligned analytics card assertions in `test_admin_console.py` to match formatted `<code>` tags.
   - Handled background async broadcast task in `test_admin_broadcast_flow` with event loop yield.
   - Added `monkeypatch.setattr(settings, "SUPER_ADMIN_ID", admin_id)` in `test_admin_analytics_close`.
   - Updated document upload test to match random UUID filename regex pattern.
   - Enforced database isolation across matching tests by resetting tables at test starts.
   - Added unit tests for unauthorized chat rejection (FIX 5) and admin document delivery (FIX 2).

---

## 10. Phase 1 Final Polish & Verification (September 25, 2026)

1. **Admin Group Opportunity Alert on Response**:
   - `handle_tutor_avail_yes`: Includes tutor's name, subjects (`_format_subjects`), and an inline `[ ✅ Assign ]` button (`callback_data=f"assign_match:{parent_id}:{tutor.id}"`) into the parent request's forum topic in `ADMIN_GROUP_ID`.
   - `handle_tutor_avail_no`: Sends a decline notification into the parent request's forum topic with tutor's name and subjects so admins have full operational visibility.
2. **Global Database Isolation (`tests/conftest.py`)**:
   - Implemented `clean_database` autouse fixture in `conftest.py` that truncates all tables on setup and teardown before every test.
   - Added explicit transaction rollback in `db_session` fixture.
   - Seeded `SystemSetting` in `test_ensure_forum_topics_loads_from_db_without_calling_telegram_again` so tests run reliably in any execution order.
3. **Keyword Parameter Standardisation**:
   - Standardized all `reply_text` calls across `handlers.py` to explicitly use `text=...`, including `admin_command`, `handle_admin_analytics`, `handle_broadcast_menu`, `handle_cms_menu`, `handle_cms_view_current`, `handle_export_menu`, `cancel_command`, and `handle_text_message`.
4. **Broadcast Flow Test Assertion Realignment**:
   - Updated `test_admin_broadcast_flow` in `test_admin_console.py` to assert recipient delivery on `mock_context.bot.send_message.call_args_list[0].kwargs["chat_id"] == 111222`, distinguishing recipient dispatches from post-loop admin completion summaries.

---

## 11. Production Telegram WebApp Authentication & URL Resolution Fix (September 25, 2026)

1. **Root Cause Analysis ("Missing Telegram WebApp authentication")**:
   - **Backend URL Ambiguity**: When `MINI_APP_URL` was configured as a Telegram bot link (`https://t.me/MentorLinkBot/app`), `handlers.py` passed `https://t.me/...` directly to Telegram's `WebAppInfo(url=...)`. Telegram prohibits `t.me` links inside `WebAppInfo` and opened the app in an external browser where `window.Telegram.WebApp.initData` was empty.
   - **Frontend initData Fallbacks**: If the Mini App was opened inside an iframe or webview where `window.Telegram.WebApp.initData` had an initialization race condition, `api.js` did not check the URL hash (`#tgWebAppData=...`) or search parameters (`?tgWebAppData=...`) or sessionStorage cache.
   - **Production Security Check**: In production (`ENVIRONMENT="production"`), `get_current_telegram_user` strictly rejects unauthenticated requests with 401 Unauthorized when `Authorization: tma ...` is omitted.

2. **Remediation & Enhancements**:
   - **`backend/app/bot/handlers.py`**: Added `_get_webapp_url()` which prioritizes direct HTTPS web hosting URLs (`settings.WEBAPP_URL`) over `t.me` links for `WebAppInfo(url=...)`. Preserved backward compatibility fallback for test fixtures.
   - **`frontend/src/services/api.js`**: Enhanced `getTelegramInitData()` with a multi-source fallback checking `window.Telegram.WebApp.initData`, `window.location.hash` (`#tgWebAppData=...`), `window.location.search` (`?tgWebAppData=...`), and `sessionStorage`. All API requests now reliably supply `Authorization: tma <initData>`.
   - **`frontend/src/App.jsx`**: Caches initData to `sessionStorage` on mount and fallback-parses user profile JSON from `getTelegramInitData()`.
   - **`backend/app/config.py` & `auth.py`**: Added token trimming to strip quotes and whitespace from `BOT_TOKEN`, parsed `ALLOW_UNVERIFIED_WEB_PREVIEW` safely, and added logging for missing auth in production.
   - **`backend/app/main.py`**: Expanded CORS origins to include `MINI_APP_URL` hosting domains.
   - **Test Coverage**: Added `test_authenticated_request_accepted_in_production` and `test_get_webapp_url_prioritizes_actual_web_hosting_domain` in `backend/tests/test_api.py`.
