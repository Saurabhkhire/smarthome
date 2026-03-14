# Demo script — **San Francisco only** (matches `scraper.py` data)

## Load the same data the scraper uses (no Austin rows)

**One-time cleanup + load SF JSON** (uses checked-in `data/combined_deduplicated.json` from homes.com + Redfin SF rents):

```bash
cd backend
.venv\Scripts\python.exe db\seed.py --sf-only
.venv\Scripts\python.exe scraper.py --json data\combined_deduplicated.json
```

- `--sf-only` deletes every listing whose city is **not** San Francisco (removes old Austin/demo rows).
- `--json` loads only SF rows from the file (same shape as after `python scraper.py` with API).

**With API** (refreshes JSON + DB):

```bash
# .env: SCRAPER_AI_AUTH=Bearer ...
.venv\Scripts\python.exe scraper.py
```

Scraper always **purges non-SF** before upsert; ingest **forces city = San Francisco** so new extracts never mix markets.

---

## Sample rows in `combined_deduplicated.json` (real copy-paste)

| Address / title | Beds | Rent (approx) | Zip |
|-----------------|------|---------------|-----|
| 50 Jerrold Ave Unit 214 | 2bd/2ba | $3,800/mo | 94124 |
| 355 Berry St (Edgewater) | — | $3,732/mo | 94158 |
| 260 King St Unit 885 | 2bd/2ba | $5,650/mo | 94107 |
| 399 Fremont St | 3bd | $4k–$7.9k/mo | 94105 |
| 1800 Pacific Ave | 1bd/1ba | $4,800/mo | 94109 |

---

## Chat demo lines (aligned to that data)

1. **Broad SF browse**  
   `2 bedroom rentals under 4000`  
   → Should include **50 Jerrold** ($3,800) if in top results.

2. **Zip 94107**  
   `anything under 6000 in zip 94107`  
   → Should surface **260 King St** ($5,650).

3. **Pacific / Nob area**  
   `1 bedroom under 5000 pacific`  
   → **1800 Pacific Ave** ($4,800).

4. **Lookup (exact URL from JSON)**  
   `https://www.homes.com/property/50-jerrold-ave-san-francisco-ca-unit-214/n0rn1ysvxsnym/`  
   → Summary + toast; listing must exist in DB (same URL as scrape).

5. **Second lookup**  
   `https://www.homes.com/property/1800-pacific-ave-san-francisco-ca/xzpy4kmy1q3xm/`

6. **Negotiate (SF rent)**  
   `Negotiate: 3800/mo 2br San Francisco 94124`  
   → Meter + comps from SF DB.

7. **“Search from anywhere” (still SF)**  
   `I'm in Dallas but need a cheap 2br near the water`  
   → Reply still **San Francisco —** results only.

8. **Email (after a search with results)**  
   `Email me this list you@example.com`  
   (Include an email + send/listings wording.)

---

## If you still see Austin

1. Run **`db\seed.py --sf-only`** again.  
2. Re-load JSON or full **`scraper.py`**.  
3. Hard refresh the React app (new session clears cached listing state).
