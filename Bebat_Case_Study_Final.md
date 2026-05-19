# Bebat Case Study — Strategic Fleet Planning for Remanufacturing

Supplementary code for the KU Leuven master thesis  
**"Strategic Fleet Planning for Remanufacturing: The Financial Impact of Autonomous Vehicle Flexibility"**  
Joppe Baert & Victor Rommel, 2025–2026

---

## What this notebook does

`Bebat_Case_StudyMSS.ipynb` implements a full strategic fleet-planning simulation for Bebat, the Belgian battery collection operator (~13,420 active collection points). It compares three vehicle technologies — internal combustion (ICEV), battery-electric (BEV), and autonomous electric (AV) — across a case ladder of eight operational scenarios, and reports fleet size, annualised total cost (EUAC), and CO₂ emissions for each.

The pipeline runs end-to-end in a single notebook:

| Stage | Cells | What happens |
|---|---|---|
| Data preparation | 6–16 | Load Bebat collection data, geocode locations, cluster into 50 zones and 5 regional hubs via K-means |
| Demand modelling | 17–26 | Extend historical demand with a growth rate, disaggregate into daily Poisson arrivals, generate 10 Monte Carlo traces over a 3-year horizon |
| Routing | 28–30 | Build tours with the Clarke–Wright savings algorithm; assign tours to vehicles with First-Fit-Decreasing (FFD) bin packing; enforce per-shift time limits |
| Fleet sizing | 30 | Choose $N_k = \max(N^\text{formula}, N^\text{packing})$ per scenario, taking the worst case across all Monte Carlo traces |
| Costing | 32–40 | Compute CAPEX (EUAC with optimal disposal point), energy, labour, maintenance, viapass tolls, and external CO₂ cost per scenario |
| Case ladder | 56–60 | Run eight cases (shuttle baseline, tight SLA, loose SLA + deferral, load-factor sensitivity, AV multi-depot, multi-shift ICEV/BEV, all-24h limit case) with result caching |
| Visualisation | 42–54, 58–62 | Cross-case bar charts, per-trace box plots, sensitivity sweeps, EUAC decomposition, tornado plots, illustrative tour map |

---

## Requirements

```
python >= 3.10
jupyter
numpy pandas matplotlib scikit-learn pypdf requests
```

An **OSRM** instance is required for road-network distances (default: `http://router.project-osrm.org`). Distances are cached locally after the first run so OSRM is only needed once.

---

## Data files

The following files must be present in the working directory:

| File | Description |
|---|---|
| `COLLECTION_DATA.xlsx` | Bebat collection point data (not included; sourced from Bebat) |
| `bebatlocations.csv` | Pre-geocoded collection point coordinates |
| `geocoded_cache_v2.json` | Nominatim geocoding cache (avoids re-querying the API) |

---

## Running the notebook

1. Clone the repository and install dependencies.
2. Place the data files listed above in the working directory.
3. Open `Bebat_Case_StudyMSS.ipynb` in Jupyter and **Run All**.

Cold runtime for the full case ladder (cells 56–60) is approximately 6–8 hours. Subsequent runs use the routing cache and complete in minutes. To force a full re-run, delete the `outputs/case_runs/` directory before running.

All results, figures, and CSVs are written to `outputs/`.

---

## Reproducibility

The master seed `MASTER_SEED = 20260503` is set in cell 2. All sub-seeds for Monte Carlo traces, K-means, and maintenance noise are derived deterministically from this value. The seed table is saved to `outputs/seeds.json` on every run.

---

## Key parameters

All modelling parameters are centralised in `CONFIG` (cell 4) and documented inline. Key values:

| Parameter | Value |
|---|---|
| Zones / hubs | 50 / 5 |
| Monte Carlo traces | 10 |
| Planning horizon | 3 years |
| Vehicle capacity | 7 200 kg |
| Load factor φ (baseline) | 0.75 |
| Average speed | 40 km/h |
| Utilisation η | 0.80 |
| Discount rate | 5 % |

---

## Structure

```
Bebat_Case_StudyMSS.ipynb   Main notebook (65 cells)
outputs/
  seeds.json                Master and derived seeds
  case_runs/                Per-case routing cache and result CSVs
  *.png                     Generated figures
```
