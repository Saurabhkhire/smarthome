"""SQLAlchemy ORM models — supports sale + scraper/rental rows."""
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Listing(Base):
    """
    price = numeric for filters: sale = USD total; rent = monthly USD (e.g. 3200).
    price_display = scraper string e.g. \"$3,200+/mo\" when set.
    listing_kind = \"sale\" | \"rent\"
    """

    __tablename__ = "listings"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    title: Mapped[str] = mapped_column(String(512))
    price: Mapped[int] = mapped_column(Integer)
    beds: Mapped[int] = mapped_column(Integer)
    baths: Mapped[float] = mapped_column(Float)
    sqft: Mapped[int] = mapped_column(Integer)
    address: Mapped[str] = mapped_column(String(256))
    city: Mapped[str] = mapped_column(String(128))
    state: Mapped[str] = mapped_column(String(8))
    zip_code: Mapped[str] = mapped_column(String(16))
    lat: Mapped[float] = mapped_column(Float)
    lng: Mapped[float] = mapped_column(Float)
    description: Mapped[str] = mapped_column(Text, default="")
    source: Mapped[str] = mapped_column(String(64))
    url: Mapped[str] = mapped_column(String(1024))
    walk_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    scraped_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    price_display: Mapped[str | None] = mapped_column(String(128), nullable=True)
    sqft_display: Mapped[str | None] = mapped_column(String(64), nullable=True)
    listing_kind: Mapped[str] = mapped_column(String(16), default="sale")

    price_history: Mapped[list["PriceHistory"]] = relationship(
        "PriceHistory", back_populates="listing", cascade="all, delete-orphan"
    )


class PriceHistory(Base):
    __tablename__ = "price_history"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    listing_id: Mapped[str] = mapped_column(String(64), ForeignKey("listings.id"), index=True)
    price: Mapped[int] = mapped_column(Integer)
    recorded_at: Mapped[datetime] = mapped_column(DateTime)

    listing: Mapped["Listing"] = relationship("Listing", back_populates="price_history")


class TranslationCache(Base):
    __tablename__ = "translation_cache"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    source_text: Mapped[str] = mapped_column(Text, index=True)
    target_lang: Mapped[str] = mapped_column(String(16), index=True)
    translated_text: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
