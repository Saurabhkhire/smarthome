"""SQLite + SQLAlchemy engine and sessions."""
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

import config
from db.models import Base

engine = create_engine(
    config.DATABASE_URL,
    connect_args={"check_same_thread": False},
    echo=False,
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def _migrate_listings_table() -> None:
    """Add scraper columns to existing SQLite DB (idempotent)."""
    with engine.connect() as conn:
        rows = conn.execute(text("PRAGMA table_info(listings)")).fetchall()
        names = {r[1] for r in rows}
        alters = []
        if "price_display" not in names:
            alters.append("ALTER TABLE listings ADD COLUMN price_display VARCHAR(128)")
        if "sqft_display" not in names:
            alters.append("ALTER TABLE listings ADD COLUMN sqft_display VARCHAR(64)")
        if "listing_kind" not in names:
            alters.append("ALTER TABLE listings ADD COLUMN listing_kind VARCHAR(16) DEFAULT 'sale'")
        for sql in alters:
            conn.execute(text(sql))
        conn.commit()


def init_db() -> None:
    Base.metadata.create_all(bind=engine)
    _migrate_listings_table()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
