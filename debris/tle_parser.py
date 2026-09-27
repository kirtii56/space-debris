"""Parse and validate Two-Line Element (TLE) sets and derive orbit properties."""

import math
from datetime import datetime, timedelta

from .config import EARTH_RADIUS_KM, MU_EARTH


def checksum(line: str) -> int:
    """TLE checksum: sum of digits, with '-' counting as 1, modulo 10."""
    total = 0
    for char in line[:68]:
        if char.isdigit():
            total += int(char)
        elif char == "-":
            total += 1
    return total % 10


def validate(line1: str, line2: str) -> bool:
    """True if both lines have the right length, line numbers and checksums."""
    if len(line1) != 69 or len(line2) != 69:
        return False
    if not (line1.startswith("1 ") and line2.startswith("2 ")):
        return False
    if not (line1[68].isdigit() and line2[68].isdigit()):
        return False
    return checksum(line1) == int(line1[68]) and checksum(line2) == int(line2[68])


def _parse_implied_decimal(field: str) -> float:
    """Parse TLE 'implied decimal' notation, e.g. ' 12345-3' -> 0.12345e-3."""
    field = field.strip()
    if not field or field in ("00000-0", "00000+0", "-00000-0"):
        return 0.0
    mantissa, exponent = field[:-2], field[-2:]
    sign = ""
    if mantissa[0] in "+-":
        sign, mantissa = mantissa[0], mantissa[1:]
    return float(f"{sign}0.{mantissa}e{exponent}")


def object_type_from_name(name: str) -> str:
    """CelesTrak names mark fragments with 'DEB' and spent stages with 'R/B'."""
    upper = name.upper()
    if " DEB" in upper or upper.endswith("DEB"):
        return "DEBRIS"
    if "R/B" in upper:
        return "ROCKET BODY"
    return "PAYLOAD"


def classify_orbit(period_min: float, inclination_deg: float, eccentricity: float) -> str:
    """Rough orbit regime from period, inclination and eccentricity."""
    if eccentricity > 0.25:
        return "HEO"
    if period_min < 128:
        return "LEO"
    if 1430 <= period_min <= 1442 and inclination_deg < 15:
        return "GEO"
    if period_min < 1430:
        return "MEO"
    return "OTHER"


def parse(line1: str, line2: str, name: str = "") -> dict:
    """Parse one TLE into a flat dictionary (one row of the objects table)."""
    if not validate(line1, line2):
        raise ValueError(f"Invalid TLE (format or checksum): {name or line1[2:7]}")

    name = name.strip()
    intl_designator = line1[9:17].strip()
    epoch_year = int(line1[18:20])
    epoch_day = float(line1[20:32])
    year = 2000 + epoch_year if epoch_year < 57 else 1900 + epoch_year
    epoch = datetime(year, 1, 1) + timedelta(days=epoch_day - 1)

    inclination = float(line2[8:16])
    eccentricity = float("0." + line2[26:33].strip())
    mean_motion = float(line2[52:63])     # revolutions per day

    period_min = 1440.0 / mean_motion
    n_rad_s = mean_motion * 2 * math.pi / 86400.0
    semi_major_axis = (MU_EARTH / n_rad_s ** 2) ** (1 / 3)

    return {
        "norad_id": int(line1[2:7]),
        "name": name,
        "object_type": object_type_from_name(name),
        "intl_designator": intl_designator,
        # First 5 characters (e.g. '99025') identify the launch the object came from.
        "launch_id": intl_designator[:5],
        "epoch": epoch,
        "inclination_deg": inclination,
        "raan_deg": float(line2[17:25]),
        "eccentricity": eccentricity,
        "arg_perigee_deg": float(line2[34:42]),
        "mean_anomaly_deg": float(line2[43:51]),
        "mean_motion_rev_day": mean_motion,
        "bstar": _parse_implied_decimal(line1[53:61]),
        "period_min": period_min,
        "semi_major_axis_km": semi_major_axis,
        "perigee_km": semi_major_axis * (1 - eccentricity) - EARTH_RADIUS_KM,
        "apogee_km": semi_major_axis * (1 + eccentricity) - EARTH_RADIUS_KM,
        "orbit_class": classify_orbit(period_min, inclination, eccentricity),
        "tle_line1": line1,
        "tle_line2": line2,
    }


def split_tle_text(text: str) -> list[tuple[str, str, str]]:
    """Split a 3-line-per-object TLE file into (name, line1, line2) tuples."""
    lines = [ln.rstrip() for ln in text.splitlines() if ln.strip()]
    records = []
    i = 0
    while i + 2 < len(lines):
        name, l1, l2 = lines[i], lines[i + 1], lines[i + 2]
        if l1.startswith("1 ") and l2.startswith("2 "):
            records.append((name, l1, l2))
            i += 3
        else:
            i += 1   # skip a malformed line and resynchronise
    return records
