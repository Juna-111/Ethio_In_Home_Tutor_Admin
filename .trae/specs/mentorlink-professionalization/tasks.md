# MentorLink Professionalization Release - Implementation Plan

## Task 1: Admin Role Simplification (Backend + Frontend)
- **Status**: `pending`
- **Priority**: high
- **Depends On**: None
- **Description**:
  - Collapse 4-role system to 2 tiers. Update schemas.py role regex to `admin|super_admin`.
  - Remove `require_role("matcher"|… / "verifier"` gating on ping, assign, verification, reject → all changed to `require_admin` (any active admin). Keep super_admin only for admin CRUD + audit.
  - Add legacy role normalization in `require_admin`: if DB row role is `matcher` or `verifier`, treat principal as `admin` transparently (no data rewrite needed — backward compat).
  - Bot-level callback handlers (verify/reject/match/close) in handlers.py → unify to accept any admin regardless of stored role string; update `_admin_roles cache loader` to normalize legacy → admin.
  - Frontend: AdminManagement role selector → 2 options only (admin / super_admin); default admin.
  - Update/remove existing tests that enforce matcher/verifier rejection; replace with tests showing generic admin can do all 4 operational actions.
- **Acceptance Criteria Addressed**: AC-3, AC-4, AC-5, AC-20
- **Test Requirements**:
  - `rule` TR-1.1: Generic admin (role="admin") hits all 4 operational endpoints (ping/assign/PATCH verify/POST reject) → all 2xx, no 403.
  - `rule` TR-1.2: role="admin" (not super) → 403 on GET/POST/DELETE /admins and GET /audit endpoints; super_admin 2xx.
  - `rule` TR-1.3: Seeded DB matcher role user → principal resolved to admin access; same for verifier.
  - `rule` TR-1.4: schemas.py role regex rejects "matcher"/"verifier" string on create; accepts admin/super_admin.
  - `rule` TR-1.5: AdminManagement create dropdown renders exactly 2 role options (frontend render check via source grep).
- **Notes**: Backwards compatible. No Alembic migration needed (raw DB strings untouched; auth layer normalizes read-time).

## Task 2: Backend Quality Audit (Hardened)
- **Status**: `pending`
- **Priority**: high
- **Depends On**: None
- **Description**:
  - Grep entire backend/app for `except.*:.*pass` → replace with `logger.warning/error(exc_info=True)` with request/entity IDs context.
  - Audit all routes for consistent error shapes: any endpoint that raises plain HTTPException without JSON `detail` is updated; unhandled exc handler from previous patch already covers 500s; ensure 422s from pydantic Vermanager render consistent JSON shape with `detail` list.
  - Audit all secret/token comparisons: any `==` string for cron/Telegram init data/HMAC → switch to `hmac.compare_digest`.
  - Expand input validation schemas.py: tighten string max_lengths, any free-form text fields, add html.escape sanitation on any string displayed in HTML parse_mode bot messages (handled at render-time — defensive double-escape safety).
  - Audit list endpoints for N+1: ensure joinedload on parent requests, tutors where joined attributes accessed.
- **Acceptance Criteria Addressed**: AC-17
- **Test Requirements**:
  - `rule` TR-2.1: `grep -rln "except.*:.*pass" backend/app` → 0 matches or matches only inside `tests/`.
  - `rule` TR-2.2: Sample 5 endpoints return JSON `detail` field on 400/403/404/422/500 (integration test using TestClient/httpx).
  - `rule` TR-2.3: No `==` on cron_secret; all using `hmac.compare_digest` (grep source confirm).
  - `rubric` TR-2.4: Code maintainability after refactor; scale 1-5; anchors 1=inconsistent logging; 3=some routes log; 5=every exception path + every write operation has structured logger.xxx with IDs context; threshold >= 4.

## Task 3: Brand Token System — Tailwind + index.css
- **Status**: `pending`
- **Priority**: high
- **Depends On**: None
- **Description**:
  - Update tailwind.config.js → theme.extend.colors add `ink, pine, muted, line, paper, coral, green, citrus` each with exact hex values (#172924, #183b34, #78847c, #e2e7df, #fbfcf9, #c35d47, #27715e, #a88221).
  - Update index.css `:root` block to declare same 8 CSS custom properties (so both vanilla CSS class styles and Tailwind utilities use same source).
  - Update index.css `body` background → #f1f3ef (matching admin page bg); default color ink #172924; font-family already set.
  - Add 1-pixel CSS reset (box-sizing: border-box, etc.) if missing — ensure consistent rendering with admin UI.
- **Acceptance Criteria Addressed**: AC-14
- **Test Requirements**:
  - `rule` TR-3.1: `tailwind.config.js` contains all 8 hex tokens under `theme.extend.colors`.
  - `rule` TR-3.2: `index.css` :root block declares all 8 --ink, --pine, etc. variables with identical values.
  - `rule` TR-3.3: Frontend build succeeds (later task validates); no Tailwind warnings on unknown tokens.
- **Notes**: Foundation task for Task 10 (customer brand overhaul) and Task 11 (admin CSS cleanup).

## Task 4: Assignment DM Content Fix (Core Notification Bug)
- **Status**: `pending`
- **Priority**: high
- **Depends On**: None
- **Description**:
  - Add two new HTML template helpers in bot_instance.py: `format_assignment_card_tutor(parent_req, tutor, assignment_id)` and `format_assignment_card_parent(parent_req, tutor, assignment_id)`.
  - Tutor card sections: HEADER (Assignment #id), CONTACT (Parent, Phone, Telegram handle if set), STUDENT CONTEXT (student_level + parent name as household), SUBJECTS, LOCATION (subcity + landmark), SCHEDULE (days + time slot + duration), RATE (budget ETB/hr), Review in App URL if resolvable.
  - Parent card sections: HEADER, TUTOR INFO (name, years exp, education: university + dept + year), QUALIFIED SUBJECTS, LOCATION (base subcity), TUTOR CONTACT (phone), TEACHING AREAS (coverage list), Review in App URL if resolvable.
  - Update `assign_admin_request` in routes/admin.py to use the new formatters instead of the single-liners. Send as separate card + keyboard (the Review URL as inline button).
  - Keep the resilience: any send failure → logger.warning with IDs; assignment commits still 2xx.
- **Acceptance Criteria Addressed**: AC-1, AC-2, FR-1.1 to FR-1.6
- **Test Requirements**:
  - `rule` TR-4.1: Tutor DM text (captured via bot mock) contains substrings: parent_name, student_level, subjects.join, location_subcity, schedule_days rendered, time_slot, session_duration, budget_etb with "ETB/hr", parent phone_number.
  - `rule` TR-4.2: Parent DM text contains: tutor full_name, university, department, education_year, years_of_experience formatted, base_subcity, subjects_qualified rendered, tutor phone_number, request ID.
  - `rule` TR-4.3: When `MINI_APP_URL` valid → InlineKeyboard for tutor DM and parent DM messages include at least one url button with `startapp=request_` prefix (captured via mock call_args).
  - `rule` TR-4.4: When bot send fails (mock raises Exception), endpoint still returns 2xx and audit/assignment rows committed; warning line logged with IDs.

## Task 5: Admin CRM Search + Request History Endpoints
- **Status**: `pending`
- **Priority**: medium
- **Depends On**: Task 1 (for role access)
- **Description**:
  - Add GET `/admin/parents` search endpoint: Query params `search` (parent_name/phone_number ilike), `status` (single), `page`, `page_size`.
  - Add GET `/admin/parents/{parent_request_id}/history` — returns all requests found by same phone_number matching the parent's phone (a proxy for a household parent history), ordered by created_at desc, each with: id, status, subjects, created_at, assignment info if any (tutor short id).
  - Existing list_admin_requests already exists; keep it. Add optional `search_by_parent` param that matches parent name or phone ILIKE as alias for new CRM search.
  - Schemas: `ParentCRMItem`, `ParentHistoryResponse` response models.
- **Acceptance Criteria Addressed**: AC-6
- **Test Requirements**:
  - `rule` TR-5.1: Seeded 10 parents, GET /admin/parents?search=partial_name returns only matches (2xx, correct count).
  - `rule` TR-5.2: search by partial phone ILIKE → correct matches.
  - `rule` TR-5.3: status filter restricts results.
  - `rule` TR-5.4: history endpoint by request id returns list of >= 2 requests if same phone seeded; sorted desc by created_at.

## Task 6: Expanded Admin Dashboard Metrics
- **Status**: `pending`
- **Priority**: medium
- **Depends On**: Task 1
- **Description**:
  - Expand existing dashboard endpoint response to add computed numeric fields:
    - `conversion_rate_pct`: assigned / total_open_past_30_days * 100
    - `avg_days_to_assign`: avg(assigned_at - created_at) days for requests where status assigned or closed, last 90d
    - `tutor_verification_funnel_pct`: verified/(pending+verified+rejected+probation) tutors * 100
  - Keep all existing dashboard fields (backwards compat).
  - Compute in SQL level queries (not Python loops) for efficiency.
- **Acceptance Criteria Addressed**: AC-7
- **Test Requirements**:
  - `rule` TR-6.1: Seeded N requests/tutors with known dates → arithmetic checks match expected computed numbers within tolerance ±0.01.
  - `rule` TR-6.2: Division by zero scenarios (zero requests) returns 0, no 500s.

## Task 7: Assignment Pipeline View + Assignment CSV Export
- **Status**: `pending`
- **Priority**: medium
- **Depends On**: Task 1
- **Description**:
  - Add GET `/admin/assignments/pipeline` endpoint: returns {by_status: [{status, count, median_age_days, oldest_10: [...]}], ...}. Use SQL aggregate for median approximation (PostgreSQL percentile_continuous if available; else fallback to sort in Python for small sets).
  - Existing assignments export / CSV endpoint: add assigned_date, closed_date columns. Add a new assignment-level CSV (separate from tutors and requests): columns: assignment_id, parent_request_id, parent_name, parent_phone, tutor_id, tutor_name, tutor_phone, subjects (comma), status (assigned/closed/cancelled), assigned_date (ISO), closed_date (ISO), days_to_close.
- **Acceptance Criteria Addressed**: AC-8, AC-9
- **Test Requirements**:
  - `rule` TR-7.1: Seeded 5-status pipeline → all status counts match; oldest-10 lists contain the right number of items.
  - `rule` TR-7.2: Assignment CSV parsed rows include all 11 column headers + assigned_date/closed_date ISO timestamps where seeded present.

## Task 8: Tutor & Parent Dashboard Endpoints (Assignments, Feedback Model)
- **Status**: `pending`
- **Priority**: high
- **Depends On**: Task 1
- **Description**:
  - Add SQLAlchemy model `AssignmentFeedback` (if not already present; check test_phase5/feedback.py references → may exist). Fields: id, assignment_id (FK), rater_role (parent/tutor enum), rating (1-5 int), comment (text, optional), created_at. Add unique constraint per-role per-assignment (one per parent per assignment; one per tutor per assignment). Alembic auto-migration.
  - Add GET `/tutors/me/assignments`: Authenticated via Telegram init data (same as /api/v1/tutors/register auth). Returns list of assignments for this tutor's telegram_user_id; each row: request_id, parent_name (parent + student_level), subjects, location, status, sessions_completed count, avg_parent_rating, estimated_earnings_etb (sum of completed_sessions × hourly rate × session_duration_hours as numeric estimate).
  - Add GET `/parents/me/requests`: Authenticated via Telegram init data. Returns list of requests by this parent telegram_user_id; each row: request_id, status, subjects, assigned_tutor (name+phone if assigned), completed_sessions_count, average_tutor_rating.
  - Add POST `/parents/me/feedback`: authenticated parent → body {assignment_id, rating (1-5), comment?} → writes AssignmentFeedback; updates tutor running avg via aggregate query recompute.
  - Add POST `/tutors/me/feedback`: same for tutor rating parent.
  - Schemas: typed request + response models with validation rating 1-5 int.
- **Acceptance Criteria Addressed**: AC-10, AC-11
- **Test Requirements**:
  - `rule` TR-8.1: GET /tutors/me/assignments without telegram init auth → 401; with valid → list rows matching seeded.
  - `rule` TR-8.2: POST feedback with 5-star → 201; GET feedback reflected in avg on tutor/parent subsequent fetch (within delta).
  - `rule` TR-8.3: Duplicate feedback same role same assignment → 409 "Already submitted".

## Task 9: Review in App Button Completeness (All 5 card types)
- **Status**: `pending`
- **Priority**: high
- **Depends On**: Task 4 (DM assignment cards use Review URL)
- **Description**:
  - Ensure startup `check_review_link_config` always called (already patched; confirm no regressions).
  - Assignment cards from Task 4 must attach the Review URL button using `get_admin_review_url(f"request_{parent_req.id}")` → consistent with existing parent request cards.
  - Add keyboard to assignment DM messages using same `[[InlineKeyboardButton("Review in App", url=review_url)]]` pattern when url resolves.
  - Add 5 test cases covering: parent topic card, parent index card, tutor registration card, tutor assignment DM, parent assignment DM — all 5 include url button if MINI_APP_URL valid t.me link.
  - Add test that if short_name missing → warning logged once; button omitted (no crash).
- **Acceptance Criteria Addressed**: AC-4, AC-12, AC-13
- **Test Requirements**:
  - `rule` TR-9.1: Valid MINI_APP_URL env set; all 5 card-build functions called → each keyboard contains 1+ url button starting with `https://t.me/` and containing `startapp=`.
  - `rule` TR-9.2: Missing MINI_APP_URL + no ADMIN_MINI_APP_SHORT_NAME → first card builder call emits 1 logger.warning containing "Review in App"; subsequent calls silent (no duplicate warning).
  - `rule` TR-9.3: `check_review_link_config` called once during startup → caplog contains sample URL; tested via direct function call with logs captured.

## Task 10: Customer Frontend Brand Overhaul
- **Status**: `pending`
- **Priority**: high
- **Depends On**: Task 3 (brand tokens ready)
- **Description**:
  - Header.jsx: replace default gradient with MentorLink brand (pine→ink gradient, brand mark square with dot, mentorlink wordmark with amharic subtitle; mirror admin.css brand styles exactly). Make the brand-mark 29x29 container + 10x10 gold citrus inner dot CSS classes added to index.css or inline styles.
  - TabNavigation.jsx: pill styling with brand tokens — active tab bg=paper text=pine shadow; inactive bg=transparent, text=muted; underline border-line; all Tailwind utility brand tokens not Telegram blues.
  - ParentForm.jsx: Every input group border-line; labels text=ink (font-semibold); helper text text=muted; chip multi-select active=pine text=paper; inactive=paper text=ink border-line. Submit button bg=pine text=paper hover:opacity-90 (no Telegram blue). Amharic text via translation dict consistent.
  - TutorForm.jsx: Same input/chip/button styling as ParentForm. File upload area bg=paper, dashed border-line, text-muted drop-hint.
  - SuccessModal.jsx: Icon ring bg=green (not green-100 stock). Primary button pine. Close secondary outline button text=pine border-pine. Badges use brand colors.
  - All numeric money amounts (ETB/hr, monthly estimate): use text-pine font-semibold styling.
- **Acceptance Criteria Addressed**: AC-15
- **Test Requirements**:
  - `rubric` TR-10.1: Brand fidelity 1-5; 1=Tailwind default blue-green; 3=header+buttons brand-colored; 5=every component: no `bg-green-*`, no `text-blue-*`, no `bg-blue-*` Tailwind stock color classes anywhere in src/components/ JSX files (grep). All color classes use MentorLink tokens. Threshold >= 4.
  - `rule` TR-10.2: Grep src/components/**.jsx for "green-100", "blue-600", "bg-blue", "text-blue" → 0 matches.
  - `rule` TR-10.3: Build passes with 0 warnings (Task 14 verifies also).

## Task 11: Admin CSS Stray Colors Cleanup
- **Status**: `pending`
- **Priority**: medium
- **Depends On**: Task 3 (tokens available)
- **Description**:
  - admin.css stray hardcoded semantic hexes: `#dc2626` danger → replace with `var(--coral)`; `#2563eb` status blue → replace with `var(--pine)` or remove status-open color styling use badge-pill utility class using pine; `#059669/#16a34a/#166534` emerald family → `var(--green)`; `#3730a3 indigo → --pine; `#e0e7ff indigo light → --line + paper.
  - Exceptions: decorative-only brand accents allowed: brand-inner-dot #e5aa5f (matches citrus a88221 close enough — keep OR swap to var(--citrus); keep topbar border #d79a51 as citrus if close; analytics gap fill OK if decorative).
  - Add comments-free CSS (no comments) per code style.
  - Grep remaining hex after edit; only decorative brand accents should remain (≤ 3 total non-token hex).
- **Acceptance Criteria Addressed**: AC-16
- **Test Requirements**:
  - `rubric` TR-11.1: Admin stray colors scale 1-5; 1=10+ semantic hex; 3=5-9; 5=0 semantic hex (only brand mark accents remain). Threshold >= 4.
  - `rule` TR-11.2: grep -Eo '#[0-9a-fA-F]{6}' admin.css | sort -u → count unique semantic meaning hexes (not ink/pine/muted/line/paper/coral/green/citrus/brand-mark decoration) ≤ 3 total.

## Task 12: Admin Business Feature UIs (CRM / Dashboard Widgets / Pipeline / Export)
- **Status**: `pending`
- **Priority**: medium
- **Depends On**: Task 5, 6, 7 (endpoints ready), Task 11
- **Description**:
  - Admin CRM view: New "Customers" tab (or enhancement of Requests view) → top search box `type=search` debounced 350ms, matches parents; click a row → open right-side drawer/detail view showing parent request history cards (Task 5 history endpoint).
  - Admin Dashboard: Add 3 small info-pill metric cards for conversion_rate_pct, avg_days_to_assign, verification_funnel_pct rendered at top of AnalyticsBoard or Dashboard tab.
  - Assignment Pipeline: New "Pipeline" section (or tab in existing views) → per-status columnized cards with counts, median age, oldest rows list; search filter.
  - ExportCenter: Add a 3rd CSV export button — "Assignments (CSV)" — calls the new endpoint.
  - All new UI components use existing admin.css classes (no new frameworks); extend admin.css minimally with new classes (.customer-drawer, .metric-card, .pipeline-col, etc.) using the 8 brand tokens only.
- **Acceptance Criteria Addressed**: AC-6 (frontend half), AC-7 (frontend half), AC-8 (frontend half), AC-9 (frontend half)
- **Test Requirements**:
  - `rule` TR-12.1: Admin build succeeds (Task 14).
  - `rubric` TR-12.2: Admin UX cohesiveness 1-5; 1=hodgepodge; 3=functional but inconsistent; 5=all 4 modules (CRM/dash/pipeline/export) look like one system, same spacing, same token colours only, no stray Tailwind. Threshold >= 4.

## Task 13: Tutor & Parent Dashboard UIs (Customer Side)
- **Status**: `pending`
- **Priority**: medium
- **Depends On**: Task 8 (endpoints ready), Task 10 (brand refactor)
- **Description**:
  - Customer App.jsx: After successful submission → show new post-submission state views. Add logic: if user telegram_user_id already has existing assignments/requests, new 3rd tabs: "My Requests" (for parents) / "My Students" (for tutors). State machine:
    - For parent: if activeTab='parent': default to request form, OR if they have active requests, default to a mini dashboard: 2 tabs ("New Request", "My Requests").
    - For tutor: 2 tabs ("Edit Profile"/basic form, "My Students").
  - "My Requests" view: cards list: each request row from Task 8 parent endpoint → assigned tutor mini card with contact; Submit Feedback inline (1-5 stars + textarea + submit button).
  - "My Students" for tutors → cards per assignment: household/student context, subjects, location, next session info, running fee-tracker total (estimated ETB); show parent rating stars.
  - Use the brand palette Task 10 established. Stars use citrus color. Action buttons use pine (primary) / outline (secondary).
  - "Contact Admin" button → calls new endpoint (POST /parents/me/contact_admin) → bot send_message to ADMIN_GROUP_ID with telegram user info + message (optional).
- **Acceptance Criteria Addressed**: AC-10 (UI half), AC-11 (UI half)
- **Test Requirements**:
  - `rule` TR-13.1: Customer build passes (Task 14 verifies).
  - `rule` TR-13.2: Feedback UI POST body → matches backend schema; mock submit validates 1-5; 0 invalid.
  - `rubric` TR-13.3: Customer dashboard UX 1-5; 1=broken; 3=works but rough; 5=clean layout, accessible inputs, brand colors only. Threshold >= 4.

## Task 14: Final Build Verification + Test Suite Expansion to ≥125 Tests
- **Status**: `pending`
- **Priority**: high
- **Depends On**: All Tasks 1-13
- **Description**:
  - Run backend pytest suite: add new tests for every new endpoint/model/helper introduced in previous tasks. Aim to reach total ≥ 125 tests.
  - Run backend pytest: fix any existing test breakage from role changes.
  - Run frontend `npm run build`: ensure 0 errors, 0 warnings.
  - Manually run `GetDiagnostics` for IDE lint/type issues.
  - Produce final pass evidence for AC-18, AC-19.
- **Acceptance Criteria Addressed**: AC-18, AC-19
- **Test Requirements**:
  - `rule` TR-14.1: `python -m pytest -q` exit 0; output line ends with "passed"; numeric count >= 125.
  - `rule` TR-14.2: `npm run build` exit 0; console contains no "error" case-insensitive; no "warning" case-insensitive lines.
  - `rule` TR-14.3: IDE diagnostics 0 errors/warnings for both Python and JS.
