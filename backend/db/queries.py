"""ORM queries — no raw SQL strings (migration uses PRAGMA in database.py)."""
from typing import Any

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from db.models import Listing, PriceHistory


def listing_to_dict(row: Listing) -> dict[str, Any]:
    return {
        "id": row.id,
        "title": row.title,
        "price": row.price,
        "beds": row.beds,
        "baths": row.baths,
        "sqft": row.sqft,
        "address": row.address,
        "city": row.city,
        "state": row.state,
        "zip_code": row.zip_code,
        "lat": row.lat,
        "lng": row.lng,
        "description": row.description or "",
        "source": row.source,
        "url": row.url,
        "walk_score": row.walk_score,
        "price_display": getattr(row, "price_display", None),
        "sqft_display": getattr(row, "sqft_display", None),
        "listing_kind": getattr(row, "listing_kind", None) or "sale",
    }


def format_price_line(x: dict[str, Any]) -> str:
    loc = f"{x.get('city') or ''}, {x.get('state') or ''}".strip(", ")
    bb = f"{x.get('beds', 0)}bd/{x.get('baths', 0)}ba"
    if x.get("listing_kind") == "rent" and x.get("price_display"):
        return f"{x['title']} — {x['price_display']} · {bb} · {loc}"
    return f"{x['title']} — ${x['price']:,} · {bb} · {loc}"


def distinct_cities_in_db(db: Session, limit: int = 12) -> list[str]:
    rows = db.execute(
        select(Listing.city, func.count(Listing.id))
        .where(Listing.city.isnot(None), Listing.city != "")
        .group_by(Listing.city)
        .order_by(func.count(Listing.id).desc())
        .limit(limit)
    ).all()
    return [r[0] for r in rows if r[0]]


def search_listings(db: Session, filters: dict[str, Any], limit: int = 5) -> list[Listing]:
    """Filters: price_min/max (sale $ or rent /mo), beds, baths, city, state, zip_code, keywords."""
    q = select(Listing)

    if filters.get("price_min") is not None:
        q = q.where(Listing.price >= int(filters["price_min"]))
    if filters.get("price_max") is not None:
        q = q.where(Listing.price <= int(filters["price_max"]))
    if filters.get("beds") is not None:
        q = q.where(Listing.beds == int(filters["beds"]))
    if filters.get("baths") is not None:
        q = q.where(Listing.baths >= float(filters["baths"]))
    if filters.get("city"):
        q = q.where(func.lower(Listing.city) == str(filters["city"]).strip().lower())
    if filters.get("state"):
        q = q.where(func.upper(Listing.state) == str(filters["state"]).strip().upper())
    if filters.get("zip_code"):
        q = q.where(Listing.zip_code == str(filters["zip_code"]).strip())
    if filters.get("listing_kind") in ("rent", "sale"):
        q = q.where(Listing.listing_kind == filters["listing_kind"])

    kw = filters.get("keywords")
    if kw:
        if isinstance(kw, str):
            kw = [kw]
        for word in kw:
            if not word:
                continue
            pattern = f"%{word.lower()}%"
            q = q.where(
                or_(
                    func.lower(Listing.description).like(pattern),
                    func.lower(Listing.title).like(pattern),
                    func.lower(Listing.address).like(pattern),
                )
            )

    q = q.limit(limit)
    return list(db.scalars(q).all())


def get_listing_by_id(db: Session, listing_id: str) -> Listing | None:
    return db.get(Listing, listing_id)


def get_listing_by_url(db: Session, url: str) -> Listing | None:
    stmt = select(Listing).where(Listing.url == url)
    return db.scalars(stmt).first()


def get_listing_by_url_contains(db: Session, url_fragment: str) -> Listing | None:
    stmt = select(Listing).where(Listing.url.contains(url_fragment))
    return db.scalars(stmt).first()


def get_comps(db: Session, zip_code: str, beds: int, exclude_id: str | None = None) -> list[Listing]:
    stmt = select(Listing).where(
        and_(Listing.zip_code == zip_code.strip(), Listing.beds == beds)
    )
    if exclude_id:
        stmt = stmt.where(Listing.id != exclude_id)
    return list(db.scalars(stmt).all())


def get_price_history_for_listing(db: Session, listing_id: str) -> list[PriceHistory]:
    stmt = (
        select(PriceHistory)
        .where(PriceHistory.listing_id == listing_id)
        .order_by(PriceHistory.recorded_at.asc())
    )
    return list(db.scalars(stmt).all())
