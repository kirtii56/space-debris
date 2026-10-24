# Space operations findings (one day of public data)

Four small questions answered with the CelesTrak catalogue of **24 Oct 2026** and this
project's own TLE parser, SGP4 propagator and conjunction screen.
Window: 24 hours from 24 Oct 2026 14:00 UTC.

Run it: `python -m findings.space_ops` (from the repo root).
Outputs: [summary.json](summary.json), [eo_close_passes.csv](eo_close_passes.csv),
[starlink_sample_close_approaches.csv](starlink_sample_close_approaches.csv).

## 1. How many chances does an Earth-observation satellite get to photograph another satellite?

Passes within **50 km** of another active satellite (debris excluded) in 24 hours.

| Host satellite | Passes < 50 km | Different satellites | Slow passes (< 3 km/s) |
|---|---|---|---|
| WorldView-3 | 176 | 71 | 6 |
| Pléiades Neo 3 | 115 | 43 | 3 |
| Sentinel-2B | 23 | 10 | 2 |
| Landsat 8 | 14 | 9 | 2 |
| Sentinel-2A | 11 | 7 | 2 |
| Landsat 9 | 8 | 6 | 0 |

Satellites at ~620 km (WorldView-3, Pléiades Neo) sit just above the busiest shells and get
far more chances than those at ~700–790 km. Slow passes are rare, and they are the ones
that give a sharp image.

## 2. How much of the day can those satellites talk to the ground?

Five large ground-station sites (Svalbard, Troll, Kiruna, Fairbanks, Hartebeesthoek),
5° minimum elevation.

| Satellite | Share of day in contact | Longest gap |
|---|---|---|
| Sentinel-2B | 29% | 87 min |
| Sentinel-2A | 29% | 87 min |
| Landsat 9 | 27% | 86 min |
| Landsat 8 | 26% | 86 min |
| Pléiades Neo 3 | 24% | 86 min |
| WorldView-3 | 24% | 86 min |

Even with some of the best-placed stations on Earth, these satellites are unreachable for
roughly three quarters of the day.

## 3. How many close passes happen while nobody on the ground can act?

Across the six satellites, **263 of 347** close passes (76%) happen out of contact.
For WorldView-3 it is **146 of 176** (83%), including its closest pass of the day (7 km).

## 4. How busy is a mega-constellation?

A random sample of **100 of 10,642** Starlink satellites, each screened against the active
catalogue for approaches under **5 km** (formation flying under 0.5 km/s excluded).

| Measure | Value |
|---|---|
| Approaches under 5 km (100 satellites, 24 h) | 929 |
| Per satellite per day | ~9 |
| Satellites with at least one | 91 of 100 |
| Share with another Starlink satellite | 90% |
| Approaches under 1 km | 33 |

Most close approaches in a mega-constellation are with its own satellites, and almost every
satellite has several a day. Screening them one by one from the ground does not scale.

## 5. Where do active satellites fly? (space weather exposure)

Script: [sky_and_drag.py](sky_and_drag.py). Active satellites in low Earth orbit by mean altitude.

| Altitude band | Satellites | Of which Starlink |
|---|---|---|
| below 400 km | 976 | 809 |
| 400–450 km | 470 | 252 |
| 450–500 km | 9,787 | 9,178 |
| 500–550 km | 796 | 212 |
| 550–600 km | 667 | 191 |
| 600–2,000 km | 2,414 | 0 |

Nearly two thirds of all active LEO satellites now sit in one 50 km band (450–500 km), and
almost 1,000 fly below 400 km, where a geomagnetic storm raises drag the most.

## 6. How crowded is the sky above one site?

24 hours from 24 Oct 2026 00:00 UTC, 1-minute steps, all 15,908 active satellites.
"Observable" = above the elevation mask, sunlit, while the site is in astronomical darkness.

| Site (mask) | Above mask at once (avg / max) | Starlink share | Observable at once in darkness | Different observable satellites in one night |
|---|---|---|---|---|
| Toronto (10°) | 558 / 621 | 39% | 270 | 6,689 |
| Mumbai (10°) | 604 / 670 | 22% | 403 | 3,077 |
| Svalbard (10°) | 393 / 455 | 18% | 299 | 4,988 |
| New Mexico dark site (20°) | 313 / 362 | 25% | 197 | 2,672 |

Propagating all 15,908 satellites for 24 hours at 1-minute steps (23 million states) takes
about 13 seconds on a 2-core machine with vectorised SGP4.

## Limits

- TLEs are accurate to roughly a kilometre, so sub-kilometre numbers are rough.
  This is a planning-level estimate, not a collision warning.
- Station locations are approximate public sites; real operators use their own networks.
- Only the "active" and four debris groups are loaded, so most debris is not screened.
