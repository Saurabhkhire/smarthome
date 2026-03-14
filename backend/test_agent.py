"""Optional smoke test — needs OPENAI_API_KEY + listings in DB (run scraper first)."""
import subprocess
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent
_VENV_PY = _ROOT / ".venv" / "Scripts" / "python.exe"
if _VENV_PY.is_file():
    try:
        import langchain_openai  # noqa: F401
    except ModuleNotFoundError:
        raise SystemExit(subprocess.call([str(_VENV_PY), str(__file__), *sys.argv[1:]], cwd=str(_ROOT)))

sys.path.insert(0, str(_ROOT))

from agent import run_agent
from db.database import SessionLocal, init_db
from db.models import Listing
from sqlalchemy import func, select


def main():
    init_db()
    db = SessionLocal()
    try:
        n = db.scalar(select(func.count()).select_from(Listing)) or 0
    finally:
        db.close()
    if n == 0:
        print("No listings — run: python scraper.py (or seed --wipe then scraper). Skipping LLM tests.")
        return
    r = run_agent("hello", "test", "en")
    print("chat:", r.reply[:120])
    r2 = run_agent("1 bedroom under 5000 san francisco", "test2", "en")
    print("filter type:", r2.type, "listings:", len(r2.listings))
    print("OK")


if __name__ == "__main__":
    main()
