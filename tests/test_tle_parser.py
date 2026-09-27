from datetime import datetime

import pytest

from debris import tle_parser
from tests.fixtures import make_tle

L1, L2 = make_tle(25544, datetime(2026, 9, 24, 12), 51.64, 100.0, 15.50)


def test_valid_tle_passes_checksum():
    assert tle_parser.validate(L1, L2)


def test_corrupted_tle_fails_checksum():
    broken = L2[:10] + ("9" if L2[10] != "9" else "8") + L2[11:]
    assert not tle_parser.validate(L1, broken)


def test_parse_rejects_bad_tle():
    with pytest.raises(ValueError):
        tle_parser.parse(L1, L2[:-1] + "x", "BROKEN")


def test_parse_values():
    row = tle_parser.parse(L1, L2, "ISS (ZARYA)")
    assert row["norad_id"] == 25544
    assert row["inclination_deg"] == pytest.approx(51.64)
    assert row["epoch"] == datetime(2026, 9, 24, 12)
    assert row["period_min"] == pytest.approx(1440 / 15.5)
    assert 400 < row["perigee_km"] < row["apogee_km"] < 430
    assert row["orbit_class"] == "LEO"
    assert row["launch_id"] == "98067"


@pytest.mark.parametrize("field, expected", [
    (" 12345-3", 0.12345e-3), ("-11606-4", -0.11606e-4), (" 00000-0", 0.0)])
def test_implied_decimal(field, expected):
    assert tle_parser._parse_implied_decimal(field) == pytest.approx(expected)


@pytest.mark.parametrize("name, expected", [
    ("FENGYUN 1C DEB", "DEBRIS"), ("SL-16 R/B", "ROCKET BODY"), ("STARLINK-1007", "PAYLOAD")])
def test_object_type(name, expected):
    assert tle_parser.object_type_from_name(name) == expected


@pytest.mark.parametrize("period, inc, ecc, expected", [
    (92.7, 51.6, 0.0005, "LEO"), (718, 55, 0.01, "MEO"), (1436, 0.05, 0.0002, "GEO"),
    (718, 63.4, 0.7, "HEO")])
def test_orbit_class(period, inc, ecc, expected):
    assert tle_parser.classify_orbit(period, inc, ecc) == expected


def test_split_skips_junk_lines():
    text = f"junk header\nISS (ZARYA)\n{L1}\n{L2}\n"
    assert tle_parser.split_tle_text(text) == [("ISS (ZARYA)", L1, L2)]
