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
