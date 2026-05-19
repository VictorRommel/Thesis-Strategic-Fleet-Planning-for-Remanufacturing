# Thesis – Strategic Fleet Planning for Remanufacturing

## Overview

In an era of increasing environmental pressure and resource scarcity, the transition toward a circular economy has become essential. Remanufacturing plays a pivotal role in this transition by restoring used products to a like-new condition, significantly reducing raw material consumption and CO2 emissions.

However, the primary barrier to scaling these operations is the inherent complexity of reverse logistics. Unlike forward supply chains, return flows are characterized by high levels of uncertainty regarding timing, quantity, and location.

This thesis investigates how the emergence of Level 4 autonomous vehicles (AVs) can provide a solution through enhanced operational flexibility.

### Research Question

> To what extent does the flexibility of autonomous vehicles influence the financial viability of a remanufacturing network under stochastic conditions?

---

## Methodology

To facilitate a scientifically grounded comparison, an integrated framework was developed to bridge the gap between raw historical data and strategic fleet planning.

The methodology consists of the following components:

- **Demand Reconstruction**  
  Monthly collection data are disaggregated into daily requests using a Poisson process to simulate realistic peak loads.

- **Stochasticity**  
  A Monte Carlo simulation is employed to generate ten independent three-year traces, testing fleet resilience against demand volatility.

- **Technological Comparison**  
  Three fleet scenarios are modeled based on the IVECO Daily platform:
  
  - Diesel baseline (**ICEV**)
  - Electric variant (**BEV**)
  - Autonomous variant (**AV**)

  For the AV scenario, a paradigm shift is modeled where the removal of human driving and rest-time regulations enables 24/7 operations.

---

## Economic Analysis

The economic analysis adopts a **Total Cost of Ownership (TCO)** perspective, utilizing the **Equivalent Uniform Annual Cost (EUAC)** as the primary decision metric.

This approach internalizes:

- Internal costs (**CAPEX/OPEX**)
- External environmental costs through a **Well-to-Wheel** boundary

---

## Case Study

The methodology was validated through a case study of the Belgian collection network of **Bebat**, comprising **13,637 unique collection points**.

Two growth forecasts were applied:

| Scenario | Growth Assumption |
|---|---|
| Scenario A | 2.83% growth |
| Scenario B | 4.21% structural trend growth |

The financial modeling incorporates:

- A Belgian wage multiplier of **1.7**
- Technological premiums for autonomous systems

---

## Key Findings

The research identifies the economic **tipping point** where the higher capital expenditures of autonomous and electric fleets are offset by:

- Lower variable costs
- Increased asset utilization

The results demonstrate that the flexibility provided by autonomous vehicles (**operational smoothing**) is crucial for ensuring the financial viability of large-scale remanufacturing networks under uncertain market conditions.

---

## Keywords

`Remanufacturing` `Autonomous Vehicles` `Reverse Logistics` `Circular Economy` `Fleet Planning` `Monte Carlo Simulation` `TCO` `EUAC`
