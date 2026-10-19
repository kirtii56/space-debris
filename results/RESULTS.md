# Results

Latest run: **2026-10-19 09:14 UTC**, using live CelesTrak data. Refreshed automatically every week by GitHub Actions.

| Measure | Value |
|---|---|
| Objects tracked | 18,606 |
| Debris fragments | 2,675 |
| Payloads | 15,926 |
| Rocket bodies | 5 |
| Share in low Earth orbit | 96% |
| ISS close approaches under 25 km (next 24 h) | 30 |
| Closest ISS approach | 0.0 km |

![Objects per altitude band](results/altitude_density.png)

**Breakup events in the catalogue**

| Breakup event | Fragments still tracked | Altitude range (km) | Avg inclination (°) |
|---|---|---|---|
| Fengyun-1C (2007 ASAT test) | 1978 | 299 – 3136 | 98.9 |
| Cosmos 2251 (2009 collision) | 585 | 325 – 1606 | 74.0 |
| Iridium 33 (2009 collision) | 108 | 469 – 1319 | 86.3 |
| Cosmos 1408 (2021 ASAT test) | 3 | 241 – 431 | 82.6 |

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
| Cosmos 2251 (2009 collision) | 0 | 578 | 0 | 7 |
| Fengyun-1C (2007 ASAT test) | 1946 | 0 | 0 | 32 |
| Iridium 33 (2009 collision) | 0 | 0 | 99 | 9 |

**Closest approaches to the ISS**

| Closest approach | Object | Type | Miss (km) | Rel. speed (km/s) | Risk |
|---|---|---|---|---|---|
| 19 Oct 13:55 UTC | PROGRESS-MS 34 | PAYLOAD | 0.0 | 0.0 | HIGH |
| 19 Oct 10:03 UTC | PROGRESS-MS 34 | PAYLOAD | 0.01 | 0.0 | HIGH |
| 19 Oct 12:22 UTC | PROGRESS-MS 34 | PAYLOAD | 0.01 | 0.0 | HIGH |
| 19 Oct 11:35 UTC | PROGRESS-MS 34 | PAYLOAD | 0.01 | 0.0 | HIGH |
| 19 Oct 15:28 UTC | PROGRESS-MS 34 | PAYLOAD | 0.02 | 0.0 | HIGH |

Full list: [results/iss_close_approaches.csv](results/iss_close_approaches.csv)
