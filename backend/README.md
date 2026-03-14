# Aria — **San Francisco homes only** (ScrapeGraph DB + web + Telegram)

All listing searches are scoped to **San Francisco**. Natural-language search still works; inventory is SF-only. Optional env: `MARKET_CITY=San Francisco` (default).

## Flow

1. **Wipe old demo data once** (optional):  
   `.\.venv\Scripts\python.exe db\seed.py --wipe`
2. **Fill DB from ScrapeGraph** (your API key in `.env`):  
   `.\.venv\Scripts\python.exe scraper.py`  
   or JSON only: `scraper.py --json data\combined_deduplicated.json`
3. **Web chat UI**: start API → open **http://127.0.0.1:8000/**
4. **Telegram** (optional): set `TELEGRAM_BOT_TOKEN` → `python telegram_bot.py`

Always use **`.venv\Scripts\python.exe`** on Windows (not global Python 3.14).

### Email (Resend)

1. Create API key at [resend.com](https://resend.com).
2. In `backend/.env`: `RESEND_API_KEY=re_...`
3. Testing: `RESEND_FROM=Aria <onboarding@resend.dev>` (sends to any recipient on free tier per Resend docs).
4. Production: add & verify a domain in Resend, then set `RESEND_FROM=Aria <you@yourdomain.com>`.
5. `GET /health/smtp` → `email_ready: true` when Resend or SMTP is configured.

### SF-only DB (drop Austin / old demo rows)

```bat
.venv\Scripts\python.exe db\seed.py --sf-only
.venv\Scripts\python.exe scraper.py --json data\combined_deduplicated.json
```

Then start the API. Ingest always stores **city = San Francisco**.

## Commands

| Command | Purpose |
|--------|--------|
| `run_server.bat` | Uvicorn + chat UI at `/` |
| `python scraper.py` | Extract + dedupe + SQLite |
| `python db\seed.py --wipe` | Delete all listings |
| `python telegram_bot.py` | Telegram polling |
| `python chat_cli.py` | Terminal chat |

## Env

- `OPENAI_API_KEY` — required for chat  
- `SCRAPER_AI_AUTH` — ScrapeGraph / extract API  
- `TELEGRAM_BOT_TOKEN` — optional  

## Frontend

Static files in `static/` — served at `/` and `/assets/*`.

## Demo (React UI)

From repo root see **`DEMO_SCRIPT.md`** — unique chat lines per feature (trail, chips, map, toast, negotiate, Spanish, email).
