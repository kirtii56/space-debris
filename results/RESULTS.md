# Results

Latest run: **2026-10-12 11:15 UTC**, using live CelesTrak data. Refreshed automatically every week by GitHub Actions.

| Measure | Value |
|---|---|
| Objects tracked | 18,618 |
| Debris fragments | 2,675 |
| Payloads | 15,938 |
| Rocket bodies | 5 |
| Share in low Earth orbit | 96% |
| ISS close approaches under 25 km (next 24 h) | 14 |
| Closest ISS approach | 6.9 km |

![Objects per altitude band](results/altitude_density.png)

**Breakup events in the catalogue**

| Breakup event | Fragments still tracked | Altitude range (km) | Avg inclination (°) |
|---|---|---|---|
| Fengyun-1C (2007 ASAT test) | 1976 | 301 – 3132 | 98.9 |
| Cosmos 2251 (2009 collision) | 587 | 266 – 1606 | 74.0 |
| Iridium 33 (2009 collision) | 108 | 472 – 1320 | 86.3 |
| Cosmos 1408 (2021 ASAT test) | 3 | 254 – 431 | 82.6 |

**DBSCAN breakup clustering** (the model is never told which event a fragment came from)

| Metric | Value |
|---|---|
| Fragments clustered | 2,674 |
| Clusters found / true events | 3 / 4 |
| Adjusted Rand index (1 = perfect) | 0.96 |
| Homogeneity | 0.97 |
| Completeness | 0.89 |
| Left as noise | 2% |

![DBSCAN clusters](results/debris_clusters.png)

**Which cluster matched which event**

| True event | cluster 0 | cluster 1 | cluster 2 | noise |
|---|---|---|---|---|
| Cosmos 1408 (2021 ASAT test) | 0 | 0 | 0 | 3 |
| Cosmos 2251 (2009 collision) | 0 | 578 | 0 | 9 |
| Fengyun-1C (2007 ASAT test) | 1946 | 0 | 0 | 30 |
| Iridium 33 (2009 collision) | 0 | 0 | 103 | 5 |

**Closest approaches to the ISS**

| Closest approach | Object | Type | Miss (km) | Rel. speed (km/s) | Risk |
|---|---|---|---|---|---|
| 13 Oct 09:12 UTC | STARLINK-1271 | PAYLOAD | 6.9 | 0.79 | LOW |
| 12 Oct 13:31 UTC | 2025-155K | PAYLOAD | 8.42 | 14.76 | LOW |
| 12 Oct 12:44 UTC | 2025-155K | PAYLOAD | 10.34 | 14.76 | LOW |
| 13 Oct 02:27 UTC | SHIYAN-32 02 | PAYLOAD | 12.22 | 9.16 | LOW |
| 12 Oct 14:46 UTC | FLOCK 4BE-18 | PAYLOAD | 12.36 | 9.62 | LOW |

Full list: [results/iss_close_approaches.csv](results/iss_close_approaches.csv)
