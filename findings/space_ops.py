"""Four small space-operations questions, answered with one day of public CelesTrak data.

Run from the repo root:   python -m findings.space_ops
It uses the daily data snapshot published by this repo (or data/raw if already downloaded),
and reuses the project's own TLE parser, SGP4 propagator and conjunction screen.

1. Imaging chances  - how often an Earth-observation satellite passes within 50 km of
                      another active satellite (a chance to photograph it from orbit).
2. Out of contact   - how much of the day that satellite can reach five well-known
                      polar / EO ground-station sites, and how long the gaps are.
3. Alone decisions  - how many of those close passes happen while it is out of contact.
4. Fleet scale      - close approaches under 5 km for a random sample of 100 Starlink
                      satellites over 24 hours.
"""

import io
import json
import tarfile
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import requests

from debris.config import RAW_DIR, SNAPSHOT_URL
from debris.conjunctions import screen
from debris.propagator import gmst_rad, propagate_many, time_grid
from debris.tle_parser import parse, split_tle_text

OUT = Path(__file__).parent
START = datetime(2026, 10, 24, 14, 0, 0)       # fixed so the results are reproducible
HOURS = 24
EO_HOSTS = ["SENTINEL-2A", "SENTINEL-2B", "LANDSAT 8", "LANDSAT 9",
            "WORLDVIEW-3 (WV-3)", "PLEIADES NEO 3"]
STATIONS = {  # approximate public locations of large ground-station sites
    "Svalbard": (78.23, 15.41), "Troll": (-72.01, 2.53), "Fairbanks": (64.86, -147.85),
    "Kiruna": (67.86, 20.96), "Hartebeesthoek": (-25.89, 27.68),
}
MIN_ELEVATION_DEG = 5
EARTH_RADIUS_KM = 6378.137


def load_catalogue() -> pd.DataFrame:
    files = sorted(RAW_DIR.glob("*.tle"))
    if files:
        texts = [f.read_text() for f in files]
    else:
        blob = requests.get(SNAPSHOT_URL, timeout=120).content
        with tarfile.open(fileobj=io.BytesIO(blob)) as tar:
            texts = [tar.extractfile(m).read().decode() for m in tar.getmembers()
                     if m.name.endswith(".tle")]
    rows, seen = [], set()
    for text in texts:
        for name, l1, l2 in split_tle_text(text):
            try:
                row = parse(l1, l2, name)
            except ValueError:
                continue
            if row["norad_id"] not in seen:
                seen.add(row["norad_id"])
                rows.append(row)
    return pd.DataFrame(rows)


def visibility(row: pd.Series, offsets: np.ndarray) -> np.ndarray:
    """True at each time step when the satellite is above 5 deg at any station."""
    jd, fr = time_grid(START, offsets)
    r, _, _ = propagate_many([row.tle_line1], [row.tle_line2], jd, fr)
    r = r[0]
    g = gmst_rad(jd + fr)
    c, s = np.cos(g), np.sin(g)
    sat = np.stack([c * r[:, 0] + s * r[:, 1], -s * r[:, 0] + c * r[:, 1], r[:, 2]], axis=1)
    seen = np.zeros(len(offsets), bool)
    for lat, lon in STATIONS.values():
        la, lo = np.radians(lat), np.radians(lon)
        p = EARTH_RADIUS_KM * np.array([np.cos(la) * np.cos(lo), np.cos(la) * np.sin(lo), np.sin(la)])
        up = p / np.linalg.norm(p)
        d = sat - p
        seen |= np.degrees(np.arcsin((d @ up) / np.linalg.norm(d, axis=1))) > MIN_ELEVATION_DEG
    return seen


def gaps_minutes(seen: np.ndarray, step_s: float) -> list[float]:
    gaps, run = [], 0
    for v in seen:
        if v:
            if run:
                gaps.append(run * step_s / 60)
            run = 0
        else:
            run += 1
    if run:
        gaps.append(run * step_s / 60)
    return gaps


def main() -> None:
    df = load_catalogue()
    names = df[["norad_id", "name"]]
    step = 10.0
    offsets = np.arange(0, HOURS * 3600 + step, step)
    summary = {"start_utc": str(START), "objects": int(len(df)), "hosts": {}}

    passes = []
    for host in EO_HOSTS:
        match = df[df.name.str.strip() == host]
        if match.empty:
            continue
        row = match.iloc[0]
        p = screen(df, int(row.norad_id), start=START, hours=HOURS, step_s=30,
                   threshold_km=50.0, max_age_days=7)
        p = p.merge(names, left_on="secondary_norad", right_on="norad_id")
        p = p[~p.name.str.contains("DEB")].copy()
        seen = visibility(row, offsets)
        idx = ((pd.to_datetime(p.tca) - pd.Timestamp(START)).dt.total_seconds() / step)
        p["in_contact"] = seen[idx.round().astype(int).clip(0, len(seen) - 1).values]
        p["host"] = host
        passes.append(p)
        gaps = gaps_minutes(seen, step)
        summary["hosts"][host] = {
            "passes_under_50km": int(len(p)),
            "different_satellites": int(p.name.nunique()),
            "slow_passes_under_3_km_s": int((p.relative_velocity_km_s < 3).sum()),
            "passes_out_of_contact": int((~p.in_contact).sum()),
            "share_of_day_in_contact": round(float(seen.mean()), 3),
            "longest_gap_min": round(max(gaps), 1),
        }
        print(host, summary["hosts"][host])
    pd.concat(passes).drop(columns=["norad_id"]).to_csv(OUT / "eo_close_passes.csv", index=False)

    starlink = df[df.name.str.startswith("STARLINK")].sample(100, random_state=0)
    events = []
    for nid in starlink.norad_id:
        e = screen(df, int(nid), start=START, hours=HOURS, step_s=30,
                   threshold_km=5.0, max_age_days=7)
        events.append(e)
    ev = pd.concat(events).merge(names, left_on="secondary_norad", right_on="norad_id")
    ev = ev[ev.relative_velocity_km_s > 0.5]     # ignore satellites flying in formation
    ev.drop(columns=["norad_id"]).to_csv(OUT / "starlink_sample_close_approaches.csv", index=False)
    summary["starlink_sample"] = {
        "satellites_sampled": 100,
        "approaches_under_5km": int(len(ev)),
        "approaches_under_1km": int((ev.miss_distance_km < 1).sum()),
        "satellites_with_at_least_one": int(ev.primary_norad.nunique()),
        "share_with_other_starlink": round(float(ev.name.str.startswith("STARLINK").mean()), 3),
    }
    print(summary["starlink_sample"])
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
