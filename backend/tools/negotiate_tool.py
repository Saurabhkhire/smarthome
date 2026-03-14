"""Rent/sale negotiation coaching — conversation tips only (no email drafts)."""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import and_, func, select

from db.database import SessionLocal
from db.models import Listing
from db.queries import get_price_history_for_listing, listing_to_dict
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage

import config

RENT_COACH_SYSTEM = """You are Aria, a rental coach. The user is deciding whether to **negotiate rent** with a landlord or manager.

STRICT RULES:
- Do NOT write an email draft, letter, "Dear landlord", or "Subject:" lines.
- Do NOT format as mail — no signatures, no "Best regards".
- DO give **short, spoken-style coaching**: bullets or paragraphs about what to **say in person, on the phone, or in a portal message** (1–2 sentences they can use verbatim max).
- Reference real numbers from context when given (avg rent, how their ask compares).
- End with one clear yes/no on whether negotiating is worth trying."""

SALE_COACH_SYSTEM = """You are Aria, a buyer's coach. STRICT: no email drafts. Spoken-style advice only: offer range, comps, walk-away line."""

EXTRACT = """Extract JSON only:
price (monthly rent in USD if rental, else sale price), beds (int), city, zip_code, listing_kind ("rent" or "sale").
Example: {"price": 3200, "beds": 1, "city": "San Francisco", "zip_code": "94108", "listing_kind": "rent"}"""


def _similar_comps(db, *, city: str, beds: int, zip_code: str, kind: str, exclude_id: str | None, limit: int = 12):
    q = select(Listing).where(
        and_(
            func.lower(Listing.city) == city.lower().strip(),
            Listing.beds == beds,
            Listing.listing_kind == kind,
        )
    )
    if zip_code:
        z = zip_code.strip()
        q_zip = select(Listing).where(
            and_(Listing.zip_code == z, Listing.beds == beds, Listing.listing_kind == kind)
        )
        rows = list(db.scalars(q_zip.limit(limit)).all())
        if len(rows) >= 2:
            if exclude_id:
                rows = [r for r in rows if r.id != exclude_id]
            return rows[:limit]
    rows = list(db.scalars(q.limit(limit * 2)).all())
    if exclude_id:
        rows = [r for r in rows if r.id != exclude_id]
    return rows[:limit]


def run_negotiate_tool(message: str) -> dict:
    out_type = "negotiate"
    try:
        llm = ChatOpenAI(model="gpt-4o", temperature=0.25, api_key=config.OPENAI_API_KEY)
        raw = (llm.invoke([SystemMessage(content=EXTRACT), HumanMessage(content=message)]).content or "{}").strip()
        if "```" in raw:
            m = re.search(r"```(?:json)?\s*([\s\S]*?)```", raw)
            if m:
                raw = m.group(1).strip()
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            data = {}
        price = int(data.get("price") or 0)
        beds = int(data.get("beds") or 1)
        city = str(data.get("city") or "").strip()
        zip_code = str(data.get("zip_code") or "").strip()
        kind = str(data.get("listing_kind") or "rent").lower()
        if kind not in ("rent", "sale"):
            kind = "rent" if any(x in message.lower() for x in ("rent", "/mo", "mo ", "lease", "landlord")) else "sale"

        db = SessionLocal()
        try:
            if not city:
                city = MARKET
            count = db.scalar(select(func.count()).select_from(Listing))
            if not count:
                return {
                    "negotiate_score": 48,
                    "negotiate_label": "Worth asking",
                    "reply": (
                        "**Worth trying?** Usually yes if the unit’s been listed a while.\n\n"
                        "**What to say (out loud, not email):** Ask if they’ll take **$50–150 less/mo** or **one month free** on a 12-month lease. "
                        "Mention you’re ready to sign this week. If they say no, ask about **parking** or **storage** instead.\n\n"
                        "Run `python scraper.py` so I can compare your ask to real listings in your zip."
                    ),
                    "listings": [],
                    "type": out_type,
                }

            comps = _similar_comps(db, city=city, beds=beds, zip_code=zip_code, kind=kind, exclude_id=None, limit=14)
            subject = next((c for c in comps if c.price == price and c.beds == beds), None)
            exclude = subject.id if subject else None
            comps = _similar_comps(db, city=city, beds=beds, zip_code=zip_code, kind=kind, exclude_id=exclude, limit=10)
            prices = [c.price for c in comps if c.price and c.price > 0]
            avg = sum(prices) // len(prices) if len(prices) >= 2 else (prices[0] if prices else price or 1)
            listings_out = ([listing_to_dict(subject)] if subject else []) + [listing_to_dict(c) for c in comps[:5]]
            listings_out = listings_out[:6]

            # 0–100 negotiation power (higher = more leverage)
            if kind == "rent" and avg:
                if price <= avg * 0.92:
                    neg_score, neg_label = 78, "You have leverage — ask below typical"
                elif price <= avg * 1.05:
                    neg_score, neg_label = 58, "Room to negotiate timing / concessions"
                else:
                    neg_score, neg_label = 38, "Market is tight at this ask"
            elif kind == "sale" and avg:
                delta_pct = (price - avg) / avg * 100 if avg else 0
                if delta_pct < -5:
                    neg_score, neg_label = 72, "Strong position vs comps"
                elif delta_pct < 8:
                    neg_score, neg_label = 55, "Fair zone — negotiate inspection"
                else:
                    neg_score, neg_label = 35, "Listed high vs area median"
            else:
                neg_score, neg_label = 52, "Enough to start a conversation"

            if kind == "rent":
                human = (
                    f"User question (paraphrase): negotiate **${price}/mo** for **{beds}BR** in **{city} {zip_code}**.\n"
                    f"From our DB: **{len(prices)}** similar rentals; typical ask about **${avg}/mo**. "
                    f"Their unit is **{'above' if price > avg else 'at or below'}** that average.\n\n"
                    "Reply in **spoken coaching only**. Sections: (1) Should they negotiate? (2) 3 concrete tactics. (3) One line they can say aloud. No email."
                )
                reply = llm.invoke(
                    [SystemMessage(content=RENT_COACH_SYSTEM), HumanMessage(content=human)]
                ).content
            else:
                delta = ((price - avg) / avg * 100) if avg else 0
                hist = ""
                if subject:
                    ph = get_price_history_for_listing(db, subject.id)
                    if ph:
                        hist = " History: " + " → ".join(f"${p.price:,}" for p in ph)
                human = (
                    f"Buyer at **${price:,}**, {beds}bd **{city}**. Comps avg **${avg:,}** ({len(prices)} listings). {delta:+.1f}% vs avg.{hist} "
                    "Coaching only—no email draft."
                )
                reply = llm.invoke(
                    [SystemMessage(content=SALE_COACH_SYSTEM), HumanMessage(content=human)]
                ).content

            return {
                "reply": (reply or "").strip(),
                "listings": listings_out,
                "type": out_type,
                "negotiate_score": neg_score,
                "negotiate_label": neg_label,
            }
        finally:
            db.close()
    except Exception as e:
        return {
            "reply": f"Quick take: ask for **one month free** or **$75 off/mo** if the listing is stale. ({str(e)[:80]})",
            "listings": [],
            "type": out_type,
            "negotiate_score": 50,
            "negotiate_label": "Try anyway",
        }
