"""
geocode_locations.py
====================
Geocodes Bebat collection locations using Nominatim (OpenStreetMap).

WHAT IT DOES
------------
1. Reads COLLECTION_DATA.xlsx
2. Sends each unique location's name to Nominatim, biased to Belgium
3. Caches every result to geocoded_cache.json (so it only ever runs once)
4. Writes locations_geocoded.csv with lat/lng + a `geocoded` flag

USAGE
-----
    python geocode_locations.py

  - First run: ~3.8 hours for full dataset (Nominatim allows 1 request/sec)
  - You can interrupt at any time (Ctrl+C) — progress is saved every 50 lookups
  - Restart and it resumes from the cache automatically
  - The notebook reads `locations_geocoded.csv` directly

REQUIREMENTS
------------
    pip install pandas openpyxl
    (no API key needed — Nominatim is free)

NOMINATIM USAGE POLICY
----------------------
This script complies with https://operations.osmfoundation.org/policies/nominatim/:
  * Sends a valid User-Agent header identifying the application
  * Throttles to <1 request/second
  * Caches results to avoid re-querying

If you have a heavy production use case, consider:
  * Self-hosting Nominatim (Docker image available)
  * Using a paid alternative (LocationIQ, Google Places, Mapbox)
"""

import json
import sys
import time
import urllib.parse
import urllib.request
import urllib.error
from pathlib import Path
from datetime import datetime, timedelta

import pandas as pd

# -----------------------------------------------------------------------------
# Configuration
# -----------------------------------------------------------------------------
EXCEL_PATH = Path("COLLECTION DATA.xlsx")
CACHE_PATH = Path("geocoded_cache.json")
OUTPUT_CSV = Path("locations_geocoded.csv")

# IMPORTANT: edit this to include your real contact email — Nominatim requires it
USER_AGENT = "BebatThesisGeocoder/1.0 (KU Leuven Master Thesis; contact: victor.rommel10@gmail.com)"

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
RATE_LIMIT_SEC = 1.1   # >1s to stay under Nominatim's 1 req/sec ceiling
SAVE_EVERY = 50        # flush cache to disk every N lookups
TIMEOUT_SEC = 15

# -----------------------------------------------------------------------------

def load_cache() -> dict:
    if CACHE_PATH.exists():
        with open(CACHE_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}


def save_cache(cache: dict) -> None:
    tmp = CACHE_PATH.with_suffix('.json.tmp')
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(cache, f, ensure_ascii=False, indent=1)
    tmp.replace(CACHE_PATH)  # atomic write — no half-written cache files


def build_query(channel: str, name: str) -> str:
    """Channel-aware query construction.

    Example transforms:
      Recycling centres:  "RP ZONHOVEN"             -> "Recyclagepark Zonhoven, Belgium"
      Retail:             "AVEVE DIEST"             -> "AVEVE Diest, Belgium"
      Companies/Schools:  "DRUKKERIJ ARTOOS"        -> "Drukkerij Artoos, Belgium"
    """
    name = str(name).strip()
    if channel == "Recycling centres" and name.upper().startswith("RP "):
        town = name[3:].strip().title()
        return f"Recyclagepark {town}, Belgium"
    return f"{name.title()}, Belgium"


def geocode_one(query: str) -> tuple:
    """Send one Nominatim request. Returns (lat, lng) or (None, None)."""
    params = {
        'q': query,
        'format': 'json',
        'limit': 1,
        'countrycodes': 'be',     # bias to Belgium
    }
    url = f"{NOMINATIM_URL}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={'User-Agent': USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_SEC) as resp:
            data = json.loads(resp.read())
            if data:
                return float(data[0]['lat']), float(data[0]['lon'])
    except urllib.error.HTTPError as e:
        if e.code == 429:
            print("    HTTP 429 (rate limited) — sleeping 60s before continuing")
            time.sleep(60)
        else:
            print(f"    HTTP error {e.code}")
    except (urllib.error.URLError, json.JSONDecodeError, TimeoutError, ValueError) as e:
        print(f"    Error: {type(e).__name__}: {e}")
    return None, None


def main():
    if not EXCEL_PATH.exists():
        print(f"ERROR: {EXCEL_PATH} not found in current directory.")
        print(f"       Place it next to this script and re-run.")
        sys.exit(1)

    print("=" * 70)
    print("Bebat location geocoder — Nominatim (OpenStreetMap)")
    print("=" * 70)
    print(f"Excel:    {EXCEL_PATH}")
    print(f"Cache:    {CACHE_PATH}")
    print(f"Output:   {OUTPUT_CSV}")
    print(f"User-Agent: {USER_AGENT}")
    print()
    if "your.email@kuleuven.be" in USER_AGENT:
        print("⚠  Edit USER_AGENT at the top of this script to include your real email.")
        print("    (Nominatim policy requires a valid contact.)")
        print()

    print("Loading Bebat dataset...")
    raw = pd.read_excel(EXCEL_PATH, sheet_name='Sheet0', header=None)
    col_names = ['Channel', 'LocationNumber', 'Location'] + [f'col{i}' for i in range(raw.shape[1] - 3)]
    df = raw.iloc[3:].copy()
    df.columns = col_names
    df = df.dropna(subset=['Channel', 'Location', 'LocationNumber']).reset_index(drop=True)

    unique_locs = df[['Channel', 'LocationNumber', 'Location']].drop_duplicates().reset_index(drop=True)
    print(f"  {len(unique_locs):,} unique locations to geocode")

    cache = load_cache()
    print(f"  {len(cache):,} already in cache")

    to_do = []
    for _, row in unique_locs.iterrows():
        key = f"{row['LocationNumber']}|{row['Location']}"
        if key not in cache:
            to_do.append((key, row['Channel'], row['Location']))

    print(f"  {len(to_do):,} remaining")
    print()

    if to_do:
        eta_sec = len(to_do) * RATE_LIMIT_SEC
        eta = datetime.now() + timedelta(seconds=eta_sec)
        print(f"Estimated time: {eta_sec / 3600:.1f} hours")
        print(f"Estimated finish: {eta.strftime('%Y-%m-%d %H:%M')}")
        print()
        print("Starting geocoding loop. Press Ctrl+C to stop — progress is saved.")
        print("-" * 70)

        try:
            for i, (key, channel, name) in enumerate(to_do, 1):
                query = build_query(channel, name)
                lat, lng = geocode_one(query)
                cache[key] = {
                    'lat': lat, 'lng': lng,
                    'query': query, 'channel': channel,
                    'name': name,
                }

                if i % 25 == 0 or i == len(to_do):
                    hits = sum(1 for v in cache.values() if v.get('lat') is not None)
                    pct = 100 * hits / len(cache) if cache else 0
                    print(f"  [{i:5d}/{len(to_do):5d}]  hits: {hits:5d} ({pct:5.1f}%)   "
                          f"last: {name[:38]:38s}  -> "
                          f"{'OK' if lat else 'miss'}")

                if i % SAVE_EVERY == 0:
                    save_cache(cache)

                time.sleep(RATE_LIMIT_SEC)
        except KeyboardInterrupt:
            print()
            print("Interrupted — saving cache before exit...")
            save_cache(cache)
            print(f"Saved {len(cache):,} entries. Re-run the script to resume.")
            sys.exit(0)

        save_cache(cache)
        print("-" * 70)
        print("Geocoding loop finished.")

    # ------------------------------------------------------------------------
    # Write final CSV
    # ------------------------------------------------------------------------
    print()
    print(f"Writing {OUTPUT_CSV}...")
    rows = []
    for _, r in unique_locs.iterrows():
        key = f"{r['LocationNumber']}|{r['Location']}"
        c = cache.get(key, {})
        rows.append({
            'LocationNumber': r['LocationNumber'],
            'Location': r['Location'],
            'Channel': r['Channel'],
            'lat': c.get('lat'),
            'lng': c.get('lng'),
            'geocoded': c.get('lat') is not None,
        })
    out = pd.DataFrame(rows)
    out.to_csv(OUTPUT_CSV, index=False)

    hits = int(out['geocoded'].sum())
    print()
    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"Total locations:  {len(out):,}")
    print(f"Successfully geocoded: {hits:,}  ({100 * hits / len(out):.1f}%)")
    print(f"Failed (will use synthetic fallback): {len(out) - hits:,}")
    print()
    print("By channel:")
    summary = out.groupby('Channel').agg(
        total=('geocoded', 'size'),
        geocoded=('geocoded', 'sum'),
    )
    summary['pct'] = (100 * summary['geocoded'] / summary['total']).round(1)
    print(summary.to_string())
    print()
    print(f"Done. The notebook will pick up {OUTPUT_CSV} automatically.")


if __name__ == "__main__":
    main()
