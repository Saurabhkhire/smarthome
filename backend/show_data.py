"""Print everything stored in listings.db (run from backend/)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from sqlalchemy import select

from db.database import SessionLocal, init_db
from db.models import Listing, PriceHistory, TranslationCache

init_db()
db = SessionLocal()
try:
    listings = list(db.scalars(select(Listing)).all())
    print("=" * 60)
    print(f"LISTINGS ({len(listings)} rows) | DB file: listings.db")
    print("=" * 60)
    for r in listings:
        print(f"\n  ID:       {r.id}")
        print(f"  Title:    {r.title}")
        kind = getattr(r, "listing_kind", "sale") or "sale"
        pd = getattr(r, "price_display", None)
        print(f"  Kind:     {kind}")
        print(f"  Price:    {pd or f'${r.price:,}'}")
        sd = getattr(r, "sqft_display", None)
        print(f"  Beds/Baths/Sqft: {r.beds} / {r.baths} / {sd or r.sqft}")
        print(f"  Address:  {r.address}, {r.city}, {r.state} {r.zip_code}")
        print(f"  Source:   {r.source}   Walk score: {r.walk_score}")
        print(f"  URL:      {r.url}")
        print(f"  Desc:     {r.description[:120]}...")

    print("\n" + "=" * 60)
    print("PRICE_HISTORY")
    print("=" * 60)
    for p in db.scalars(select(PriceHistory)).all():
        print(f"  {p.listing_id}  ${p.price:,}  recorded_at={p.recorded_at}")

    n = len(list(db.scalars(select(TranslationCache)).all()))
    print("\n" + "=" * 60)
    print(f"TRANSLATION_CACHE ({n} rows)")
    print("=" * 60)
    for t in db.scalars(select(TranslationCache).limit(20)):
        print(f"  [{t.target_lang}] {t.source_text[:50]}... -> {t.translated_text[:50]}...")
finally:
    db.close()
