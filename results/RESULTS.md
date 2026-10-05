# Results

Latest run: **2026-10-05 10:47 UTC**, using live CelesTrak data. Refreshed automatically every week by GitHub Actions.

| Measure | Value |
|---|---|
| Objects tracked | 18,641 |
| Debris fragments | 2,679 |
| Payloads | 15,957 |
| Rocket bodies | 5 |
| Share in low Earth orbit | 96% |
| ISS close approaches under 25 km (next 24 h) | 15 |
| Closest ISS approach | 3.43 km |

![Objects per altitude band](results/altitude_density.png)

**Breakup events in the catalogue**

| Breakup event | Fragments still tracked | Altitude range (km) | Avg inclination (°) |
|---|---|---|---|
| Fengyun-1C (2007 ASAT test) | 1981 | 304 – 3124 | 98.9 |
| Cosmos 2251 (2009 collision) | 585 | 266 – 1606 | 74.0 |
| Iridium 33 (2009 collision) | 109 | 476 – 1320 | 86.3 |
| Cosmos 1408 (2021 ASAT test) | 3 | 263 – 431 | 82.6 |

**DBSCAN breakup clustering** (the model is never told which event a fragment came from)

| Metric | Value |
|---|---|
| Fragments clustered | 2,678 |
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
| Cosmos 2251 (2009 collision) | 0 | 577 | 0 | 8 |
| Fengyun-1C (2007 ASAT test) | 1951 | 0 | 0 | 30 |
| Iridium 33 (2009 collision) | 0 | 0 | 104 | 5 |

**Closest approaches to the ISS**

| Closest approach | Object | Type | Miss (km) | Rel. speed (km/s) | Risk |
|---|---|---|---|---|---|
| 05 Oct 11:22 UTC | POLYTECH UNIVERSE-4 | PAYLOAD | 3.43 | 7.4 | LOW |
| 06 Oct 05:12 UTC | STARLINK-30806 | PAYLOAD | 4.03 | 7.91 | LOW |
| 06 Oct 10:37 UTC | STARLINK-30806 | PAYLOAD | 9.79 | 7.93 | LOW |
| 06 Oct 03:39 UTC | STARLINK-30806 | PAYLOAD | 10.69 | 7.91 | LOW |
| 05 Oct 12:09 UTC | POLYTECH UNIVERSE-4 | PAYLOAD | 13.47 | 7.41 | LOW |

Full list: [results/iss_close_approaches.csv](results/iss_close_approaches.csv)
