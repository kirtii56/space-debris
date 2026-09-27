"""Central settings. Everything can be overridden with environment variables."""

import os
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.getenv("DATA_DIR", ROOT_DIR / "data"))
RAW_DIR = DATA_DIR / "raw"

# SQLite for local work, PostgreSQL inside Docker (set in docker-compose.yml).
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{DATA_DIR / 'debris.db'}")

# CelesTrak groups to download. Debris groups come first so an object that
# appears in several groups keeps its breakup-event label.
CELESTRAK_GROUPS = [
    "fengyun-1c-debris",
    "cosmos-2251-debris",
    "iridium-33-debris",
    "cosmos-1408-debris",
    "stations",
    "active",
]
DEBRIS_GROUPS = [g for g in CELESTRAK_GROUPS if g.endswith("-debris")]

# CelesTrak asks users not to re-download the same group more than once every 2 hours.
CACHE_HOURS = float(os.getenv("CACHE_HOURS", "2"))

# Physical constants
EARTH_RADIUS_KM = 6378.137          # WGS84 equatorial radius
MU_EARTH = 398600.4418              # km^3 / s^2

# Conjunction screening defaults
DEFAULT_PRIMARY_NORAD = 25544       # ISS (ZARYA)
SCREEN_HOURS = 24
SCREEN_STEP_SECONDS = 30
MISS_THRESHOLD_KM = 10.0
MAX_TLE_AGE_DAYS = 30               # older TLEs give unreliable positions
POSITION_SIGMA_KM = 1.0             # assumed 1-sigma position uncertainty (public TLEs have no covariance)
HARD_BODY_RADIUS_KM = 0.020         # combined object radius used for probability
