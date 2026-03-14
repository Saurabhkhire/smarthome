"""Smart chips + memory breadcrumbs (no extra LLM call)."""
from __future__ import annotations

import re
from typing import Any


def breadcrumb_from_message(msg: str) -> str | None:
    m = msg.strip()
    if len(m) > 48:
        m = m[:45] + "…"
    if not m:
        return None
    return m


def build_chips(
    *,
    intent: str,
    listings: list[dict[str, Any]],
    message: str,
    area_median: int | None,
    kind: str,
) -> list[str]:
    chips: list[str] = []
    msg_l = message.lower()
    if intent == "filter" and listings:
        prices = [x.get("price", 0) for x in listings if x.get("price")]
        if prices:
            mx = max(prices)
            mn = min(prices)
            floor = max(1, mn - 1)
            chips.append(f"Under ${floor:,}/mo" if kind == "rent" else f"Under ${floor:,}")
            chips.append(f"Under ${mx + 500:,}/mo" if kind == "rent" else f"Under ${int(mx * 1.15):,}")
        chips.append("Add pool")
        chips.append("2 bedrooms in SF")
        chips.append("Rentals only")
        chips.append("Negotiate rent on a place like this")
        chips.append("Email me this list you@email.com")
    elif intent == "negotiate":
        chips.append("How do I frame a lower offer?")
        chips.append("What if they refuse rent reduction?")
        chips.append("Should I ask for one month free?")
    elif intent == "lookup":
        chips.append("Similar homes nearby")
        chips.append("Is price fair?")
    else:
        chips.append("1br under 4000")
        chips.append("2 bed with pool SF")
        chips.append("Cheapest rentals SF")
    seen = set()
    out = []
    for c in chips:
        if c not in seen and len(out) < 5:
            seen.add(c)
            out.append(c)
    return out
