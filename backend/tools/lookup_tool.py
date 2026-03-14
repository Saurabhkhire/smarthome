"""URL → listing in DB only (scraper data). No demo/fallback URLs."""
import re
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from db.database import SessionLocal
from db.models import Listing
from db.queries import get_listing_by_url, listing_to_dict
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage
from sqlalchemy import select

import config

URL_RE = re.compile(r"https?://[^\s]+", re.I)


def _hidden_costs(description: str) -> list[str]:
    found = []
    text = description.lower()
    if "hoa" in text:
        found.append("HOA fees mentioned")
    if "pet deposit" in text or "pet fee" in text:
        found.append("Pet deposit/fee")
    if "special assessment" in text:
        found.append("Special assessment")
    return found


def run_lookup_tool(message: str) -> dict:
    out_type = "lookup"
    t0 = time.perf_counter()
    stages = ["Resolving URL…", "Matching scraped listing in DB…"]
    try:
        urls = URL_RE.findall(message)
        url = urls[0] if urls else None
        if not url:
            return {
                "reply": "Paste a full listing URL that was ingested by **python scraper.py** (same URL as in the DB).",
                "listings": [],
                "type": out_type,
                "scrape_ms": round((time.perf_counter() - t0) * 1000, 0),
                "scrape_stages": stages + ["No URL"],
            }

        db = SessionLocal()
        try:
            listing = get_listing_by_url(db, url)
            if not listing:
                path = urlparse(url).path.strip("/")
                for row in db.scalars(select(Listing)):
                    if path and path in (row.url or ""):
                        listing = row
                        break
            if not listing:
                for row in db.scalars(select(Listing)):
                    u, v = url.rstrip("/"), (row.url or "").rstrip("/")
                    if u in row.url or row.url in url or (v and v in u):
                        listing = row
                        break
            if not listing:
                return {
                    "reply": (
                        "That URL is not in the database. Run **scraper.py** on that site first, "
                        "then paste the exact listing URL you ingested."
                    ),
                    "listings": [],
                    "type": out_type,
                    "scrape_ms": round((time.perf_counter() - t0) * 1000, 0),
                    "scrape_stages": stages + ["No match — scrape this URL first"],
                }
            data = listing_to_dict(listing)
            hidden = _hidden_costs(listing.description or "")
            llm = ChatOpenAI(model="gpt-4o", temperature=0.3, api_key=config.OPENAI_API_KEY)
            sys_msg = """Summarize this listing in exactly 3 short bullet points. Be factual."""
            user = f"Title: {listing.title}\nPrice: ${listing.price}\nBeds/Baths: {listing.beds}/{listing.baths}\nDescription: {listing.description}\nURL: {listing.url}"
            summary = llm.invoke([SystemMessage(content=sys_msg), HumanMessage(content=user)]).content
            flags = ""
            if hidden:
                flags = " Hidden costs flagged: " + ", ".join(hidden) + "."
            reply = f"{summary}{flags}"
            stages.append("AI summary… done")
            return {
                "reply": reply,
                "listings": [data],
                "type": out_type,
                "scrape_ms": round((time.perf_counter() - t0) * 1000, 0),
                "scrape_stages": stages,
            }
        finally:
            db.close()
    except Exception as e:
        return {
            "reply": f"Lookup failed: {str(e)[:150]}",
            "listings": [],
            "type": out_type,
            "scrape_ms": round((time.perf_counter() - t0) * 1000, 0),
            "scrape_stages": stages + ["Error"],
        }
