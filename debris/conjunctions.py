"""Screen one primary object (e.g. the ISS) against the catalogue for close approaches.

Method
1. Filter: drop objects with stale TLEs and objects whose altitude range never
   overlaps the primary's (they can never meet).
2. Coarse pass: propagate everything on a 30-second grid and find local minima of
   the distance to the primary.
3. Refine each candidate minimum on a 1-second grid, then apply a straight-line
   correction using relative velocity to get the exact time of closest approach (TCA).
"""

import logging
from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd

from . import db
from .collision import collision_probability
from .config import (DEFAULT_PRIMARY_NORAD, MAX_TLE_AGE_DAYS, MISS_THRESHOLD_KM,
                     SCREEN_HOURS, SCREEN_STEP_SECONDS)
from .propagator import propagate_many, propagate_one, time_grid

logger = logging.getLogger(__name__)

MAX_RELATIVE_SPEED_KM_S = 16.0   # head-on LEO encounter upper bound
CHUNK = 500                      # objects propagated per batch (keeps memory small)


def _candidate_filter(df: pd.DataFrame, primary: pd.Series, start: datetime,
                      threshold_km: float, max_age_days: float) -> pd.DataFrame:
    age_days = (start - pd.to_datetime(df["epoch"])).dt.total_seconds().abs() / 86400
    overlaps = ((df["perigee_km"] <= primary["apogee_km"] + threshold_km)
                & (df["apogee_km"] >= primary["perigee_km"] - threshold_km))
    return df[(df["norad_id"] != primary["norad_id"]) & (age_days <= max_age_days) & overlaps]


def _local_minima(d: np.ndarray, gate: float) -> tuple[np.ndarray, np.ndarray]:
    """Indices (object, time) where distance is a local minimum below the gate."""
    padded = np.pad(d, ((0, 0), (1, 1)), constant_values=np.inf)
    is_min = (d <= padded[:, :-2]) & (d <= padded[:, 2:]) & (d < gate)
    return np.nonzero(is_min)


def _refine(sec_l1, sec_l2, pri_l1, pri_l2, start, t_center_s, step_s):
    """Return (tca_offset_s, miss_km, rel_speed_km_s) around a coarse minimum."""
    offsets = np.arange(t_center_s - step_s, t_center_s + step_s + 1, 1.0)
    jd, fr = time_grid(start, offsets)
    rp, vp, okp = propagate_one(pri_l1, pri_l2, jd, fr)
    rs, vs, oks = propagate_one(sec_l1, sec_l2, jd, fr)
    dist = np.linalg.norm(rs - rp, axis=1)
    dist[~(okp & oks)] = np.inf
    k = int(np.argmin(dist))
    if not np.isfinite(dist[k]):
        return None
    dr, dv = rs[k] - rp[k], vs[k] - vp[k]
    tau = float(np.clip(-np.dot(dr, dv) / np.dot(dv, dv), -1.0, 1.0))
    miss = float(np.linalg.norm(dr + dv * tau))
    return offsets[k] + tau, miss, float(np.linalg.norm(dv))


def screen(objects: pd.DataFrame, primary_norad: int = DEFAULT_PRIMARY_NORAD,
           start: datetime | None = None, hours: float = SCREEN_HOURS,
           step_s: int = SCREEN_STEP_SECONDS, threshold_km: float = MISS_THRESHOLD_KM,
           max_age_days: float = MAX_TLE_AGE_DAYS) -> pd.DataFrame:
    start = start or datetime.now(timezone.utc).replace(tzinfo=None, microsecond=0)
    match = objects[objects["norad_id"] == primary_norad]
    if match.empty:
        raise ValueError(f"NORAD {primary_norad} is not in the catalogue")
    primary = match.iloc[0]

    candidates = _candidate_filter(objects, primary, start, threshold_km, max_age_days)
    logger.info("Screening %s against %d candidates (of %d objects)",
                primary["name"], len(candidates), len(objects))

    offsets = np.arange(0, hours * 3600 + step_s, step_s, dtype=float)
    jd, fr = time_grid(start, offsets)
    rp, _, okp = propagate_one(primary["tle_line1"], primary["tle_line2"], jd, fr)
    gate = threshold_km + MAX_RELATIVE_SPEED_KM_S * step_s / 2

    events = []
    for i in range(0, len(candidates), CHUNK):
        chunk = candidates.iloc[i:i + CHUNK]
        r, _, ok = propagate_many(chunk["tle_line1"], chunk["tle_line2"], jd, fr)
        d = np.linalg.norm(r - rp[None, :, :], axis=2)
        d[~(ok & okp[None, :])] = np.inf
        for obj_idx, t_idx in zip(*_local_minima(d, gate)):
            sec = chunk.iloc[obj_idx]
            refined = _refine(sec["tle_line1"], sec["tle_line2"], primary["tle_line1"],
                              primary["tle_line2"], start, offsets[t_idx], step_s)
            if refined and refined[1] <= threshold_km:
                t_off, miss, speed = refined
                events.append({
                    "primary_norad": int(primary["norad_id"]),
                    "secondary_norad": int(sec["norad_id"]),
                    "tca": start + timedelta(seconds=float(t_off)),
                    "miss_distance_km": miss,
                    "relative_velocity_km_s": speed,
                })

    result = pd.DataFrame(events, columns=["primary_norad", "secondary_norad", "tca",
                                           "miss_distance_km", "relative_velocity_km_s"])
    if not result.empty:
        # Minima from neighbouring coarse steps can refine to the same event; keep one.
        result["tca"] = pd.to_datetime(result["tca"]).dt.round("1s")
        result = result.sort_values("miss_distance_km").drop_duplicates(
            subset=["secondary_norad", "tca"])
    result["collision_probability"] = collision_probability(result["miss_distance_km"])
    result["screened_at"] = start
    logger.info("Found %d close approaches under %.1f km", len(result), threshold_km)
    return result.sort_values("tca").reset_index(drop=True)


def run(primary_norad: int = DEFAULT_PRIMARY_NORAD, **kwargs) -> pd.DataFrame:
    objects = db.query_df("SELECT * FROM objects")
    if objects.empty:
        raise RuntimeError("The objects table is empty. Run the ingest step first.")
    result = screen(objects, primary_norad, **kwargs)
    db.replace_rows(result, "conjunctions",
                    "DELETE FROM conjunctions WHERE primary_norad = :p", {"p": primary_norad})
    return result
