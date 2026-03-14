"""
Scraper → sgai extract API → dedupe → SQLite (listing_ingest).

Env:
  SCRAPER_AI_AUTH=your_token          # or full "Bearer ..."
  EXTRACT_API_URL=https://sgai-api-v2.onrender.com/api/v1/extract  (optional)

Run:
  python scraper.py                    # call API for default URLs + upsert DB
  python scraper.py --json data/combined_deduplicated.json   # JSON only, no API
  python scraper.py --dry-run          # print count only
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import requests

import config
from services.listing_ingest import upsert_listing

DEFAULT_PROMPT = (
    "extract the address, id, title, price, beds, baths, sqft, city, state, "
    "zip_code, description, source, url, walk_score as a JSON array of listings"
)

DEFAULT_URLS = {
    "homes.com": "https://www.homes.com/san-francisco-ca/homes-for-rent/",
    "redfin": "https://www.redfin.com/city/17151/CA/San-Francisco/rentals",
}

DATA_DIR = Path(__file__).resolve().parent / "data"


def replace_nulls(items: list[dict]) -> list[dict]:
    for item in items:
        for key, value in list(item.items()):
            if value is None:
                item[key] = -1
    return items


def normalize_api_listings(raw: dict) -> list[dict]:
    """Handle { json: { listings: [...] } } or { listings: [...] }."""
    if not raw:
        return []
    j = raw.get("json") or raw
    listings = j.get("listings")
    if listings is None and isinstance(j, list):
        listings = j
    if not isinstance(listings, list):
        return []
    return listings


def _post_extract(url: str, prompt: str, authorization: str) -> dict:
    endpoint = config.EXTRACT_API_URL
    if not endpoint.endswith("/extract"):
        endpoint = endpoint.rstrip("/") + "/extract"
    r = requests.post(
        endpoint,
        headers={"Content-Type": "application/json", "Authorization": authorization},
        json={"url": url, "prompt": prompt},
        timeout=180,
    )
    r.raise_for_status()
    return r.json()


ABBREVIATIONS = {
    r"\bst\b": "street",
    r"\bave\b": "avenue",
    r"\brd\b": "road",
    r"\bblvd\b": "boulevard",
    r"\bdr\b": "drive",
    r"\bln\b": "lane",
}


def normalize_address(address: str) -> str:
    if not address or address == -1:
        return ""
    addr = str(address).lower()
    for pattern, replacement in ABBREVIATIONS.items():
        addr = re.sub(pattern, replacement, addr)
    addr = re.sub(r"[.,]", "", addr)
    return re.sub(r"\s+", " ", addr).strip()


def deduplicate(listings: list[dict]) -> list[dict]:
    seen: set[str] = set()
    out: list[dict] = []
    for item in listings:
        addr = item.get("address", "")
        if addr == -1:
            addr = ""
        norm = normalize_address(str(addr))
        key = norm or str(item.get("url", "")) or str(item.get("id", ""))
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out


def listings_to_db(listings: list[dict], dry_run: bool = False) -> int:
    n = 0
    for item in listings:
        if dry_run:
            n += 1
            continue
        try:
            upsert_listing(item)
            n += 1
        except Exception as e:
            print(f"  skip id={item.get('id')}: {e}", file=sys.stderr)
    return n


def run_from_api(prompt: str | None = None, dry_run: bool = False) -> list[dict]:
    auth = config.SCRAPER_AI_AUTH
    if not auth:
        raise SystemExit("Missing SCRAPER_AI_AUTH in .env")
    prompt = prompt or DEFAULT_PROMPT
    combined: list[dict] = []
    for site, url in DEFAULT_URLS.items():
        print(f"Extracting {site} ...")
        raw = _post_extract(url, prompt, auth)
        listings = normalize_api_listings(raw)
        listings = replace_nulls(listings)
        for row in listings:
            if not row.get("source") or row.get("source") == -1:
                row["source"] = site
        combined.extend(listings)
        print(f"  {len(listings)} listings")

    cleaned = deduplicate(combined)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(DATA_DIR / "combined_deduplicated.json", "w", encoding="utf-8") as f:
        json.dump(cleaned, f, indent=2)
    print(f"Deduped: {len(cleaned)} -> data/combined_deduplicated.json")

    if not dry_run:
        from db.seed import purge_non_sf

        removed = purge_non_sf()
        if removed:
            print(f"Purge non-SF: removed {removed} old row(s) before upsert")
        listings_to_db(cleaned)
        print(f"Upserted {len(cleaned)} rows into listings.db (city normalized to San Francisco)")
    return cleaned


def run_from_json(path: Path, dry_run: bool = False) -> int:
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        data = normalize_api_listings(data)
    cleaned = deduplicate(data)
    if not dry_run:
        from db.seed import purge_non_sf

        purge_non_sf()
    n = listings_to_db(cleaned, dry_run=dry_run)
    if not dry_run:
        print(f"Upserted {n} listings from {path}")
    return n


def scrape_url(url: str) -> dict:
    """Legacy: fetch HTML snippet (optional)."""
    try:
        r = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
        text = re.sub(r"<[^>]+>", " ", r.text)[:8000]
        return {"url": url, "raw_text": text, "ok": r.ok}
    except Exception as e:
        return {"url": url, "error": str(e), "ok": False}


def main() -> None:
    parser = argparse.ArgumentParser(description="Scraper → extract API → DB")
    parser.add_argument("--json", type=Path, help="Load listings from JSON only (no API)")
    parser.add_argument("--dry-run", action="store_true", help="No DB writes / API still runs unless --json")
    parser.add_argument("--prompt", default=None, help="Override extract prompt")
    args = parser.parse_args()

    if args.json:
        run_from_json(args.json, dry_run=args.dry_run)
        return
    run_from_api(prompt=args.prompt, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
