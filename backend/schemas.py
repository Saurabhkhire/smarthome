"""Pydantic API models."""
from typing import List, Optional

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str
    session_id: str = "default"
    lang: str = "en"


class ListingOut(BaseModel):
    id: str
    title: str
    price: int = 0
    beds: int = 0
    baths: float = 0
    sqft: int = 0
    address: str = ""
    city: str = ""
    state: str = ""
    zip_code: str = ""
    lat: float = 0
    lng: float = 0
    description: str = ""
    source: str = ""
    url: str = ""
    walk_score: Optional[int] = None
    price_display: Optional[str] = None
    sqft_display: Optional[str] = None
    listing_kind: str = "sale"
    pct_vs_median: Optional[float] = None


class ChatResponse(BaseModel):
    reply: str
    listings: List[ListingOut]
    type: str
    lang: str
    session_id: str
    email_sent: Optional[bool] = None
    email_note: Optional[str] = None
    suggested_chips: List[str] = Field(default_factory=list)
    negotiate_score: Optional[int] = None
    negotiate_label: Optional[str] = None
    area_median_price: Optional[int] = None
    scrape_ms: Optional[float] = None
    scrape_stages: Optional[List[str]] = None
    memory_trail: List[str] = Field(default_factory=list)
    lang_badge: Optional[str] = None
    user_message_was_translated_from: Optional[str] = None
