"""REST API over the debris database.

Run locally:  uvicorn api.main:app --reload
Docs:         http://localhost:8000/docs
"""

from datetime import datetime, timezone

import numpy as np
from fastapi import FastAPI, HTTPException, Query

from debris import db
from debris.collision import risk_level
from debris.ml.clustering import load_metrics
from debris.propagator import propagate_one, teme_to_geodetic, time_grid

app = FastAPI(
    title="Space Debris Tracker API",
    version="1.0.0",
    description="Real CelesTrak orbital data, close-approach screening and breakup clustering.",
)

OBJECT_COLUMNS = ("norad_id, name, object_type, intl_designator, source_group, epoch, "
                  "inclination_deg, eccentricity, period_min, perigee_km, apogee_km, orbit_class")


def records(df):
    """DataFrame -> JSON-safe list of dicts (NaN becomes null, timestamps become strings)."""
    return df.astype(object).where(df.notna(), None).to_dict(orient="records")


@app.get("/health")
def health():
    count = db.query_df("SELECT COUNT(*) AS n FROM objects")["n"].iloc[0]
    return {"status": "ok", "objects": int(count)}


@app.get("/stats/summary")
def stats_summary():
    return {
        "by_type": records(db.query_df("SELECT * FROM v_summary_by_type ORDER BY object_count DESC")),
        "by_orbit": records(db.query_df("SELECT * FROM v_summary_by_orbit ORDER BY object_count DESC")),
        "breakup_events": records(db.query_df("SELECT * FROM v_breakup_events")),
    }


@app.get("/stats/altitude-density")
def altitude_density():
    return records(db.query_df("SELECT * FROM v_altitude_density ORDER BY altitude_band_km"))


@app.get("/objects")
def list_objects(
    object_type: str | None = Query(None, description="PAYLOAD, DEBRIS or ROCKET BODY"),
    orbit_class: str | None = Query(None, description="LEO, MEO, GEO, HEO or OTHER"),
    search: str | None = Query(None, description="part of the object name"),
    limit: int = Query(50, ge=1, le=1000),
    offset: int = Query(0, ge=0),
):
    sql = f"SELECT {OBJECT_COLUMNS} FROM objects WHERE 1 = 1"
    params = {"limit": limit, "offset": offset}
    if object_type:
        sql += " AND object_type = :object_type"
        params["object_type"] = object_type.upper()
    if orbit_class:
        sql += " AND orbit_class = :orbit_class"
        params["orbit_class"] = orbit_class.upper()
    if search:
        sql += " AND UPPER(name) LIKE :search"
        params["search"] = f"%{search.upper()}%"
    sql += " ORDER BY norad_id LIMIT :limit OFFSET :offset"
    return records(db.query_df(sql, params))


def _get_object(norad_id: int):
    df = db.query_df("SELECT * FROM objects WHERE norad_id = :id", {"id": norad_id})
    if df.empty:
        raise HTTPException(status_code=404, detail=f"NORAD {norad_id} not found")
    return df.iloc[0]


@app.get("/objects/{norad_id}")
def get_object(norad_id: int):
    row = _get_object(norad_id)
    return records(row.to_frame().T)[0]


@app.get("/objects/{norad_id}/position")
def get_position(norad_id: int, at: datetime | None = None):
    """Where the object is now (or at the given UTC time), from SGP4."""
    row = _get_object(norad_id)
    at = (at or datetime.now(timezone.utc)).replace(tzinfo=None)
    jd, fr = time_grid(at, np.array([0.0]))
    r, v, ok = propagate_one(row["tle_line1"], row["tle_line2"], jd, fr)
    if not ok[0]:
        raise HTTPException(status_code=422, detail="SGP4 could not propagate this TLE to that time")
    lat, lon, alt = teme_to_geodetic(r, jd + fr)
    return {
        "norad_id": norad_id,
        "time_utc": at.isoformat(),
        "latitude_deg": float(lat[0]),
        "longitude_deg": float(lon[0]),
        "altitude_km": float(alt[0]),
        "speed_km_s": float(np.linalg.norm(v[0])),
    }


@app.get("/conjunctions")
def list_conjunctions(primary: int | None = None, max_miss_km: float = Query(10.0, gt=0)):
    sql = "SELECT * FROM v_conjunctions_detail WHERE miss_distance_km <= :m"
    params = {"m": max_miss_km}
    if primary:
        sql += " AND primary_norad = :p"
        params["p"] = primary
    df = db.query_df(sql + " ORDER BY tca", params)
    df["risk_level"] = df["collision_probability"].map(risk_level)
    return records(df)


@app.get("/clusters")
def clusters():
    summary = db.query_df(
        "SELECT c.cluster_id, o.source_group, COUNT(*) AS fragments "
        "FROM debris_clusters c JOIN objects o ON o.norad_id = c.norad_id "
        "GROUP BY c.cluster_id, o.source_group ORDER BY c.cluster_id, fragments DESC"
    )
    return {"metrics": load_metrics(), "cluster_vs_event": records(summary)}
