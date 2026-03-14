"""
Telegram bot → same run_agent as web UI.

.env:
  TELEGRAM_BOT_TOKEN=123456:ABC...   (from @BotFather)
  OPENAI_API_KEY=...

Run (venv):
  python telegram_bot.py

Web UI and Telegram can run at the same time; sessions are tg-<chat_id>.
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from dotenv import load_dotenv

load_dotenv()

import os

from agent import run_agent

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
if not TOKEN:
    sys.exit("Set TELEGRAM_BOT_TOKEN in .env (create bot via @BotFather)")


def main() -> None:
    try:
        from telegram import Update
        from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters
    except ImportError:
        sys.exit("pip install python-telegram-bot>=21.0")

    async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
        await update.message.reply_text(
            "Hey — I’m **Aria**. Send me what you want (e.g. 2br under 3500 SF, or a listing URL). "
            "Listings come from your ScrapeGraph database.",
            parse_mode="Markdown",
        )

    async def on_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
        if not update.message or not update.message.text:
            return
        chat_id = update.effective_chat.id
        session_id = f"tg-{chat_id}"
        await update.message.chat.send_action(action="typing")
        try:
            r = run_agent(update.message.text, session_id=session_id, lang="en")
            text = r.reply[:4000]
            if len(r.reply) > 4000:
                text += "…"
            await update.message.reply_text(text)
            for L in r.listings[:5]:
                price = L.price_display if L.listing_kind == "rent" and L.price_display else f"${L.price:,}"
                line = f"{L.title}\n{price} · {L.beds}bd · {L.city}\n{L.url}"
                await update.message.reply_text(line[:4000])
        except Exception as e:
            await update.message.reply_text(f"Something went wrong: {str(e)[:300]}")

    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))
    print("Telegram bot polling… Ctrl+C to stop")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
