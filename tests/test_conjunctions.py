from datetime import timedelta

import numpy as np
import pandas as pd
import pytest

from debris import tle_parser
from debris.collision import collision_probability, risk_level
from debris.conjunctions import screen
from tests.fixtures import make_tle


def catalogue(now, visitor_epoch_offset_days=0):
    iss = tle_parser.parse(*make_tle(25544, now, 51.64, 100.0, 15.50), "ISS")
    visitor = tle_parser.parse(*make_tle(90001, now - timedelta(days=visitor_epoch_offset_days),
                                         51.70, 100.0, 15.50, mean_anomaly_deg=0.02), "VISITOR")
    far = tle_parser.parse(*make_tle(90002, now, 98.0, 0.0, 14.0), "FAR AWAY")  # ~900 km up
    return pd.DataFrame([iss, visitor, far])


def test_finds_visitor_and_ignores_far_object(now):
    result = screen(catalogue(now), 25544, start=now, hours=6)
    assert set(result["secondary_norad"]) == {90001}
    assert result["miss_distance_km"].max() <= 10
    # planes cross at 0.06 degrees, so relative speed is about 7.66 km/s * sin(0.06 deg)
    assert result["relative_velocity_km_s"].iloc[0] == pytest.approx(0.008, abs=0.002)


def test_stale_tles_are_skipped(now):
    result = screen(catalogue(now, visitor_epoch_offset_days=60), 25544, start=now, hours=6)
    assert result.empty


def test_unknown_primary_raises(now):
    with pytest.raises(ValueError):
        screen(catalogue(now), 12345, start=now)


def test_probability_behaviour():
    pc = collision_probability(np.array([0.0, 0.5, 1.0, 5.0]))
    assert np.all(np.diff(pc) < 0)           # further apart -> less likely
    assert pc[0] == pytest.approx(0.02 ** 2 / 2)
    assert risk_level(1e-3) == "HIGH" and risk_level(1e-5) == "MEDIUM" and risk_level(1e-9) == "LOW"
