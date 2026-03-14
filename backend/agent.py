"""Agent + enriched ChatResponse (chips, map data, negotiate meter, trail)."""
import re
import sys
from collections import deque
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage

import config
from schemas import ChatResponse, ListingOut
from services.chips_trail import breadcrumb_from_message, build_chips
from services.email_service import send_listings_email
from services.translate import translate_response, translate_to_english
from tools.chat_tool import run_chat_tool
from tools.filter_tool import run_filter_tool
from tools.lookup_tool import run_lookup_tool
from tools.negotiate_tool import run_negotiate_tool

sessions: dict[str, deque] = {}
MEMORY_K = 6
_trails: dict[str, list[str]] = {}
_last_listings: dict[str, list[dict]] = {}

EMAIL_RE = re.compile(
    r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", re.I
)

LANG_NAMES = {"es": "Spanish", "fr": "French", "de": "German", "hi": "Hindi", "ar": "Arabic", "pt": "Portuguese", "it": "Italian", "zh": "Chinese", "ja": "Japanese"}


def _wants_listing_email(msg: str) -> bool:
    if not EMAIL_RE.search(msg):
        return False
    m = msg.lower()
    if re.search(r"\bnegotiate\b", m) and not re.search(r"\b(email|send|mail)\b", m):
        return False
    # Any "email / send / mail" + address = try to send table (avoid pure chat)
    return bool(re.search(r"\b(email|send|e-mail|mail)\b", m))


CLASSIFIER_SYSTEM = """One word: filter | lookup | negotiate | chat"""


def get_memory(session_id: str) -> deque:
    if session_id not in sessions:
        sessions[session_id] = deque(maxlen=MEMORY_K)
    return sessions[session_id]


def clear_session(session_id: str) -> None:
    sessions.pop(session_id, None)
    _trails.pop(session_id, None)
    _last_listings.pop(session_id, None)


def classify_intent(message: str) -> str:
    llm = ChatOpenAI(model="gpt-4o", temperature=0, api_key=config.OPENAI_API_KEY)
    out = (llm.invoke([SystemMessage(content=CLASSIFIER_SYSTEM), HumanMessage(content=message)]).content or "chat").strip().lower()
    first = out.split()[0] if out else "chat"
    for token in ("filter", "lookup", "negotiate", "chat"):
        if first.startswith(token):
            return token
    for token in ("negotiate", "filter", "lookup", "chat"):
        if token in out[:24]:
            return token
    return "chat"


def _memory_context(session_id: str) -> str:
    mem = get_memory(session_id)
    return "\n".join(f"User: {u}\nAria: {a}" for u, a in mem)


def run_agent(message: str, session_id: str, lang: str) -> ChatResponse:
    """UI lang (es/fr/…) always wins for reply translation + badge; English UI can auto-detect non-English input."""
    requested = (lang or "en").lower()
    original_lang = requested
    detected_from = None
    try:
        translated, detected = translate_to_english(message)
        if detected != "en" and detected != requested:
            detected_from = detected
        if requested == "en" and detected != "en":
            original_lang = detected  # user wrote Spanish etc. while UI is English
    except Exception:
        translated, detected = message, requested

    intent = classify_intent(translated)
    if re.search(r"\bnegotiate\b", message.lower()):
        intent = "negotiate"
    # Do not hijack negotiate into filter/email flow
    wants_mail = _wants_listing_email(message) or _wants_listing_email(translated)
    # Pasted address alone after a search → still send last results
    if (
        not wants_mail
        and EMAIL_RE.search(message)
        and _last_listings.get(session_id)
        and len(message.strip()) < 120
    ):
        wants_mail = True
    if intent != "negotiate" and wants_mail:
        intent = "filter"
    if "http://" in message.lower() or "https://" in message.lower():
        intent = "lookup"

    mem = get_memory(session_id)
    ctx = _memory_context(session_id)

    try:
        if intent == "filter":
            if wants_mail and EMAIL_RE.search(message) and not re.search(
                r"\b(email|send|mail)\b", message.lower()
            ):
                # Message is basically just an address — do not re-query; email uses last_listings
                result = {
                    "reply": "Sending the listings from your last search.",
                    "listings": [],
                    "type": "filter",
                }
            else:
                # Strip email so filter LLM only sees search intent (avoids 0 results)
                filter_msg = EMAIL_RE.sub("", translated).strip() or "san francisco rentals"
                result = run_filter_tool(filter_msg, memory_context=ctx)
        elif intent == "lookup":
            result = run_lookup_tool(message)
        elif intent == "negotiate":
            result = run_negotiate_tool(translated)
        else:
            result = run_chat_tool(translated, memory_context=ctx)
    except Exception as e:
        result = {"reply": f"Something went wrong. ({str(e)[:80]})", "listings": [], "type": "chat"}

    email_sent = None
    email_note = None
    if intent == "filter":
        crumb = breadcrumb_from_message(message)
        if crumb:
            _trails.setdefault(session_id, [])
            if not _trails[session_id] or _trails[session_id][-1] != crumb:
                _trails[session_id].append(crumb)
            _trails[session_id] = _trails[session_id][-8:]

    to = EMAIL_RE.search(message) or EMAIL_RE.search(translated)
    if intent == "filter" and result.get("listings"):
        _last_listings[session_id] = list(result["listings"])

    listings_for_mail = list(result.get("listings") or [])
    if wants_mail and to and not listings_for_mail:
        listings_for_mail = list(_last_listings.get(session_id) or [])
    if wants_mail and to and not listings_for_mail:
        result = run_filter_tool("san francisco rentals browse", memory_context=ctx)
        listings_for_mail = list(result.get("listings") or [])
        if listings_for_mail:
            _last_listings[session_id] = listings_for_mail

    if intent != "negotiate" and to and wants_mail and listings_for_mail:
        ok, note = send_listings_email(to.group(0), listings_for_mail)
        email_sent = ok
        email_note = note
        base = (result.get("reply") or "").rstrip()
        if "Email:" not in base:
            result["reply"] = base + "\n\n**Email:** " + note
        result["listings"] = listings_for_mail
    elif intent != "negotiate" and to and wants_mail and not listings_for_mail:
        result["reply"] = (
            (result.get("reply") or "").rstrip()
            + "\n\nNo listings to email — run a search first, then: **Email me this list your@email.com**. "
            + "Set **RESEND_API_KEY** (or SMTP) in backend `.env`. GET /health/smtp"
        )

    reply = result.get("reply") or ""
    lang_badge = None
    if original_lang != "en":
        try:
            reply = translate_response(reply, original_lang)
        except Exception:
            pass
        lang_badge = f"Responding in {LANG_NAMES.get(original_lang, original_lang.upper())}"

    mem.append((message, reply))

    raw_listings = result.get("listings") or []
    _mc = (config.MARKET_CITY or "San Francisco").lower()
    raw_listings = [
        x for x in raw_listings if (x.get("city") or "").lower().strip() == _mc
    ]
    prices = [x.get("price", 0) for x in raw_listings if x.get("price")]
    area_median = None
    if len(prices) >= 2:
        s = sorted(prices)
        area_median = s[len(s) // 2]
    kind = raw_listings[0].get("listing_kind", "sale") if raw_listings else "sale"

    listings_out = []
    for x in raw_listings:
        p = int(x.get("price") or 0)
        pct = None
        if area_median and area_median > 0:
            pct = round((p - area_median) / area_median * 100, 1)
        listings_out.append(
            ListingOut(
                id=x["id"],
                title=x.get("title") or "",
                price=p,
                beds=int(x.get("beds") or 0),
                baths=float(x.get("baths") or 0),
                sqft=int(x.get("sqft") or 0),
                address=x.get("address") or "",
                city=x.get("city") or "",
                state=x.get("state") or "",
                zip_code=x.get("zip_code") or "",
                lat=float(x.get("lat") or 0),
                lng=float(x.get("lng") or 0),
                description=x.get("description") or "",
                source=x.get("source") or "",
                url=x.get("url") or "",
                walk_score=x.get("walk_score"),
                price_display=x.get("price_display"),
                sqft_display=x.get("sqft_display"),
                listing_kind=x.get("listing_kind") or "sale",
                pct_vs_median=pct,
            )
        )

    chips = build_chips(
        intent=intent,
        listings=raw_listings,
        message=message,
        area_median=area_median,
        kind=kind,
    )

    return ChatResponse(
        reply=reply,
        listings=listings_out,
        type=result.get("type", intent),
        lang=original_lang,
        session_id=session_id,
        email_sent=email_sent,
        email_note=email_note,
        suggested_chips=chips,
        negotiate_score=result.get("negotiate_score"),
        negotiate_label=result.get("negotiate_label"),
        area_median_price=area_median,
        scrape_ms=result.get("scrape_ms"),
        scrape_stages=result.get("scrape_stages"),
        memory_trail=list(_trails.get(session_id, [])),
        lang_badge=lang_badge,
        user_message_was_translated_from=detected_from,
    )
