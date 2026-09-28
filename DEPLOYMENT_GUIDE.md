# MentorLink — Production Deployment & Configuration Guide

This single document provides the complete, end-to-end production deployment procedure for **MentorLink (Backend API, Telegram Bot, Intake Mini App, and Admin Mini App)**. It details every step: Telegram Bot creation via BotFather, Forum Topics configuration, PostgreSQL provisioning, environment variables with production examples, Vercel & Render hosting, and GitHub Actions automated cron execution.

---

## Table of Contents
1. [Architecture & Services Overview](#1-architecture--services-overview)
2. [Telegram Bot & Admin Group Setup](#2-telegram-bot--admin-group-setup)
   - [2.1 Create Telegram Bot via @BotFather](#21-create-telegram-bot-via-botfather)
   - [2.2 Configure Mini App Menu Buttons & Direct Links](#22-configure-mini-app-menu-buttons--direct-links)
   - [2.3 Create & Configure the Admin Telegram Supergroup](#23-create--configure-the-admin-telegram-supergroup)
   - [2.4 Obtain IDs (Group ID, Super Admin ID, Topic IDs)](#24-obtain-ids-group-id-super-admin-id-topic-ids)
3. [Database Provisioning (Neon / Supabase / Render PostgreSQL)](#3-database-provisioning)
4. [Backend API & Bot Deployment (Render / Linux VM)](#4-backend-api--bot-deployment)
   - [4.1 Backend Environment Variables Reference](#41-backend-environment-variables-reference)
   - [4.2 Build & Run Commands](#42-build--run-commands)
   - [4.3 Polling vs. Webhook Mode](#43-polling-vs-webhook-mode)
5. [Frontend Mini App Deployment (Vercel)](#5-frontend-mini-app-deployment)
   - [5.1 Dual-Entry Architecture](#51-dual-entry-architecture)
   - [5.2 Frontend Environment Variables Reference](#52-frontend-environment-variables-reference)
   - [5.3 Vercel Deployment Settings](#53-vercel-deployment-settings)
6. [Automated Scheduled Cron Setup (GitHub Actions)](#6-automated-scheduled-cron-setup)
7. [Post-Deployment Smoke Test Checklist](#7-post-deployment-smoke-test-checklist)
8. [Troubleshooting & FAQ](#8-troubleshooting--faq)

---

## 1. Architecture & Services Overview

MentorLink consists of four interconnected layers:

```mermaid
flowchart TD
    User["Parent / Tutor (Telegram Client)"] -->|TMA initData / HTTP| Vercel["Vercel Frontend (Vite)"]
    Admin["Admin / Verifier (Telegram Client)"] -->|TMA initData / HTTP| Vercel
    Vercel -->|REST API Requests| Render["Render / VM Backend (FastAPI)"]
    Render -->|SQL Queries (asyncpg)| Postgres[("PostgreSQL Database")]
    Render -->|Bot API Messages / Topics / DMs| TgAPI["Telegram Bot API"]
    TgAPI -->|Webhook / Polling| Render
    GHA["GitHub Actions Cron (Every 20m)"] -->|POST /api/v1/admin/cron/run| Render
```

- **Frontend (`frontend/`)**: Vite React application building two entry points:
  1. `index.html`: Public intake Mini App for parents submitting requests and tutors applying.
  2. `admin.html`: Operations & management console with verification checklists, matching workbench, ops flags, analytics, audit log, and CSV exports.
- **Backend (`backend/`)**: FastAPI application using Python 3.12, SQLAlchemy (asyncio), Alembic, and `python-telegram-bot`.
- **Database**: PostgreSQL (Neon, Render Postgres, or Supabase).
- **Automation / Scheduler**: An external cron hit (`POST /api/v1/admin/cron/run`) executes background tasks (feedback collection, red flags, probation/re-verification checks) using transactional database locks to guarantee idempotency.

---

## 2. Telegram Bot & Admin Group Setup

### 2.1 Create Telegram Bot via @BotFather

1. Open Telegram and search for [@BotFather](https://t.me/BotFather).
2. Send `/newbot`.
3. Enter your bot's display name: `MentorLink Admin Bot`.
4. Enter your bot's username (must end in `bot`): e.g., `MentorLinkProdBot`.
5. **Save the HTTP API Token** returned by BotFather. This is your `BOT_TOKEN`.
   > **Example Token:** `7123456789:AAFlxyz-ExampleToken12345abcdef`
6. **Disable Group Privacy Mode** so the bot can process group commands and receive updates:
   - Send `/setprivacy` to @BotFather.
   - Choose your bot (`@MentorLinkProdBot`).
   - Select **Disable**.
7. Enable inline mode (optional, recommended):
   - Send `/setinline` to @BotFather -> Select your bot -> Enter a placeholder like `Search mentors...`.

---

### 2.2 Configure Mini App Menu Buttons & Direct Links

#### A. Set Main Intake Web App Menu Button (For Parents & Tutors)
1. In @BotFather, send `/setmenubutton`.
2. Select your bot.
3. Choose **Configure menu button**.
4. Enter URL: `https://<your-frontend-domain>.vercel.app/`
5. Enter Button Title: `Open MentorLink`

#### B. Create Direct Mini App for Admin Console (For Admins)
1. In @BotFather, send `/newapp`.
2. Select your bot (`@MentorLinkProdBot`).
3. Title: `MentorLink Admin`
4. Description: `Admin Operations Mini App`
5. Upload a 640x360 photo (or choose skip).
6. Upload GIF or skip.
7. Enter Web App URL: `https://<your-frontend-domain>.vercel.app/admin.html`
8. Choose a short name: e.g., `admin`
   - Your direct link becomes: `https://t.me/MentorLinkProdBot/admin`
   - Telegram automatically supports deep-links: `https://t.me/MentorLinkProdBot/admin?startapp=tutor_12`

---

### 2.3 Create & Configure the Admin Telegram Supergroup

1. In Telegram, create a new **Group** (e.g. `MentorLink Operations Team`).
2. Convert it to a **Supergroup with Topics**:
   - Open **Group Settings** / **Manage Group**.
   - Enable **Topics** (toggle on "Forum Topics").
3. Add your bot (`@MentorLinkProdBot`) to the group.
4. Promote your bot to **Administrator** with the following permissions:
   - [x] Change Group Info
   - [x] Delete Messages
   - [x] Pin Messages
   - [x] Manage Topics (essential for auto-creating and posting in topic threads)

---

### 2.4 Obtain IDs (Group ID, Super Admin ID, Topic IDs)

#### A. Finding your `ADMIN_GROUP_ID`
1. Temporarily add `@userinfobot` or `@raw_data_bot` to your group, or forward a message from the group to `@userinfobot`.
2. Look for the `chat.id`. For Supergroups, it always starts with `-100`.
   > **Example Value:** `-1002345678901`

#### B. Finding your `SUPER_ADMIN_ID`
1. Open a direct chat with [@userinfobot](https://t.me/userinfobot) in Telegram.
2. Send `/start`.
3. Copy your numeric `Id`.
   > **Example Value:** `582914831`

#### C. Forum Topic IDs (`PARENT_REQUESTS_TOPIC_ID`, `TUTOR_REGISTRATION_TOPIC_ID`)
- **Automatic Provisioning (Recommended):** If left blank in `.env`, the backend bot will automatically detect or create two dedicated forum topics upon startup:
  1. `Parent` (for new parent request cards)
  2. `Tutor Profiles` (for tutor registration cards and verification alerts)
- **Manual Provisioning (Optional):** If you create topics manually, click on each topic thread, copy the message link, and note the thread ID from the URL (e.g., `https://t.me/c/2345678901/142` -> Topic ID is `142`).

---

## 3. Database Provisioning

Provision an isolated PostgreSQL database (e.g. Neon.tech, Render Postgres, or Supabase).

1. **Create Database:** Create a Postgres database named `mentorlink_prod`.
2. **Connection URL:** Obtain the standard connection string:
   ```
   postgresql://mentorlink_user:SecretPassword123@ep-cool-fog-12345.us-east-2.aws.neon.tech/mentorlink_prod?sslmode=require
   ```
3. **Asyncpg URL Format:** The backend uses async SQLAlchemy. Prepend `+asyncpg` and strip incompatible query arguments if needed:
   ```
   postgresql+asyncpg://mentorlink_user:SecretPassword123@ep-cool-fog-12345.us-east-2.aws.neon.tech/mentorlink_prod
   ```
4. **Run Migrations:** Apply all 5 database migration phases:
   ```bash
   cd backend
   alembic upgrade head
   ```
   > This generates all tables: `tutors`, `parent_requests`, `assignments`, `match_invites`, `session_feedback`, `tutor_incidents`, `tutor_verifications`, `audit_log`, `admin_users`, `system_settings`, `scheduled_event_claims`, `notification_outbox`, and `registration_funnel_events`.

---

## 4. Backend API & Bot Deployment

Deploy the `backend/` directory as a Web Service (e.g., on Render, Railway, or a Linux VPS).

### 4.1 Backend Environment Variables Reference

Configure these environment variables in your deployment dashboard:

| Variable Name | Required | Default / Mode | Purpose & Description | Realistic Production Example |
|---|---|---|---|---|
| `DATABASE_URL` | **Yes** | — | Async PostgreSQL connection string with `postgresql+asyncpg://` scheme. | `postgresql+asyncpg://ml_user:P@ss123@ep-xy.neon.tech/ml_db` |
| `BOT_TOKEN` | **Yes** | — | Telegram Bot API token generated by @BotFather. | `7123456789:AAFlxyz-ExampleToken12345abcdef` |
| `BOT_MODE` | **Yes** | `webhook` | `webhook` for production hosting; `polling` for local single-process dev. | `webhook` |
| `WEBHOOK_URL` | **Yes** (in webhook mode) | — | Public HTTPS endpoint where Telegram delivers updates. Must point to `/telegram/webhook/<WEBHOOK_SECRET>`. | `https://mentorlink-api.onrender.com/telegram/webhook/a9b8c7d6e5f412345678` |
| `WEBHOOK_SECRET` | **Yes** (in webhook mode) | — | Random high-entropy secret string to protect the webhook endpoint from spoofing. | `a9b8c7d6e5f412345678` |
| `ADMIN_GROUP_ID` | **Yes** | — | Numeric ID of the Telegram admin supergroup (starts with `-100`). | `-1002345678901` |
| `SUPER_ADMIN_ID` | **Yes** | — | Numeric Telegram User ID of the primary owner who has permanent super admin privileges. | `582914831` |
| `ADMIN_IDS` | No | `[]` | Comma-separated list of secondary initial admin Telegram IDs. | `112233445,998877665` |
| `PARENT_REQUESTS_TOPIC_ID` | No | Auto | Forum topic thread ID for parent requests. Leave empty for automatic creation. | `2` |
| `TUTOR_REGISTRATION_TOPIC_ID` | No | Auto | Forum topic thread ID for tutor profiles. Leave empty for automatic creation. | `4` |
| `WEBAPP_URL` | **Yes** | — | Public HTTPS URL of the hosted frontend (Vercel). Used for validating Telegram `initData`. | `https://mentorlink-app.vercel.app` |
| `MINI_APP_URL` | **Yes** | — | Direct Telegram link to the **Admin** Mini App you registered in step 2.2-B (same short name). "Review in App" buttons are built from it. Do **not** use the intake app's link or the Vercel URL. | `https://t.me/MentorLinkProdBot/admin` |
| `ADMIN_REVIEW_LINK_MODE` | No | `both` | `direct`, `bot` or `both`. `both` adds an **Open via bot** button next to **Review in App**; it goes through the bot chat and always opens the app, even if Telegram resolves the direct link to the bot. | `both` |
| `ENVIRONMENT` | **Yes** | `development` | Environment mode. **The code default is `development`, so set it to `production` explicitly.** In `development` the app creates tables itself at startup (`create_all`), which conflicts with Alembic migrations, and allows localhost origins. | `production` |
| `ALLOW_UNVERIFIED_WEB_PREVIEW` | **Yes** | `false` | Must be `false` in production. Setting to `true` is blocked by validation when `ENVIRONMENT=production`. | `false` |
| `CRON_SECRET` | **Yes** | — | Secret token required to authenticate external triggers to `POST /api/v1/admin/cron/run`. | `cron_ml_prod_9876543210_secret` |

---

### 4.2 Build & Run Commands

- **Build Command:**
  ```bash
  pip install --no-cache-dir -r requirements.txt && alembic upgrade head
  ```
- **Start Command (Production Webhook Mode):**
  ```bash
  uvicorn app.main:app --host 0.0.0.0 --port $PORT --workers 2
  ```

---

### 4.3 Polling vs. Webhook Mode

- **Production (Webhook):**
  Set `BOT_MODE=webhook`. When the backend boots, it automatically registers `WEBHOOK_URL` with Telegram using `bot.set_webhook()`. Multi-worker concurrency and fast cold-starts are safely supported.
- **Local Dev (Polling):**
  Set `BOT_MODE=polling`. The bot runs internal polling tasks directly inside the FastAPI lifespan process.

---

## 5. Frontend Mini App Deployment

Deploy the `frontend/` directory to **Vercel** (or Cloudflare Pages / Render Static Site).

### 5.1 Dual-Entry Architecture

The Vite configuration (`vite.config.js`) builds two distinct HTML apps into `dist/`:
1. `dist/index.html`: Intake interface for parents and tutors.
2. `dist/admin.html`: Operations & management console for administrators.

To prevent 404 errors on browser refresh and clean routing, ensure `frontend/vercel.json` is present:
```json
{
  "rewrites": [
    { "source": "/admin", "destination": "/admin.html" },
    { "source": "/admin/:match*", "destination": "/admin.html" },
    { "source": "/((?!assets/|admin\\.html|index\\.html).*)$", "destination": "/index.html" }
  ]
}
```

---

### 5.2 Frontend Environment Variables Reference

Configure this variable in your Vercel Project Settings (**Settings -> Environment Variables**):

| Variable Name | Required | Purpose & Description | Realistic Production Example |
|---|---|---|---|
| `VITE_API_BASE_URL` | **Yes** | Base HTTPS URL of your deployed backend API without trailing slash. | `https://mentorlink-api.onrender.com` |

---

### 5.3 Vercel Deployment Settings

1. Import the repository into Vercel.
2. Configure Project:
   - **Framework Preset:** `Vite`
   - **Root Directory:** `frontend`
   - **Build Command:** `npm run build`
   - **Output Directory:** `dist`
   - **Install Command:** `npm install`
3. Add Environment Variable:
   - Key: `VITE_API_BASE_URL`
   - Value: `https://mentorlink-api.onrender.com` (your backend URL)
4. Click **Deploy**.
5. Once deployed, copy your assigned domain (e.g., `https://mentorlink-app.vercel.app`) and update the backend's `WEBAPP_URL`.

---

## 6. Automated Scheduled Cron Setup

The backend features a durable, idempotent scheduler (`app/services/scheduler.py`) that executes:
- Parent feedback requests 3 days after tutoring assignment.
- Red-flag anomaly scans across tutors (missing documents, fee outliers, low scores).
- Tutor re-verification cadence alerts (every 90 days).
- Probation check-in alerts (every 7 days for tutors on probation).
- Notification outbox draining to the Telegram group and parent DMs.

The scheduler endpoint `POST /api/v1/admin/cron/run` is driven automatically by the repository's GitHub Actions workflow: [`.github/workflows/scheduled-cron.yml`](file:///.github/workflows/scheduled-cron.yml).

### Configuring GitHub Actions Secrets

1. In your GitHub repository, navigate to **Settings -> Secrets and variables -> Actions**.
2. Click **New repository secret** and create the following two secrets:

| Secret Name | Value Description | Realistic Example Value |
|---|---|---|
| `BACKEND_CRON_URL` | Full URL to the backend's admin cron runner endpoint. | `https://mentorlink-api.onrender.com/api/v1/admin/cron/run` |
| `CRON_SECRET` | Must match the `CRON_SECRET` configured in the backend environment. | `cron_ml_prod_9876543210_secret` |

3. The workflow runs every 20 minutes (`*/20 * * * *`). You can also manually trigger it at any time via the **Actions -> Scheduled Admin Cron -> Run workflow** button.

---

## 7. Post-Deployment Smoke Test Checklist

Execute these 7 steps to confirm production readiness:

- [ ] **1. Health Check:**
  ```bash
  curl -i https://mentorlink-api.onrender.com/api/v1/health
  # Expected: HTTP 200 {"status":"ok","db":"ok"}
  ```

- [ ] **2. Cron Endpoint Authentication:**
  ```bash
  # Test Unauthorized:
  curl -i -X POST https://mentorlink-api.onrender.com/api/v1/admin/cron/run
  # Expected: HTTP 401 Unauthorized

  # Test Authorized:
  curl -i -X POST https://mentorlink-api.onrender.com/api/v1/admin/cron/run \
       -H "X-Cron-Secret: cron_ml_prod_9876543210_secret"
  # Expected: HTTP 200 {"ok":true,"message":"Scheduled checks and outbox drained successfully."...}
  ```

- [ ] **3. Public Parent Intake Test:**
  - In Telegram, open `@MentorLinkProdBot` and click the **Open MentorLink** menu button.
  - Submit a test parent request (e.g., Grade 10 Mathematics in Bole).
  - Confirm the request card appears in the Telegram Admin Group under the **Parent** topic with a **Review in App** button.

- [ ] **4. Public Tutor Application Test:**
  - Submit a new tutor registration with CV/ID document.
  - Confirm the tutor profile card appears in the Telegram Admin Group under the **Tutor Profiles** topic with a **Review in App** button.

- [ ] **5. Admin Mini App Verification:**
  - Open `https://t.me/MentorLinkProdBot/admin` as the `SUPER_ADMIN_ID` user.
  - Verify that dashboard metrics load with real counts.
  - Open the **Tutor Verification** tab: inspect uploaded credentials, check the 4 verification boxes, and approve.
  - Confirm status updates to `Verified`.

- [ ] **6. Matching & Assignment:**
  - Open the pending parent request in the **Matching Workbench**.
  - Review candidate rankings, fit scores, and ping candidate tutors.
  - Assign the verified tutor and confirm that an active `Assignment` record is created.

- [ ] **7. Parity CSV Export Test:**
  - In the Admin Mini App, go to the **Export Center**.
  - Download both `tutors_export.csv` and `parents_export.csv`.
  - Confirm valid UTF-8-SIG formatting and byte-for-byte data integrity.

---

## 8. Troubleshooting & FAQ

#### Q1: Mini App gives "Telegram Mini App authentication is required" (HTTP 401)?
- **Cause:** Opening the web app directly in a standard browser instead of inside the Telegram client container.
- **Solution:** Telegram Web Apps must be launched inside Telegram (via bot menu button or inline link) so that Telegram provides signed `initData`. For automated API testing, pass `Authorization: tma <valid_init_data>` headers.

#### Q2: Webhook returns HTTP 403 Forbidden from Telegram?
- **Cause:** `WEBHOOK_URL` in the environment does not match the actual deployed domain, or `WEBHOOK_SECRET` in the URL path doesn't match the header secret.
- **Solution:** Verify that `WEBHOOK_URL` starts with `https://` and includes the secret: `https://<domain>/telegram/webhook/<WEBHOOK_SECRET>`.

#### Q3: Bot does not post cards into topics?
- **Cause:** The bot lacks the **Manage Topics** permission in the supergroup, or the group does not have Forum Topics enabled.
- **Solution:** Edit the supergroup, enable Topics, promote the bot to Administrator, and toggle on **Manage Topics**.

#### Q4: Alembic migration fails during deployment?
- **Cause:** Database URL is using `postgresql://` instead of `postgresql+asyncpg://` or database user lacks table creation privileges.
- **Solution:** Ensure `DATABASE_URL` uses the async driver: `postgresql+asyncpg://<user>:<pass>@<host>/<db>`. Run `alembic upgrade head`.

