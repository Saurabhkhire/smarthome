"""
Map scraper / Redfin-style JSON into Listing rows.

Expected shape (flexible):
  id, title, address, price (str or int), beds, baths, sqft (str or int),
  city, state, zip_code, description, source, url, walk_score
"""
from __future__ import annotations

import hashlib
import re
from typing import Any

import config

from db.database import SessionLocal, init_db
from db.models import Listing

MARKET = getattr(config, "MARKET_CITY", "San Francisco")


def _sentinel(v: Any) -> Any:
    """Scraper uses -1 for null; DB uses None."""
    if v == -1 or v == "-1":
        return None
    return v


def _int_from_str(s: str | int | None, default: int = 0) -> int:
    if s is None:
        return default
    if isinstance(s, int):
        return s
    digits = re.sub(r"[^\d]", "", str(s))
    return int(digits) if digits else default


def _rent_monthly_numeric(price_str: str) -> int:
    """'$3,200+/mo' -> 3200"""
    m = re.search(r"[\d,]+", price_str.replace(",", ""))
    if not m:
        return 0
    return int(re.sub(r"\D", "", m.group(0)))


def _sqft_min(sqft: str | int | None) -> tuple[int, str | None]:
    if sqft is None:
        return 0, None
    if isinstance(sqft, int):
        return sqft, None
    s = str(sqft).strip()
    if "-" in s:
        parts = s.split("-", 1)
        lo = _int_from_str(parts[0], 0)
        return lo, s
    return _int_from_str(s, 0), None


def scraper_row_to_listing(data: dict[str, Any]) -> Listing:
    data = {k: _sentinel(v) for k, v in data.items()}
    lid = data.get("id")
    if lid is None or str(lid).strip() in ("", "None"):
        base = f"{data.get('url', '')}|{data.get('address', '')}"
        lid = hashlib.sha256(base.encode()).hexdigest()[:16]
    else:
        lid = str(lid)[:64]

    price_raw = data.get("price", 0)
    price_display = None
    listing_kind = "sale"
    if isinstance(price_raw, str) and ("/mo" in price_raw.lower() or "mo" in price_raw.lower()):
        listing_kind = "rent"
        price_display = price_raw.strip()
        price = _rent_monthly_numeric(price_raw)
    elif isinstance(price_raw, str):
        price = _int_from_str(price_raw, 0)
    else:
        try:
            price = int(price_raw or 0)
        except (TypeError, ValueError):
            price = 0

    beds = _int_from_str(data.get("beds"), 0)
    baths = float(_int_from_str(str(data.get("baths", "0")).split(".")[0], 0))
    if isinstance(data.get("baths"), str) and "." in str(data["baths"]):
        try:
            baths = float(data["baths"])
        except ValueError:
            pass

    sqft, sqft_display = _sqft_min(data.get("sqft"))

    lat = float(data.get("lat") or 0)
    lng = float(data.get("lng") or 0)
    # Single-market app: normalize city so DB never mixes Austin etc. from bad extracts
    data["city"] = MARKET
    if not str(data.get("state", "")).strip():
        data["state"] = "CA"
    if not lat and not lng:
        lat, lng = 37.7749, -122.4194  # SF center for map pins

    walk = data.get("walk_score")
    if walk is not None:
        try:
            walk = int(walk)
        except (TypeError, ValueError):
            walk = None

    return Listing(
        id=lid,
        title=str(data.get("title", ""))[:512],
        price=price,
        beds=beds,
        baths=baths,
        sqft=sqft or 0,
        address=str(data.get("address", ""))[:256],
        city=MARKET[:128],
        state=str(data.get("state", "CA"))[:8],
        zip_code=str(data.get("zip_code", ""))[:16],
        lat=lat,
        lng=lng,
        description=str(data.get("description") or ""),
        source=str(data.get("source", "scraper"))[:64],
        url=str(data.get("url", ""))[:1024],
        walk_score=walk,
        price_display=price_display,
        sqft_display=sqft_display,
        listing_kind=listing_kind,
    )


def upsert_listing(data: dict[str, Any]) -> Listing:
    """Insert or update by id."""
    init_db()
    row = scraper_row_to_listing(data)
    db = SessionLocal()
    try:
        existing = db.get(Listing, row.id)
        if existing:
            for k in (
                "title", "price", "beds", "baths", "sqft", "address", "city", "state",
                "zip_code", "lat", "lng", "description", "source", "url", "walk_score",
                "price_display", "sqft_display", "listing_kind",
            ):
                setattr(existing, k, getattr(row, k))
            db.commit()
            db.refresh(existing)
            return existing
        db.add(row)
        db.commit()
        db.refresh(row)
        return row
    finally:
        db.close()
