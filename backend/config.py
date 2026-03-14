"""Environment — always load .env from this folder (fixes uvicorn --reload cwd)."""
import os
from pathlib import Path

from dotenv import load_dotenv

_BACKEND_DIR = Path(__file__).resolve().parent

# Load backend/.env no matter where you started the process (run_server.bat, IDE, etc.)
for _name in (".env", ".env.local"):
    _p = _BACKEND_DIR / _name
    if _p.is_file():
        load_dotenv(_p, override=True)


def _strip_quotes(s: str) -> str:
    s = (s or "").strip()
    if len(s) >= 2 and s[0] == s[-1] and s[0] in ('"', "'"):
        return s[1:-1]
    return s


OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
DEEPL_API_KEY = os.getenv("DEEPL_API_KEY", "")
DB_PATH = os.getenv("DB_PATH", str(_BACKEND_DIR / "listings.db"))
if not Path(DB_PATH).is_absolute():
    DB_PATH = str(_BACKEND_DIR / DB_PATH.lstrip("./"))

SCRAPER_AI_AUTH = os.getenv("SCRAPER_AI_AUTH", "").strip()

# Single-market product: all listing searches scope to this city (natural language still works).
MARKET_CITY = os.getenv("MARKET_CITY", "San Francisco").strip() or "San Francisco"
if SCRAPER_AI_AUTH and not SCRAPER_AI_AUTH.lower().startswith("bearer "):
    SCRAPER_AI_AUTH = f"Bearer {SCRAPER_AI_AUTH}"
EXTRACT_API_URL = os.getenv("EXTRACT_API_URL", "https://sgai-api-v2.onrender.com/api/v1/extract").rstrip("/")

# SMTP — support SMTP_PASS or SMTP_PASSWORD / GMAIL_APP_PASSWORD
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com").strip()
SMTP_PORT = int(os.getenv("SMTP_PORT", "465") or "465")
SMTP_USER = _strip_quotes(os.getenv("SMTP_USER", "") or os.getenv("GMAIL_USER", ""))
SMTP_PASS = _strip_quotes(
    os.getenv("SMTP_PASS", "")
    or os.getenv("SMTP_PASSWORD", "")
    or os.getenv("GMAIL_APP_PASSWORD", "")
)
SMTP_PASS = SMTP_PASS.replace(" ", "")  # app passwords sometimes pasted with spaces
SMTP_FROM = _strip_quotes(os.getenv("SMTP_FROM", "") or SMTP_USER or "noreply@localhost")

# Resend (https://resend.com) — preferred when set; no SMTP needed
RESEND_API_KEY = _strip_quotes(os.getenv("RESEND_API_KEY", ""))
RESEND_FROM = _strip_quotes(
    os.getenv("RESEND_FROM", "") or "Aria <onboarding@resend.dev>"
)

DATABASE_URL = f"sqlite:///{DB_PATH}"
