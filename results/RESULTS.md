# Results

Latest run: **2026-10-01 09:02 UTC**, using live CelesTrak data. Refreshed automatically every week by GitHub Actions.

| Measure | Value |
|---|---|
| Objects tracked | 18,645 |
| Debris fragments | 2,673 |
| Payloads | 15,967 |
| Rocket bodies | 5 |
| Share in low Earth orbit | 96% |
| ISS close approaches under 25 km (next 24 h) | 22 |
| Closest ISS approach | 9.16 km |

![Objects per altitude band](results/altitude_density.png)

**Breakup events in the catalogue**

| Breakup event | Fragments still tracked | Altitude range (km) | Avg inclination (°) |
|---|---|---|---|
| Fengyun-1C (2007 ASAT test) | 1978 | 305 – 3123 | 98.9 |
| Cosmos 2251 (2009 collision) | 582 | 278 – 1606 | 74.0 |
| Iridium 33 (2009 collision) | 109 | 476 – 1321 | 86.3 |
| Cosmos 1408 (2021 ASAT test) | 3 | 267 – 430 | 82.6 |

**DBSCAN breakup clustering** (the model is never told which event a fragment came from)

| Metric | Value |
|---|---|
| Fragments clustered | 2,672 |
| Clusters found / true events | 3 / 4 |
| Adjusted Rand index (1 = perfect) | 0.96 |
| Homogeneity | 0.98 |
| Completeness | 0.89 |
| Left as noise | 2% |

![DBSCAN clusters](results/debris_clusters.png)

**Which cluster matched which event**

| True event | cluster 0 | cluster 1 | cluster 2 | noise |
|---|---|---|---|---|
| Cosmos 1408 (2021 ASAT test) | 0 | 0 | 0 | 3 |
| Cosmos 2251 (2009 collision) | 0 | 574 | 0 | 8 |
| Fengyun-1C (2007 ASAT test) | 1948 | 0 | 0 | 30 |
| Iridium 33 (2009 collision) | 0 | 0 | 104 | 5 |

**Closest approaches to the ISS**

| Closest approach | Object | Type | Miss (km) | Rel. speed (km/s) | Risk |
|---|---|---|---|---|---|
| 01 Oct 09:07 UTC | FLOCK 4BE-13 | PAYLOAD | 9.16 | 13.8 | LOW |
| 01 Oct 16:44 UTC | STARLINK-1183 | PAYLOAD | 10.07 | 11.25 | LOW |
| 01 Oct 16:52 UTC | FLOCK 4BE-9 | PAYLOAD | 11.94 | 13.72 | LOW |
| 01 Oct 21:31 UTC | CONNECTA IOT-4 | PAYLOAD | 11.98 | 13.66 | LOW |
| 01 Oct 20:40 UTC | STARLINK-30806 | PAYLOAD | 13.54 | 7.65 | LOW |

Full list: [results/iss_close_approaches.csv](results/iss_close_approaches.csv)
