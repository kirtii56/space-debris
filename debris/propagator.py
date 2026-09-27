"""SGP4 orbit propagation, vectorised with NumPy so thousands of objects run at once."""

from datetime import datetime

import numpy as np
from sgp4.api import Satrec, SatrecArray, jday

from .config import EARTH_RADIUS_KM


def make_satrec(line1: str, line2: str) -> Satrec:
    return Satrec.twoline2rv(line1, line2)


def time_grid(start: datetime, offsets_s: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Julian date split into whole (jd) and fractional (fr) parts for each offset in seconds."""
    jd0, fr0 = jday(start.year, start.month, start.day, start.hour, start.minute,
                    start.second + start.microsecond / 1e6)
    fr = fr0 + np.asarray(offsets_s, dtype=float) / 86400.0
    jd = np.full_like(fr, jd0)
    return jd, fr


def propagate_many(line1s, line2s, jd: np.ndarray, fr: np.ndarray):
    """Positions/velocities in the TEME frame for N objects at T times.

    Returns r (N, T, 3) km, v (N, T, 3) km/s and ok (N, T) — False where SGP4 failed
    (for example a decayed orbit). Failed positions are set to NaN.
    """
    sats = SatrecArray([make_satrec(a, b) for a, b in zip(line1s, line2s)])
    err, r, v = sats.sgp4(jd, fr)
    ok = err == 0
    r[~ok] = np.nan
    v[~ok] = np.nan
    return r, v, ok


def propagate_one(line1: str, line2: str, jd: np.ndarray, fr: np.ndarray):
    """Same as propagate_many for a single object. Returns r (T, 3), v (T, 3), ok (T,)."""
    r, v, ok = propagate_many([line1], [line2], jd, fr)
    return r[0], v[0], ok[0]


def gmst_rad(jd_full: np.ndarray) -> np.ndarray:
    """Greenwich mean sidereal time (IAU 1982 model), in radians."""
    t = (jd_full - 2451545.0) / 36525.0
    seconds = (67310.54841 + (876600.0 * 3600 + 8640184.812866) * t
               + 0.093104 * t ** 2 - 6.2e-6 * t ** 3)
    return np.radians((seconds % 86400.0) / 240.0)


def teme_to_geodetic(r: np.ndarray, jd_full: np.ndarray):
    """Convert TEME positions (..., 3) to latitude, longitude (deg) and altitude (km).

    Rotates by Earth's sidereal angle, then solves for WGS84 geodetic latitude.
    Ignores polar motion (sub-kilometre effect), which is fine for maps and statistics.
    """
    theta = gmst_rad(jd_full)
    x, y, z = r[..., 0], r[..., 1], r[..., 2]
    x_ecef = np.cos(theta) * x + np.sin(theta) * y
    y_ecef = -np.sin(theta) * x + np.cos(theta) * y

    f = 1 / 298.257223563
    e2 = f * (2 - f)
    p = np.hypot(x_ecef, y_ecef)
    lat = np.arctan2(z, p * (1 - e2))
    for _ in range(5):  # converges to well under a metre
        n = EARTH_RADIUS_KM / np.sqrt(1 - e2 * np.sin(lat) ** 2)
        alt = p / np.cos(lat) - n
        lat = np.arctan2(z, p * (1 - e2 * n / (n + alt)))
    lon = np.degrees(np.arctan2(y_ecef, x_ecef))
    return np.degrees(lat), lon, alt
