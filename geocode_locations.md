# Geocoding Pipeline

Converts raw Bebat collection point names and addresses into coordinates (lat/lng) for use in the case study notebook.

---

## Files

| File | Description |
|---|---|
| `bebat-locations.csv` | Raw export from Bebat: 5,675 locations with name, city, and a pre-existing lat/lng from Bebat's own system |
| `geocode_locations.py` | First-pass geocoder — queries Nominatim (OpenStreetMap) with the full location name, caches every result |
| `geocoded_cache.json` | Cache of all 13,637 Nominatim responses from the first pass (keyed by `LocationNumber\|LocationName`) |
| `locations_geocoded.csv` | Output of the first pass: 13,637 locations with lat/lng, a `geocoded` boolean flag, and the source method |
| `geocode_locations_v2.py` | Second-pass geocoder — recovers locations that the first pass failed on by progressively shortening the query to the town name |
| `geocoded_cache_v2.json` | Cache of 7,343 Nominatim responses from the second pass; each entry records which query variant succeeded |
| `locations_geocoded_v2.csv` | Output of the second pass: 6,441 previously-unmatched locations, resolved to town-centroid accuracy (~3–5 km) |

---

## How the pipeline works

**Pass 1 — exact name lookup** (`geocode_locations.py`)

Reads `COLLECTION_DATA.xlsx`, sends each location's full name to Nominatim biased to Belgium, and writes results to `locations_geocoded.csv`. Every API response is cached in `geocoded_cache.json` so the geocoder only contacts Nominatim once per location; re-running the script without deleting the cache is safe and fast.

**Pass 2 — town-centroid fallback** (`geocode_locations_v2.py`)

Many Bebat location names (e.g. `EXELLENT DEBRIGODE ELECTRO`) are small businesses that Nominatim cannot find by full name. The second pass tries progressively shorter substrings of the name (last word, last two words, last three words) until it finds a hit inside Belgium. The recovered coordinate is the town centroid rather than the exact address, which is accurate enough for the 50-zone clustering in the case study. Results are cached in `geocoded_cache_v2.json`.

**In the notebook**

Cells 8–9 of `Bebat_Case_StudyMSS.ipynb` run this waterfall: first the Bebat-supplied coordinates are used where available, then `locations_geocoded.csv` (exact Nominatim), then `locations_geocoded_v2.csv` (town centroid), with a synthetic Belgium-bounding-box fallback for any remaining misses.

---

## Running the geocoders

The cache files are included in the repository, so you do **not** need to re-run the geocoders to use the notebook. Run them only if you want to update the location data:

```bash
python geocode_locations.py       # first pass — may take several hours
python geocode_locations_v2.py    # second pass — runs on first-pass failures only
```

Nominatim's usage policy requires a maximum of one request per second; both scripts enforce this automatically.
