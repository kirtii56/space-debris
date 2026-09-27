from datetime import datetime

import numpy as np
import pytest

from debris.propagator import gmst_rad, propagate_many, propagate_one, teme_to_geodetic, time_grid
from tests.fixtures import make_tle

EPOCH = datetime(2026, 9, 24, 12)
L1, L2 = make_tle(25544, EPOCH, 51.64, 100.0, 15.50)


def test_iss_altitude_and_speed_over_one_day():
    jd, fr = time_grid(EPOCH, np.arange(0, 86400, 60))
    r, v, ok = propagate_one(L1, L2, jd, fr)
    assert ok.all()
    altitude = np.linalg.norm(r, axis=1) - 6378.137
    speed = np.linalg.norm(v, axis=1)
    assert altitude.min() > 380 and altitude.max() < 450
    assert speed == pytest.approx(7.66, abs=0.05)


def test_latitude_never_exceeds_inclination():
    jd, fr = time_grid(EPOCH, np.arange(0, 6000, 30))
    r, _, _ = propagate_one(L1, L2, jd, fr)
    lat, lon, _ = teme_to_geodetic(r, jd + fr)
    assert np.abs(lat).max() <= 51.64 + 0.3
    assert np.abs(lon).max() <= 180


def test_gmst_at_j2000():
    # GMST at 2000-01-01 12:00 UT1 is 280.46061837 degrees.
    assert np.degrees(gmst_rad(np.array([2451545.0])))[0] == pytest.approx(280.46061837, abs=1e-6)


def test_vectorised_matches_single():
    other = make_tle(40000, EPOCH, 98.7, 10.0, 14.3)
    jd, fr = time_grid(EPOCH, np.array([0.0, 600.0, 1200.0]))
    r_many, _, _ = propagate_many([L1, other[0]], [L2, other[1]], jd, fr)
    r_one, _, _ = propagate_one(L1, L2, jd, fr)
    np.testing.assert_allclose(r_many[0], r_one)
