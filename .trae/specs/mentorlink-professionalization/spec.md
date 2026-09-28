# MentorLink Professionalization Release - Product Requirements Document

## Overview
- **Summary**: End-to-end release that resolves the 6 user-identified platform problems and professionalizes MentorLink: (1) fixes tutor assignment DM content (stop sending only phone numbers), (2) collapses fragmented admin roles into 2 tiers (super_admin + admin), (3) ships MVP business features across all 3 user roles, (4) fixes "Review in App" deep-link reliability, (5) brand-aligned UI overhaul across admin + customer frontends using the official MentorLink palette, and (6) backend hardening and refactor.
- **Purpose**: Eliminate the operational bugs (missing assignment data, broken buttons, role-siloed admins, frontend brand disconnect) that block day-to-day tutoring operations and unlock the basic business tooling the platform needs to scale operations efficiently.
- **Target Users**: Super admins, operational admins, tutors (mentors), and parents (customers).

## Goals
- **G-1**: When an admin assigns a tutor to a parent request, the tutor receives ALL the assignment data (parent name + student context, subjects, location subcity/landmark, schedule days + time + duration, budget/rate, parent phone, plus a Mini App deep-link back to the request) — not just the parent's phone number.
- **G-2**: Every active admin user has uniform access to all operational actions (ping candidates, assign, verify, reject, close, waitlist, nudge, coverage, analytics, exports). Only admin-CRUD and audit-log remain super_admin-only.
- **G-3**: MVP business modules exist and are functional end-to-end for all three user roles, backed by real endpoints and real data.
- **G-4**: "Review in App" buttons on every admin group card (request topic, index, tutor) are always present, always clickable, and always open the correct admin Mini App detail view — never silently omitted and never falling back to bot chat.
- **G-5**: Both the admin Mini App UI AND the customer-facing TWA (Find-a-Tutor / Become-a-Tutor forms) render with a uniform MentorLink brand identity: consistent tokens, consistent typography, no stray Tailwind defaults, matching header, surfaces, and accents.
- **G-6**: Backend code quality reaches modern professional standards: validated inputs, structured JSON error responses everywhere, no swallowed exceptions, no bare `except: pass`, every admin route returns `4xx/5xx with consistent shapes, and sensitive comparisons use constant-time.

## Non-Goals
- **NG-1**: No full booking/calendar engine (scheduling views render captured data only; no drag-drop calendar with double-booking prevention).
- **NG-2**: No real-time in-app chat. Parent↔tutor communication remains human-mediated via Telegram bot DMs and phone contact shared at assignment time.
- **NG-3**: No payment processing, Stripe integration, or financial transactions; "tuition management" is assignment status tracking + session counts only.
- **NG-4**: No changes to the existing match-scoring algorithm or tutor ranking logic; the scoring engine is out of scope.
- **NG-5**: No new languages; keep en/am bilingual support only.
- **NG-6**: No React Router introduction; customer TWA continues with its current state-based tab navigation model.
- **NG-7**: No new student_name DB column; parent_name + student_level are used as the student-identifying context in all cards.

## Background & Context
Current state per codebase audit (2026-09-28):

### 1. Assignment DM Bug (Root cause):
In [admin.py#L365-383], the `/requests/{id}/assign endpoint sends the tutor only: `You have been assigned to a tutoring request from {parent.parent_name}. Contact: {parent.phone_number}` — a single line. Missing: subjects, location, schedule (days + time + duration), student level, budget, request ID, and any deep link back to the request. The parent DM is similarly truncated: only tutor name + phone only.

### 2. Admin Role Fragmentation:
Four roles exist: `super_admin`, `matcher`, `verifier`, `admin`. Per [schemas.py#L334] regex allows all four; per [admin_auth.py#L40-50] require_role gates:
- `matcher` only: ping + assign (lines 223,324)
- `verifier` only: verify + reject (lines 570,627)
- `admin` (generic): read-only dashboard/list only
- `super_admin`: all + admin CRUD + audit
Operational reality: all admins sit in the same Telegram group and are expected to do all tasks. Bot-level `is_admin` in handlers.py#L85-113 already recognizes only `admin` + `super_admin`.

### 3. Business Features:
**Admin side**: Dashboard exists with counts (basic). No: customer CRM (search/edit parent, see request history), reporting (conversion funnel), assignment tracking (pipeline by status + aging). AnalyticsBoard exists but coverage gap only — no operational-efficiency modules. ExportCenter CSV exports (tutors + requests, no assignment-level export.
**Tutor side**: No dashboard at all post-registration. No: schedule view of assigned students / upcoming sessions / session count / avg rating / earnings tracker.
**Parent side**: No post-submission dashboard. No: communication (message admin / view assigned tutor / submit session feedback / view session count + payment tracking.

### 4. Broken Review in App Buttons:
Per earlier patch, MINI_APP_URL → t.me link + ADMIN_MINI_APP_SHORT_NAME → None → fallback + one-time warn + startup self-check diagnostic are IN PLACE already. Frontend start_param parser works for admin. Still need: (a) consistent addition of assignment-level "Review in App" for tutor/parent assignment DMs, (b) cross-role navigation tests ensure parent working pattern (callback_data) replicated, (c) regression tests verify the button never omitted paths always include the correct short_name present, and full.

### 5. Brand Palette:
Single source of truth = admin.css :root (8 tokens: ink #172924, pine #183b34, muted #78847c, line #e2e7df, paper #fbfcf9, coral #c35d47, green #27715e, citrus #a88221). Customer index.css has 0 color tokens and relies on Tailwind defaults (random blues/greens). Tailwind config has only telegram.* (Telegram palette only, no MentorLink tokens). Hardcoded scattered #dc2626/#2563eb etc exist in admin.css classes.

### 6. Backend Quality:
→ Already: Schema bare except exist in assignment DMs (fixed in previous patch but check remainder of codebase; check all error response struct (schemas response shapes; ensure no pydantic validation error consistent 422 detail format; check remaining bare excepts handlers.py and elsewhere).

## Functional Requirements

### Assignment Content (User Story 1 — Core Notification Bug)
- **FR-1.1**: Tutor assignment DM (`POST /admin/requests/{id}/assign send_message to tutor MUST include: parent name, student level, subjects (comma-separated), location (subcity + landmark), schedule (days + time slot + duration), hourly budget ETB/hr, parent phone_number, request ID, and a Review in App deep link when available.
- **FR-1.2**: Parent assignment DM MUST include: tutor full name, subjects, education summary (university + dept + year), years of experience, base subcity + coverage, phone, request ID, deep link when available.
- **FR-1.3**: Assignment messages use the same HTML formatting template (bold sections (contact/requirement/location/schedule blocks as `format_parent_card` + `format_tutor_card` so formatting is consistent.
- **FR-1.4**: Assignment DM send failures are logged with request ID + tutor/parent ID + role. No bare pass silently fails the API returns 200 regardless (assignment always commits; DM failures are non-fatal and logged).
- **FR-1.5**: A new `format_assignment_card_tutor(parent_req, tutor, assignment_id)` helper produces a structured HTML card block for tutors.
- **FR-1.6**: A new `format_assignment_card_parent(parent_req, tutor, assignment_id)` helper produces a structured HTML card block for parents.

### Story 2 — Admin Role Simplification (Single-Tier Admin)
- **FR-2.1**: `schemas.py role regex allows only `admin` + `super_admin`. Matcher, verifier removed from pattern.
- **FR-2.2**: `require_role` gates removed from ping/assign/verify/reject → all moved to `require_admin` (any active admin). Only `super_admin` guards retained for `GET/POST /admins`, DELETE /admins/{id}` and `GET /audit`.
- **FR-2.3**: Existing `matcher` or `verifier` rows in DB get migrated in-appearing as `admin` role transparently (mapping layer; existing DB rows are not rewritten; auth layer normalizes).
- **FR-2.4**: Bot-level `is_admin` in handlers.py → already correctly handles this; ensure bot callback handlers (match_parent / close_parent / verify / reject → any active admin, regardless of old role string.
- **FR-2.5**: Admin-management UI (AdminManagement.jsx role selector → shows 2 options only (admin vs super_admin); AdminUserCreate defaults to admin.

### Story 3 — Business Optimization Features
- **FR-3.1 Admin CRM**: Admin side → Customer CRM module (searchable parent request list with: search by parent name / phone / subcity, open/closed filter, view full request history per parent (open a parent detail drawer showing all requests, assignments, dates, statuses).
- **FR-3.2 Admin Reporting Dashboard**: Dashboard module counts → expanded: request-to-assignment conversion %, tutor verification funnel %, avg time-to-assign (days), avg tutor salary estimator per subject/draw a small widget with numbers only (tabular summary; CoverageBoard + AnalyticsBoard enhanced).
- **FR-3.3 Admin Assignment Tracking**: Pipeline view by status counts, per-status median-age oldest-10 list; search by status; bulk actions close/waitlist).
- **FR-3.4 Admin Export Center**: assignment CSV export (columns assignment id, parent, tutor, subject(s), status, created, assigned_date, closed_date); link to existing tutor/request CSV already.
- **FR-3.5 Tutor Dashboard**: After Tutor tab "My Assignments" — list: student name context, subject, location, next-session info, session count completed, avg session feedback star avg, estimated ETB accumulated fee tracker running total shows).
- **FR-3.6 Parent Dashboard → After submission: "My Tutor(s)" view assigned tutor card + phone + subjects + session counter, session counter progress timeline; Submit Feedback button → post feedback 1-5 star comment box; Contact Admin button → sends bot DM to admin group on parent's behalf; tuition status tracking count + admin messages admin on DM notification count).

### Story 4 — Fix Review in App Functionality
- **FR-4.1**: Assignment DM content (see FR-1) includes the "Review in App" deep link for admins; uses same startapp=request_{id} pattern; ensures it renders when can be clicked works correctly (no silent omit).
- **FR-4.2**: Existing self-check startup `check_review_link_config()` always called during app startup.
- **FR-4.3**: `_review_url_warning_logged one-time warning prints once per server start works; subsequent calls silent.
- **FR-4.4**: Test verifies button renders or routes all (tutor card, parent topic card, index card, assignment DM cards → all build when MINI_APP_URL valid t.me link; all None fallback builds fallback short_name exactly.

### Story 5 — Brand Frontend Design
- **FR-5.1 Mirror all 8 brand tokens to Tailwind config `theme.extend.colors` → bg-pine, text-pine, etc.).
- **FR-5.2 index.css root declares the same 8 CSS custom properties (so both vanilla CSS + Tailwind both see them).
- **FR-5.3 Header component refactored to use MentorLink brand gradient pine→ink gradient header + mentorlink logo mark (recreate the admin css brand-header style brand css brand mark classes).
- **FR-5.4 ParentForm + TutorForm use all inputs styled with paper surfaces line borders ink text; focus states pine; buttons; primary submit bg-pine text-paper; secondary uses).
- **FR-5.5 SuccessModal uses brand success green not Tailwind green; coral-colored not default).
- **FR-5.6 TabNavigation pill-styled using brand tokens (active bg-paper shadow; inactive use line).
- **FR-5.7 Admin side consistency: remove all stray hardcoded #dc2626, #2563eb, #059669 etc. → use --coral / --pine / --green. No admin.css admin.css admin hardcoded colours cleaned.
- **FR-5.8**: Typography uses consistent font weights, font for headers; uses font DM Mono consistent for labels/money).

### Story 6 — Backend Logic Professionalization
- **FR-6.1**: Full backend codebase audit: grep for `bare pass and logger.warning / logger.error / exception context).
- **FR-6.2**: All endpoints return structured error JSON (all 4xx/5xx → `detail` field; all `errors? No non-JSON plain text bodies; unhandled exc handler previously patched; validation errors pydantic Vermanager ensure consistent shape).
- **FR-6.3**: HMAC compare everywhere secret comparison — cron + any token equality checks all using constant time string compare
- **FR-6.4**: Input validation expanded — phone numbers Ethiopian normalized, string length boundaries enforced, enum values validated; routes use tighter schemas.py).
- **FR-6.5**: DB query performance — N+1 detection in list endpoints add joinedload selectinload parent/tutor eager loads where needed; no N+1.

## Non-Functional Requirements
- **NFR-1 Performance**: Admin list endpoints (requests, tutors) respond <500ms for a 500-row dataset on Render dev tier.
- **NFR-2 Security**: No plaintext logged secrets; no timing attacks on cron secret/Telegram init data checks; CORS origin exact matching.
- **NFR-3 Reliability**: Assignment endpoint never partial-writes (assignment commit + audit rows atomic transaction).
- **NFR-4 Testability**: Backend test suite ≥125 tests (up from 110) after additions) 0 failures. Frontend build 0 errors 0 warnings.
- **NFR-5 Maintainability**: Admin role constants centralized in a single source of truth (auth layer normalizes legacy values).
- **NFR-6 Accessibility**: Color contrast ratios ≥ 4.5:1 on all text/background combinations in both UIs.
- **NFR-7 Backwards compat**: Old links, existing env vars still work; role values `matcher`/`verifier` DB rows behave as `admin` without data migration needed; API unchanged env names unchanged.

## Constraints
- **Technical**: FastAPI + SQLAlchemy 2.0 async + PostgreSQL/Alembic, React 18 + Vite + Tailwind v3, python-telegram-bot v20 (asyncio). No React Router added. No new heavy npm/pip packages.
- **Business**: All existing data preserved. All existing Telegram links/cards unchanged. Admin flow preserved. Deployment targets: Render backend (Pre-Deploy alembic upgrade head), Vercel frontend, GitHub Actions cron → unchanged.
- **Dependencies**: lucide-react icons already present. No new backend libraries.

## Assumptions
- **A-1**: The 8-token admin.css :root palette IS the official MentorLink brand identity per user confirmation — pine, ink, paper, coral, green, citrus, muted, line.
- **A-2**: No new DB column student_name added per user confirmation; parent_name + student_level student-identifying context.
- **A-3**: End-to-end MVP scope: working functional API endpoints + functional UI views connected real data.
- **A-4**: Tutor/parent dashboards live in the existing TWA (Telegram Web App) single index.html entry as new post-submission views) — no new separate Mini App registration, no new admin TWA mini required.

## Acceptance Criteria

### AC-1: Tutor assignment DM includes all required fields
- **Type**: `rule`
- **Given**: A verified tutor, a parent request, admin calls POST /requests/{id}/assign succeeds
- **When**: The bot sends the assignment DM to the tutor's telegram_user_id
- **Then**: The DM HTML text contains parent_name, student_level, subjects string, location_subcity, schedule_days, time_slot, session_duration, budget_etb formatted, parent phone_number, request ID, and a Review in App URL
- **Pass Condition**: HTML contains all 10 substrings/fields; pytest passes on 3 different seeded fixtures
- **Evidence**: `pytest tests/test_admin_api.py::test_assignment_dm_content_complete_for_tutor` (new test) green

### AC-2: Parent assignment DM includes all required tutor fields
- **Type**: `rule`
- **Given**: Same fixture assignment event
- **When**: The bot sends the DM to the parent
- **Then**: DM contains tutor full_name, university, department, education_year, years_of_experience, phone_number, base_subcity, subjects, request ID, Review URL
- **Pass Condition**: 10 fields present; pytest green
- **Evidence**: `pytest tests/test_admin_api.py::test_assignment_dm_content_complete_for_parent` (new test) passes

### AC-3: Role gates removed — any admin (role=admin) can ping/assign/verify/reject
- **Type**: `rule`
- **Given**: An active AdminUser with role="admin"
- **When**: It hits POST /ping, POST /assign, PATCH /verification, POST /reject endpoints with valid telegram init data
- **Then**: All return 2xx; none return 403
- **Pass Condition**: 4 endpoints × role=admin → all 2xx in test; old test `test_require_role_rejects_admin_without_required_role` updated/removed/replaced with new test showing 2xx for generic admin
- **Evidence**: pytest files role tests show admin generic allowed on all 4 ops

### AC-4: Only super_admin can access admin-CRUD and audit
- **Type**: `rule`
- **Given**: role="admin" (not super)
- **When**: GET /admins, POST /admins, DELETE /admins/{id}, GET /audit
- **Then**: All 4 return 403. super_admin variant returns 2xx
- **Pass Condition**: 4 endpoints × 2 roles matrix passes
- **Evidence**: pytest tests pass

### AC-5: Legacy matcher/verifier role rows treated as admin
- **Type**: `rule`
- **Given**: AdminUser row in DB with role="matcher" or role="verifier"
- **When**: require_admin loads it
- **Then**: principal.role returned is normalized to "admin" (or the raw is accepted) and the user passes any admin-only gates
- **Pass Condition**: tests with seeded DB rows old role → full operational access; no 403s
- **Evidence**: New pytest role normalization tests pass

### AC-6: Admin Customer CRM — search parent by name/phone
- **Type**: `rule`
- **Given**: 10 seeded parent requests
- **When**: admin calls GET /admin/parents?search=… with partial name or phone
- **Then**: returns filtered list with matching parents; status filter (all status filter. HTML no results for non-matches
- **Pass Condition**: 3 different search queries match correctly
- **Evidence**: pytest new endpoint tests

### AC-7: Admin expanded dashboard metrics
- **Type**: `rule`
- **Given**: Seeded assignment/closed data
- **When**: GET /admin/dashboard returns payload
- **Then**: Response includes: conversion_rate_pct, avg_days_to_assign, tutor_verification_funnel_pct fields present numeric fields
- **Pass Condition**: all 3 present; values correct based on seeded rows; tests verify arithmetic
- **Evidence**: pytest dashboard metric tests pass

### AC-8: Assignment pipeline view endpoint
- **Type**: `rule`
- **Given**: Requests in 5 different statuses
- **When**: GET /admin/assignments/pipeline fetched
- **Then**: Returns per-status counts, per-status median age, oldest-10 per status
- **Pass Condition**: counts match seeded
- **Evidence**: pytest passes

### AC-9: Assignment CSV export includes assigned_date, closed_date columns
- **Type**: `rule`
- **Given**: assigned and closed assignments in DB
- **When**: Export CSV endpoint
- **Then**: CSV includes assignment id, parent, tutor, subjects, status, assigned_date, closed_date
- **Pass Condition**: CSV parsed rows contain columns data matches seeded
- **Evidence**: pytest export includes tests

### AC-10: Tutor My Assignments list API
- **Type**: `rule`
- **Given**: A tutor telegram_user_id with 2 active + 1 closed assignment
- **When**: GET /tutors/me/assignments authenticated via Telegram init auth
- **Then**: Returns list, each row: parent_name context (parent+level), subjects, location, next_session (if any), sessions_completed count, avg_rating, estimated_earnings_etb sum
- **Pass Condition**: 3 rows, fields computed; pytest auth required (401 without telegram init data)
- **Evidence**: new endpoint tests

### AC-11: Parent My Tutors + Feedback endpoint
- **Type**: `rule`
- **Given**: parent telegram_user_id has 1 assigned request
- **When**: GET /parents/me/requests returns list; POST /parents/me/feedback submits 1-5 stars+comment
- **Then**: list returns tutor info; feedback saved to AssignmentFeedback model; rating shows tutor avg_rating updated
- **Pass Condition**: list + feedback endpoints; seeded pytest scenario passes
- **Evidence**: new feedback endpoint tests

### AC-12: "Review in App" button never silently omitted for well-configured MINI_APP_URL
- **Type**: `rule`
- **Given**: settings.MINI_APP_URL = "https://t.me/MentorLinkBot/admin" valid
- **When**: bot_instance produces: parent request card, index card, tutor card, tutor assignment DM, parent assignment DM
- **Then**: Every card's InlineKeyboard includes at least one InlineKeyboardButton with url= starting with the t.me link + startapp=
- **Pass Condition**: 5 card types × 1 Review button each → pytest inspects keyboard structure
- **Evidence**: new bot_instance card keyboard tests

### AC-13: Review URL startup self-check always runs
- **Type**: `rule`
- **Given**: App lifespan startup
- **When**: check_review_link_config called
- **Then**: Logs INFO level message containing "Review in App" sample URL
- **Pass Condition**: caplog captures log during test startup or direct call
- **Evidence**: existing test_deployment_readiness.py existing tests + new assignment cards test pass

### AC-14: Brand tokens mirrored in Tailwind config
- **Type**: `rule`
- **Given**: tailwind.config.js loaded
- **When**: a component uses className="bg-pine text-paper border-line text-coral bg-green bg-citrus text-muted bg-ink"
- **Then**: Tailwind CSS output includes rules with exact hex values (#183b34 for pine, etc.)
- **Pass Condition**: grep tailwind config, colors block lists all 8 tokens
- **Evidence**: manual file inspection + frontend build output contains all 8 hex values

### AC-15: Customer UI uses brand palette — no Tailwind default greens/blues
- **Type**: `rubric`
- **Dimension**: Brand palette fidelity on customer-facing TWA
- **Scale**: 1-5
- **Anchors**: 1 = Tailwind default green/blue everywhere; 3 = header/buttons brand-colored, some inputs still default; 5 = every surface, button, badge, input border, link rendered exclusively MentorLink tokens (ink/pine/paper/coral/green/citrus/muted/line), zero Tailwind stock colour utilities (bg-green-*, text-blue-*, etc.) anywhere in customer components.
- **Pass Threshold**: >= 4
- **Evidence**: git diff src/components/* + index.css; visual inspection screenshot of each of: Header, TabNavigation, ParentForm, TutorForm, SuccessModal screenshots
- **Notes**: Hardcoded hex replaced with Tailwind pine/ink/paper/coral/green/citrus/muted/line tokens

### AC-16: Admin UI stray hardcoded colors replaced with tokens
- **Type**: `rubric`
- **Dimension**: Admin CSS stray hardcoded hex clean-up
- **Scale**: 1-5
- **Anchors**: 1 = 10+ stray hardcoded #dc2626, #2563eb, #059669; 3 = danger/success/status use tokens but analytics still custom; 5 = every status, button, badge class in admin.css references only the 8 tokens plus their Tailwind equivalents, 0 stray hardcoded hex values of semantic meaning (only brand-mark internal dot allowed as accents).
- **Pass Threshold**: >= 4
- **Evidence**: grep admin.css for hex literals; count <= 3 (only brand-mark decorative accents)

### AC-17: Backend no bare `except: pass`
- **Type**: `rule`
- **Given**: Entire backend/ app source tree
- **When**: grep -rn "except.*:.*pass" backend/app
- **Then**: 0 matches except test-only code
- **Pass Condition**: zero occurrences (after audit + replacement with logger.warning/error)
- **Evidence**: grep command output empty string

### AC-18: Backend test suite 0 failures, >= 125 tests total
- **Type**: `rule`
- **Given**: Current working tree
- **When**: `python -m pytest -q` in backend/
- **Then**: Exit code 0; output line "XXX passed" where XXX >= 125
- **Pass Condition**: Exit 0, passed count >=125
- **Evidence**: Full pytest log output

### AC-19: Frontend production build 0 errors, 0 warnings
- **Type**: `rule`
- **Given**: Current frontend/ working tree
- **When**: `npm run build` completes
- **Then**: Exit 0, no "[error]" or "[warning]" lines in output (vite build console output)
- **Pass Condition**: Exit 0; 0 warnings
- **Evidence**: vite build stdout

### AC-20: Role selector on Admin CRUD offers only (admin/super_admin)
- **Type**: `rule`
- **Given**: AdminManagement.jsx rendered
- **When**: Role dropdown inspected; schemas.py AdminUserCreate field regex
- **Then**: 2 options only admin/super_admin
- **Pass Condition**: schemas regex matches admin|super_admin only; frontend dropdown 2 items
- **Evidence**: Source inspection + tests

## Open Questions
- None. Three material ambiguities (brand palette, student_name field, feature scope) were resolved via user input on 2026-09-28: palette adopt admin everywhere, no student_name column, end-to-end MVP scope.
