#!/usr/bin/env python3
"""
Interactive terminal chat — same logic as POST /chat (run_agent).

Run from backend/ with venv activated:
  python chat_cli.py
  python chat_cli.py --lang es
  python chat_cli.py --session demo
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent
_VENV_PY = _ROOT / ".venv" / "Scripts" / "python.exe"
# Global Python 3.14 often has no langchain_openai — reuse project venv automatically
if _VENV_PY.is_file():
    try:
        import langchain_openai  # noqa: F401
    except ModuleNotFoundError:
        print(
            "Relaunching with .venv\\Scripts\\python.exe (your python has no langchain_openai).",
            file=sys.stderr,
        )
        raise SystemExit(
            subprocess.call([str(_VENV_PY), str(__file__), *sys.argv[1:]], cwd=str(_ROOT))
        )

sys.path.insert(0, str(_ROOT))

from agent import clear_session, run_agent
from db.database import init_db
from db.seed import seed


def print_response(r) -> None:
    print()
    print("─" * 56)
    print(f"  type: {r.type}  |  lang: {r.lang}  |  listings: {len(r.listings)}")
    print("─" * 56)
    print(r.reply)
    print()
    if r.listings:
        print("  Listings:")
        for i, L in enumerate(r.listings, 1):
            price_s = L.price_display if L.listing_kind == "rent" and L.price_display else f"${L.price:,}"
            print(f"    {i}. {L.title} | {price_s} | {L.beds}bd/{L.baths}ba | {L.city} {L.zip_code} [{L.listing_kind}]")
            print(f"       {L.url[:70]}{'…' if len(L.url) > 70 else ''}")
    print("─" * 56)
    print()


def main() -> None:
    parser = argparse.ArgumentParser(description="Interactive real estate chat (CLI)")
    parser.add_argument("--session", default="cli", help="Session id (memory per session)")
    parser.add_argument("--lang", default="en", help="Language code, e.g. en, es")
    parser.add_argument("--no-seed", action="store_true", help="Skip auto-seed if DB empty")
    args = parser.parse_args()

    init_db()
    if not args.no_seed:
        try:
            seed(wipe=False)
        except Exception:
            pass

    session_id = args.session
    lang = args.lang

    print()
    print("  Real estate chat — type a message and press Enter.")
    print("  Commands:  quit | exit | q  ·  clear  (reset memory)  ·  help")
    print(f"  session={session_id!r}  lang={lang!r}")
    print("  (Needs OPENAI_API_KEY in .env — same as the API.)")
    print()

    while True:
        try:
            line = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nBye.")
            break

        if not line:
            continue

        lower = line.lower()
        if lower in ("quit", "exit", "q"):
            print("Bye.")
            break
        if lower == "clear":
            clear_session(session_id)
            print("(Session memory cleared.)\n")
            continue
        if lower == "help":
            print("""
  Examples:
    show me houses under $200k
    2 bedroom rentals under 4000 San Francisco
    homes with a pool
    paste a homes.com SF URL from scraper output
    should I negotiate? $320k 3bd Austin 78704
  Spanish: muéstrame alquileres de 2 habitaciones en San Francisco
""")
            continue

        try:
            r = run_agent(line, session_id=session_id, lang=lang)
            print_response(r)
        except Exception as e:
            print(f"\n  Error: {e}\n")


if __name__ == "__main__":
    main()
