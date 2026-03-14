"""Init DB + migrations only. Listings come from ScrapeGraph/scraper — no demo seed."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from db.database import SessionLocal, init_db
from db.models import Listing, PriceHistory
from sqlalchemy import delete, func, select


def purge_non_sf() -> int:
    """Delete listings whose city is not San Francisco (fixes old Austin/demo rows)."""
    init_db()
    from sqlalchemy import delete

    db = SessionLocal()
    try:
        sub = select(Listing.id).where(
            func.lower(func.coalesce(Listing.city, "")) != "san francisco"
        )
        ids = [r[0] for r in db.execute(sub).all()]
        if not ids:
            return 0
        db.execute(delete(PriceHistory).where(PriceHistory.listing_id.in_(ids)))
        db.execute(delete(Listing).where(Listing.id.in_(ids)))
        db.commit()
        return len(ids)
    finally:
        db.close()


def wipe_all_listings() -> int:
    """Delete every listing and price history (ScrapeGraph is source of truth)."""
    init_db()
    db = SessionLocal()
    try:
        n = db.scalar(select(func.count()).select_from(Listing)) or 0
        db.execute(delete(PriceHistory))
        db.execute(delete(Listing))
        db.commit()
        return n
    finally:
        db.close()


def seed(wipe: bool = False) -> None:
    init_db()
    if wipe:
        n = wipe_all_listings()
        print(f"Wiped {n} listings + price history. DB ready for scraper.")
    else:
        print("DB ready. Run: python scraper.py (or --json) to fill listings. Use seed(wipe=True) to clear.")


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--wipe", action="store_true", help="Delete all listings first")
    p.add_argument(
        "--sf-only",
        action="store_true",
        help="Delete every row that is NOT San Francisco (keep SF scraper data)",
    )
    args = p.parse_args()
    if args.sf_only:
        n = purge_non_sf()
        print(f"Removed {n} non-San Francisco listing(s). SF-only DB.")
        sys.exit(0)
    seed(wipe=args.wipe)
