# Freshman Resources Bot (Aiogram 3 + PostgreSQL)

Academic materials locked behind a one-time manual payment (CBE / Telebirr receipt), delivered with
`protect_content=True` from a private Telegram channel (zero storage cost).

## 1. Setup
1. Create the bot with @BotFather → `BOT_TOKEN`.
2. Create a **private channel** for materials, add the bot as **admin** → `STORAGE_CHANNEL_ID` (`-100…`).
3. Create an **admin group** for receipts, add the bot → `ADMIN_CHAT_ID`.
4. Put the Telegram IDs of everyone allowed to approve/upload in `ADMIN_IDS` (comma-separated).
5. Create a Supabase (or any Postgres) database → `DATABASE_URL`.
   For the Supabase pooler use the *transaction* connection string and append `?prepared_statement_cache_size=0`.
6. `cp .env.example .env` and fill it in.

## 2. Run
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m bot.main
```
Tables are created automatically on startup.

Docker: `docker build -t freshman-bot . && docker run --env-file .env freshman-bot`
(works on Railway, Render, Fly.io, any VPS — run it as a *worker*, no port needed).

## 3. Uploading materials (admins)
DM the bot `/admin` for help. Send any file with a caption:
```
/add MATH101 | modules | Chapter 1 - Limits
/add PHYS101 | exams | 2024 Midterm | 2024
/add CHEM101 | slides | Intro to Atoms | sample
```
The bot copies it into the storage channel and saves the `message_id`.
Edit courses/categories in `bot/utils/constants.py`.

## 4. Payment flow
Unlock Full Access → payment details → student sends screenshot (FSM) → receipt posted to the admin
group with ✅ / ❌ buttons → student notified by DM, admin message updated.

## Notes
- `protect_content` stops forwarding/saving inside Telegram; it cannot stop screenshots or screen recording.
- FSM uses in-memory storage: a restart during "waiting for receipt" just requires tapping Unlock again.
  Swap in `RedisStorage` in `bot/main.py` if you want it persistent.
