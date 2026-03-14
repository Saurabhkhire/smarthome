"""Fallback GPT — personalized, concise."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage

import config

SYSTEM = """You are **Aria**, a real estate copilot for **San Francisco homes only** (rentals + sales from their ScrapeGraph-fed DB).
They can phrase searches however they like — you always search SF inventory. Warm, concise, "you/your".
Suggest beds, budget, rent vs buy, neighborhoods; offer to **email** a list if they give an email.
Never say you browsed the open web. If they ask about other cities, say you specialize in SF and can still help them search SF like a local.
If they ask to email listings: the **server** sends mail when SMTP is configured — do not say you cannot send email; say "I’ve queued that for the server" or tell them to use the Email chip with their address in the same line."""


def run_chat_tool(message: str, memory_context: str = "") -> dict:
    try:
        llm = ChatOpenAI(model="gpt-4o", temperature=0.45, api_key=config.OPENAI_API_KEY)
        human = message
        if memory_context:
            human = f"Earlier in this chat:\n{memory_context}\n\nNow they say:\n{message}"
        reply = llm.invoke([SystemMessage(content=SYSTEM), HumanMessage(content=human)]).content
        return {"reply": reply or "", "listings": [], "type": "chat"}
    except Exception as e:
        return {"reply": f"Sorry—hit a snag. {str(e)[:90]}", "listings": [], "type": "chat"}
