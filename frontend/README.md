# MentorLink — Telegram Mini App (TMA) Frontend

Modern React + Vite + Tailwind CSS frontend for the **Ethiopian In-Home Tutor & Mentor Matching Platform**. Built to run seamlessly inside Telegram as a Telegram Mini App (TMA) or in a standard mobile browser.

---

## 🚀 Quick Start (Local Development)

### 1. Install Dependencies
```bash
cd frontend
npm install
```

### 2. Configure Environment
Create `.env` (or copy from `.env.example`):
```env
VITE_API_BASE_URL=http://localhost:8000
```

### 3. Run Local Dev Server
```bash
npm run dev
```
Open **`http://localhost:3000`** in your browser.

## Admin Mini App

The admin console is a separate Vite entry at **`/admin.html`** (locally, `http://localhost:3000/admin.html`). Deploy the frontend as usual; the production build includes both the public intake page and the admin page. Configure the standalone admin bot's Telegram Mini App URL to the hosted `/admin.html` URL.

The console requires signed Telegram Mini App `initData` and an active `AdminUser` record (or the configured bootstrap `SUPER_ADMIN_ID`). Opening it in a regular browser without Telegram authentication intentionally shows the access-required screen. Supported Telegram `startapp` parameters are `tutor_{id}` and `request_{id}`; Phase 1 acknowledges the target while detail screens are added in Phase 2.

---

## 🌐 Deploy to Vercel

1. Push your repository to GitHub.
2. In Vercel, import the repository and set:
   - **Root Directory:** `frontend`
   - **Framework Preset:** `Vite`
   - **Environment Variable:**
     - `VITE_API_BASE_URL`: `https://<your-backend>.onrender.com`
3. Click **Deploy**.

---

## 🤖 Connect to Telegram Bot (@BotFather)

1. Open [@BotFather](https://t.me/botfather) in Telegram.
2. Use the `/newapp` command or `/myapps` -> select your bot.
3. Provide:
   - **Title:** `MentorLink`
   - **Description:** `Ethiopian In-Home Tutor Matching Platform`
   - **Web App URL:** Your Vercel URL (e.g. `https://mentorlink.vercel.app`).
   - **Short Name:** e.g. `app`
4. You can now launch the Mini App inside Telegram via `t.me/<your_bot_username>/app` or via a direct WebApp menu button!
