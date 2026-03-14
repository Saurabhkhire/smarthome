"""NL → JSON filters → search_listings. Always scoped to MARKET_CITY (San Francisco)."""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from db.database import SessionLocal
from db.queries import format_price_line, listing_to_dict, search_listings
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage

import config

MARKET = config.MARKET_CITY

EXTRACT_SYSTEM = f"""Extract search filters from the user message. Return ONLY valid JSON.

Product rule: inventory is **{MARKET} only**. Users may mention any city in conversation — still extract beds, budget, rent vs buy, zip, amenities — never use another city for filtering.

Keys (optional): price_min, price_max (sale $ or rent/mo), beds, baths, zip_code, keywords (array, amenity words like pool, parking),
listing_kind ("rent" or "sale"). Omit city — server always searches {MARKET}.

Examples:
{{"price_max": 3500, "beds": 1, "listing_kind": "rent"}}
{{"price_max": 900000, "beds": 2, "listing_kind": "sale", "keywords": ["pool"]}}"""


def _parse_json_loose(s: str) -> dict:
    s = s.strip()
    if "```" in s:
        m = re.search(r"```(?:json)?\s*([\s\S]*?)```", s)
        if m:
            s = m.group(1).strip()
    return json.loads(s)


def run_filter_tool(message: str, memory_context: str = "") -> dict:
    out_type = "filter"
    try:
        llm = ChatOpenAI(model="gpt-4o", temperature=0, api_key=config.OPENAI_API_KEY)
        human = message
        if memory_context:
            human = f"Prior conversation context:\n{memory_context}\n\nCurrent user message:\n{message}"
        filters: dict = {}
        for attempt in range(2):
            try:
                r = llm.invoke(
                    [SystemMessage(content=EXTRACT_SYSTEM), HumanMessage(content=human)]
                )
                content = (r.content or "").strip()
                filters = _parse_json_loose(content)
                break
            except (json.JSONDecodeError, ValueError):
                if attempt == 1:
                    filters = {
                        "keywords": [w for w in re.split(r"\W+", message.lower()) if len(w) > 2][:5]
                    }
                else:
                    continue
        else:
            filters = {}

        # Never search outside our market
        filters.pop("city", None)
        filters["city"] = MARKET

        has_scope = any(
            [
                filters.get("price_max"),
                filters.get("price_min"),
                filters.get("beds") is not None,
                filters.get("baths") is not None,
                filters.get("zip_code"),
                filters.get("keywords"),
                filters.get("listing_kind"),
            ]
        )
        if not has_scope:
            # Browse SF inventory
            filters = {"city": MARKET}

        db = SessionLocal()
        try:
            rows = search_listings(db, filters, limit=10)
            listings = [listing_to_dict(r) for r in rows]
        finally:
            db.close()

        lead = f"**{MARKET}** — "
        if not listings:
            reply = (
                lead
                + "no matches for that filter. Try a wider budget, different beds, or run **scraper.py** to refresh inventory."
            )
        else:
            reply = (
                lead
                + f"{len(listings)} home(s) matching your search: "
                + "; ".join(format_price_line(x) for x in listings[:6])
            )
        return {"reply": reply, "listings": listings, "type": out_type}
    except Exception as e:
        return {
            "reply": f"I couldn't run that search right now. ({str(e)[:120]})",
            "listings": [],
            "type": out_type,
        }
