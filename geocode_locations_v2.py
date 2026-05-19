"""
geocode_locations_v2.py
=======================
SECOND-PASS geocoder for locations that v1 (geocode_locations.py) failed to find.

Strategy: many Bebat location names contain a Belgian town somewhere in the
string. v1 sent the whole name to Nominatim as a single query, which often
fails for small businesses. v2 tries progressively shorter substrings (last
word, last two words, last three words) until Nominatim returns a hit that
sits inside Belgium.

WHAT YOU GET
------------
Each recovered location gets the **town centroid** as its (lat, lng), accurate
to ~3-5 km of the actual address. This is more than enough for zone-level
fleet sizing (50 zones across Belgium, ~25 km per zone), but it is NOT
suitable for street-level routing.

USAGE
-----
    # First make sure v1 has run and produced geocoded_cache.json:
    python geocode_locations.py
    # Then run v2 to retry the misses:
    python geocode_locations_v2.py

  - Reads ONLY locations that v1 failed to find (~7,300 entries).
  - Takes about 2-3 hours (Nominatim 1 req/sec, plus 1-3 fallback queries each).
  - You can interrupt at any time (Ctrl+C) — progress is saved every 50 lookups.
  - Restart and it resumes from the v2 cache automatically.
  - Writes `locations_geocoded_v2.csv` with the EXTRA hits, plus updates the
    existing `locations_geocoded.csv` so the notebook picks both up.

REQUIREMENTS
------------
    pip install pandas openpyxl
    (no API key needed — Nominatim is free)

NOMINATIM USAGE POLICY
----------------------
This script is fully compliant with the Nominatim usage policy:
  * Identifies itself with a User-Agent (edit USER_AGENT below).
  * Throttles to <1 request/second.
  * Caches every result so we never re-query.
"""

import json
import re
import sys
import time
import urllib.parse
import urllib.request
import urllib.error
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd

# -----------------------------------------------------------------------------
# Configuration
# -----------------------------------------------------------------------------
EXCEL_PATH         = Path("COLLECTION_DATA.xlsx")
CACHE_V1           = Path("geocoded_cache.json")          # produced by v1
CACHE_V2           = Path("geocoded_cache_v2.json")       # built here
OUTPUT_V2_CSV      = Path("locations_geocoded_v2.csv")    # extra hits only
OUTPUT_COMBINED    = Path("locations_geocoded.csv")       # what the notebook reads (UPDATED IN PLACE)

# IMPORTANT: edit USER_AGENT to include your real email — Nominatim policy.
USER_AGENT = (
    "BebatThesisGeocoderV2/1.0 "
    "(KU Leuven Master Thesis; contact: victor.rommel10@gmail.com)"
)

NOMINATIM_URL  = "https://nominatim.openstreetmap.org/search"
RATE_LIMIT_SEC = 1.1
SAVE_EVERY     = 50
TIMEOUT_SEC    = 15

# Acceptable Belgium bounding-box for sanity-checking returned coordinates
BE_LAT_MIN, BE_LAT_MAX = 49.4, 51.6
BE_LON_MIN, BE_LON_MAX = 2.4, 6.5

# Words we strip out of business names before splitting (these are never towns)
BUSINESS_STOPWORDS = {
    # legal / company suffixes
    "SA", "S.A", "S.A.", "NV", "N.V", "N.V.", "BV", "B.V", "B.V.", "BVBA", "B.V.B.A.",
    "SPRL", "S.P.R.L", "VOF", "V.O.F", "ASBL", "A.S.B.L", "VZW", "V.Z.W",
    "GMBH", "INC", "LTD", "LLC", "S.A.E", "SCS", "SCRL", "S.C.R.L", "SE",
    # connectors
    "AND", "EN", "ET", "VAN", "DE", "DER", "DU", "LA", "LE", "LES", "DES", "AU", "AUX", "VAN",
    "&", "+", "/", "&CO", "C°",
    # generic business descriptors
    "BVBA", "INDUSTRIES", "INDUSTRIAL", "PRODUCTS", "SERVICES", "GROUP", "GROUPE",
    "INTERNATIONAL", "CORPORATION", "TECHNOLOGIES", "BELGIUM", "BELGIE", "BELGIQUE",
    "WERKEN", "EIGEN", "BEHEER", "IN", "OP", "OF", "ON", "FOR", "VOOR", "POUR",
    # common school / institution words
    "BASISSCHOOL", "BASISONDERWIJS", "KLEUTERSCHOOL", "LAGERE", "LAG", "VRIJE",
    "ECOLE", "COMMUNAL", "COMMUNALE", "PRIMAIRE", "FONDAMENTALE", "PRIM",
    "SCHOOL", "STEDELIJKE", "GBS", "VBS", "CENTRE", "SCOLAIRE", "INSTITUUT",
    "MIDDENSCHOOL", "KATHOLIEK", "BUITENGEWOON", "ONDERWIJS", "ETABLISSEMENT",
    "ENSEIGNEMENT", "SPECIAL",
    # common retail / company prefixes
    "DRUKKERIJ", "MAISON", "LIBRAIRIE", "EXELLENT", "FOTO", "MEGA", "GSM",
    "PLANET", "POLITIEZONE", "STAD", "ATELIERS", "VILLE", "CLINIQUE", "ZIEKENHUIS",
    "PSYCHIATRISCH", "BROEDERS", "TELECOM", "GRAPHICS", "QUALITY", "ASSISTANCE",
    "MOTORS", "ELECTRABEL", "KERNCENTRALE",
    # recycling-park prefixes
    "RP", "RECYCLAGEPARK", "RECYCLAGE", "PARC",
    # number-only tokens
    "1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "I", "II", "III", "IV", "V",
}

# Common Belgian compound town names (multi-word) we want to recognise as ONE
# unit. Sub-municipalities and well-known compound towns. Stored as
# tuples-of-tokens; matching is greedy from the longest possible match downwards.
COMPOUND_TOWNS = {
    # Brussels-Capital region
    ("SINT", "PIETERS", "WOLUWE"): "Sint-Pieters-Woluwe",
    ("SAINT", "PIERRE", "WOLUWE"): "Woluwe-Saint-Pierre",
    ("WOLUWE", "ST", "PIERRE"): "Woluwe-Saint-Pierre",
    ("WOLUWE", "SAINT", "PIERRE"): "Woluwe-Saint-Pierre",
    ("WOLUWE", "ST", "LAMBERT"): "Woluwe-Saint-Lambert",
    ("WOLUWE", "SAINT", "LAMBERT"): "Woluwe-Saint-Lambert",
    ("SINT", "LAMBRECHTS", "WOLUWE"): "Sint-Lambrechts-Woluwe",
    ("SINT", "STEVENS", "WOLUWE"): "Sint-Stevens-Woluwe",
    ("WATERMAEL", "BOITSFORT"): "Watermael-Boitsfort",
    ("BERCHEM", "STE", "AGATHE"): "Berchem-Sainte-Agathe",
    ("SINT", "AGATHA", "BERCHEM"): "Sint-Agatha-Berchem",
    ("SINT", "GENESIUS", "RODE"): "Sint-Genesius-Rode",
    ("RHODE", "SAINT", "GENESE"): "Rhode-Saint-Genèse",
    ("KOEKELBERG",): "Koekelberg",
    # Common composite municipalities
    ("SINT", "PIETERS", "LEEUW"): "Sint-Pieters-Leeuw",
    ("SINT", "NIKLAAS",): "Sint-Niklaas",
    ("SINT", "TRUIDEN"): "Sint-Truiden",
    ("SINT", "GILLIS", "WAAS"): "Sint-Gillis-Waas",
    ("SAINT", "GHISLAIN"): "Saint-Ghislain",
    ("FONTAINE", "L", "EVEQUE"): "Fontaine-l'Évêque",
    ("FONTAINE", "L'EVEQUE"): "Fontaine-l'Évêque",
    ("LA", "LOUVIERE"): "La Louvière",
    ("LA", "HULPE"): "La Hulpe",
    ("LA", "ROCHE", "EN", "ARDENNE"): "La Roche-en-Ardenne",
    ("MARCHE", "EN", "FAMENNE"): "Marche-en-Famenne",
    ("BRAINE", "L", "ALLEUD"): "Braine-l'Alleud",
    ("BRAINE", "LE", "COMTE"): "Braine-le-Comte",
    ("OTTIGNIES", "LOUVAIN", "LA", "NEUVE"): "Ottignies-Louvain-la-Neuve",
    ("LOUVAIN", "LA", "NEUVE"): "Louvain-la-Neuve",
    ("MONT", "SAINT", "GUIBERT"): "Mont-Saint-Guibert",
    ("MONT", "SUR", "MARCHIENNE"): "Mont-sur-Marchienne",
    ("CHAUMONT", "GISTOUX"): "Chaumont-Gistoux",
    ("GREZ", "DOICEAU"): "Grez-Doiceau",
    ("LA", "PANNE",): "De Panne",
    ("DE", "PANNE"): "De Panne",
    ("MOORSLEDE", "DADIZELE"): "Dadizele",   # take second token as primary
    ("OUD", "TURNHOUT"): "Oud-Turnhout",
    ("OUD", "HEVERLEE"): "Oud-Heverlee",
    ("HOEILAART",): "Hoeilaart",
    ("HEUSDEN", "ZOLDER"): "Heusden-Zolder",
    ("BEVERLO",): "Beveren",
    ("HOUTHALEN", "HELCHTEREN"): "Houthalen-Helchteren",
    ("LO", "RENINGE"): "Lo-Reninge",
    ("KAPELLE", "OP", "DEN", "BOS"): "Kapelle-op-den-Bos",
    ("BAVIKHOVE",): "Bavikhove",
    # Compound towns we picked up from the user's failed list
    ("HEINSTERT", "LISCHERT", "NOBRESSART"): "Léglise",
    ("BOUILLON", "MENUCHENET"): "Bouillon",
    ("CHAMPION",): "Namur",     # Champion is a sub-area of Namur
}

# -----------------------------------------------------------------------------

def load_cache(path: Path) -> dict:
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_cache(path: Path, cache: dict) -> None:
    tmp = path.with_suffix(".json.tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=1)
    tmp.replace(path)


def in_belgium(lat: float, lon: float) -> bool:
    return BE_LAT_MIN <= lat <= BE_LAT_MAX and BE_LON_MIN <= lon <= BE_LON_MAX


def nominatim_query(query: str) -> tuple:
    """One Nominatim call. Returns (lat, lon) or (None, None)."""
    params = {
        "q": query,
        "format": "json",
        "limit": 1,
        "countrycodes": "be",
    }
    url = f"{NOMINATIM_URL}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_SEC) as resp:
            data = json.loads(resp.read())
            if data:
                lat, lon = float(data[0]["lat"]), float(data[0]["lon"])
                if in_belgium(lat, lon):
                    return lat, lon
    except urllib.error.HTTPError as e:
        if e.code == 429:
            print("    HTTP 429 (rate limit) — sleeping 60s")
            time.sleep(60)
        else:
            print(f"    HTTP {e.code}")
    except (urllib.error.URLError, json.JSONDecodeError, TimeoutError, ValueError) as e:
        print(f"    {type(e).__name__}: {e}")
    return None, None


# -----------------------------------------------------------------------------
# Token extraction
# -----------------------------------------------------------------------------
def tokenize(name: str) -> list:
    """Strip punctuation, uppercase, split into word tokens."""
    cleaned = re.sub(r"[^A-Za-zÀ-ÿ\s'-]", " ", name)
    cleaned = cleaned.replace("'", " ").replace("-", " ")
    return [t for t in cleaned.upper().split() if t]


def candidate_queries(name: str) -> list:
    """Return a list of candidate town queries to try, in priority order.

    Order:
      1. Compound-town matches (e.g. WOLUWE ST PIERRE, SINT LAMBRECHTS WOLUWE).
         Run on raw tokens BEFORE stopword filtering, so single-letter linkers
         like 'L' in FONTAINE L EVEQUE are visible to the matcher.
      2. Last-N tokens (after stopword filter), n=3 → 2 → 1.
    """
    raw = tokenize(name)        # all word tokens, length>=1, uppercase preserved
    if not raw:
        return []

    queries = []

    # 1) Compound matches against RAW tokens.
    raw_upper = [t.upper() for t in raw]
    for pattern, town in COMPOUND_TOWNS.items():
        n = len(pattern)
        for i in range(len(raw_upper) - n + 1):
            if tuple(raw_upper[i:i + n]) == pattern:
                q = f"{town}, Belgium"
                if q not in queries:
                    queries.append(q)
                break  # one match per pattern is enough

    # 2) Last-N candidates after stopword filtering.
    meaningful = [t for t in raw if t.upper() not in BUSINESS_STOPWORDS and len(t) > 1]
    for n in (3, 2, 1):
        if len(meaningful) >= n:
            tail = " ".join(meaningful[-n:])
            q = f"{tail.title()}, Belgium"
            if q not in queries:
                queries.append(q)

    return queries


# -----------------------------------------------------------------------------
# Main
# -----------------------------------------------------------------------------

def main():
    if not EXCEL_PATH.exists():
        print(f"ERROR: {EXCEL_PATH} not found.")
        sys.exit(1)
    if not CACHE_V1.exists():
        print(f"ERROR: {CACHE_V1} not found.")
        print(f"Run `python geocode_locations.py` first to produce v1 results.")
        sys.exit(1)

    print("=" * 70)
    print("Bebat location geocoder v2 — town-centroid second pass")
    print("=" * 70)
    print(f"Excel:          {EXCEL_PATH}")
    print(f"v1 cache:       {CACHE_V1}")
    print(f"v2 cache:       {CACHE_V2}")
    print(f"Final CSV:      {OUTPUT_COMBINED}")
    print(f"User-Agent:     {USER_AGENT}")
    print()

    if "your.email" in USER_AGENT.lower():
        print("⚠  Edit USER_AGENT at the top of this file to include your real email.")
        print()

    # Load v1 cache
    v1 = load_cache(CACHE_V1)
    v1_hits   = {k: v for k, v in v1.items() if v.get("lat") is not None}
    v1_misses = {k: v for k, v in v1.items() if v.get("lat") is None}
    print(f"v1 cache:   {len(v1):,} total — {len(v1_hits):,} hits, {len(v1_misses):,} misses")

    # Load v2 cache (resumability)
    v2 = load_cache(CACHE_V2)
    print(f"v2 cache:   {len(v2):,} entries already done")

    todo = [(k, v) for k, v in v1_misses.items() if k not in v2]
    print(f"To process: {len(todo):,} remaining\n")

    if todo:
        eta_sec = len(todo) * RATE_LIMIT_SEC * 1.5  # ~1.5 queries per location on average
        eta = datetime.now() + timedelta(seconds=eta_sec)
        print(f"Estimated time: {eta_sec / 3600:.1f} hours")
        print(f"Estimated finish: {eta.strftime('%Y-%m-%d %H:%M')}")
        print()
        print("Starting town-centroid loop. Press Ctrl+C to stop — progress is saved.")
        print("-" * 70)

        try:
            for i, (key, v1_entry) in enumerate(todo, 1):
                name = v1_entry.get("name") or v1_entry.get("location") or ""
                qs = candidate_queries(name)
                hit_lat, hit_lon, used_q = None, None, None
                for q in qs:
                    lat, lon = nominatim_query(q)
                    time.sleep(RATE_LIMIT_SEC)
                    if lat is not None:
                        hit_lat, hit_lon, used_q = lat, lon, q
                        break

                v2[key] = {
                    "lat": hit_lat,
                    "lng": hit_lon,
                    "queries_tried": qs,
                    "query_succeeded": used_q,
                    "channel": v1_entry.get("channel"),
                    "name": name,
                    "method": "town_centroid",
                }

                if i % 25 == 0 or i == len(todo):
                    new_hits = sum(1 for v in v2.values() if v.get("lat") is not None)
                    pct = 100 * new_hits / len(v2) if v2 else 0
                    status = f"OK ({used_q})" if used_q else "miss"
                    print(f"  [{i:5d}/{len(todo):5d}]  v2 hits: {new_hits:5d} ({pct:5.1f}%)  "
                          f"last: {name[:36]:36s} -> {status}")

                if i % SAVE_EVERY == 0:
                    save_cache(CACHE_V2, v2)
        except KeyboardInterrupt:
            print("\nInterrupted — saving v2 cache.")
            save_cache(CACHE_V2, v2)
            print(f"Saved {len(v2):,} entries. Re-run to resume.")
            sys.exit(0)

        save_cache(CACHE_V2, v2)
        print("-" * 70)
        print("v2 loop finished.")

    # ------------------------------------------------------------------------
    # Build the final combined CSV
    # ------------------------------------------------------------------------
    print()
    print("Building combined output CSV...")

    # Re-read the Excel to get LocationNumber + Channel + Location for every row
    raw = pd.read_excel(EXCEL_PATH, sheet_name="Sheet0", header=None)
    col_names = ["Channel", "LocationNumber", "Location"] + [f"col{i}" for i in range(raw.shape[1] - 3)]
    df = raw.iloc[3:].copy()
    df.columns = col_names
    df = df.dropna(subset=["Channel", "Location", "LocationNumber"]).reset_index(drop=True)
    unique_locs = df[["Channel", "LocationNumber", "Location"]].drop_duplicates().reset_index(drop=True)

    rows = []
    for _, r in unique_locs.iterrows():
        key = f"{r['LocationNumber']}|{r['Location']}"
        # Priority: v1 hit > v2 hit > miss
        v1_entry = v1_hits.get(key)
        v2_entry = v2.get(key, {}) if v2.get(key, {}).get("lat") is not None else None
        if v1_entry:
            lat, lng, source = v1_entry["lat"], v1_entry["lng"], "nominatim_exact"
        elif v2_entry:
            lat, lng, source = v2_entry["lat"], v2_entry["lng"], "nominatim_town"
        else:
            lat, lng, source = None, None, ""
        rows.append({
            "LocationNumber": r["LocationNumber"],
            "Location":       r["Location"],
            "Channel":        r["Channel"],
            "lat":            lat,
            "lng":            lng,
            "geocoded":       lat is not None,
            "geocode_source": source,
        })
    out = pd.DataFrame(rows)
    out.to_csv(OUTPUT_COMBINED, index=False)
    print(f"  Wrote {OUTPUT_COMBINED} ({len(out):,} rows)")

    # Also write v2-only output for inspection
    v2_only = out[out["geocode_source"] == "nominatim_town"]
    v2_only.to_csv(OUTPUT_V2_CSV, index=False)
    print(f"  Wrote {OUTPUT_V2_CSV} ({len(v2_only):,} extra hits)")

    # Final summary
    n_total   = len(out)
    n_exact   = (out["geocode_source"] == "nominatim_exact").sum()
    n_town    = (out["geocode_source"] == "nominatim_town").sum()
    n_missing = (~out["geocoded"]).sum()
    print()
    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"Total locations:         {n_total:,}")
    print(f"  v1 exact hits:         {n_exact:,}  ({100 * n_exact / n_total:.1f}%)")
    print(f"  v2 town-centroid hits: {n_town:,}  ({100 * n_town / n_total:.1f}%)  ← NEW")
    print(f"  Still missing:         {n_missing:,}  ({100 * n_missing / n_total:.1f}%)")
    print()
    print("By channel:")
    summary = (
        out.assign(
            exact = lambda d: (d["geocode_source"] == "nominatim_exact").astype(int),
            town  = lambda d: (d["geocode_source"] == "nominatim_town").astype(int),
            miss  = lambda d: (~d["geocoded"]).astype(int),
        )
        .groupby("Channel")[["exact", "town", "miss"]]
        .sum()
    )
    summary["total"]    = summary.sum(axis=1)
    summary["exact_%"]  = (100 * summary["exact"]  / summary["total"]).round(1)
    summary["town_%"]   = (100 * summary["town"]   / summary["total"]).round(1)
    summary["miss_%"]   = (100 * summary["miss"]   / summary["total"]).round(1)
    print(summary[["exact", "town", "miss", "total", "exact_%", "town_%", "miss_%"]].to_string())
    print()
    print(f"Done. The notebook will pick up {OUTPUT_COMBINED} automatically.")


if __name__ == "__main__":
    main()
