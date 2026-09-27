"""Synthetic TLEs for tests only. Built with sgp4's own exporter so checksums and
formats are genuine. The application itself only ever loads real CelesTrak data."""

import math
from datetime import datetime

import numpy as np
from sgp4.api import WGS72, Satrec
from sgp4.exporter import export_tle


def make_tle(norad_id: int, epoch: datetime, inclination_deg: float, raan_deg: float,
             mean_motion_rev_day: float, eccentricity: float = 0.0005,
             arg_perigee_deg: float = 0.0, mean_anomaly_deg: float = 0.0,
             intl_designator: str = "98067A") -> tuple[str, str]:
    epoch_1949 = (epoch - datetime(1949, 12, 31)).total_seconds() / 86400.0
    sat = Satrec()
    sat.sgp4init(WGS72, "i", norad_id, epoch_1949, 1e-5, 0.0, 0.0, eccentricity,
                 math.radians(arg_perigee_deg), math.radians(inclination_deg),
                 math.radians(mean_anomaly_deg), mean_motion_rev_day * 2 * math.pi / 1440.0,
                 math.radians(raan_deg))
    sat.intldesg = intl_designator
    sat.classification = "U"
    return export_tle(sat)


# (group, base inclination, base mean motion, launch designator) — values close to the real events
EVENTS = [
    ("fengyun-1c-debris", 98.8, 14.25, "99025"),
    ("cosmos-2251-debris", 74.0, 14.45, "93036"),
    ("iridium-33-debris", 86.4, 14.35, "97051"),
    ("cosmos-1408-debris", 82.6, 15.40, "82092"),
]


def synthetic_catalogue(epoch: datetime, fragments_per_event: int = 60, seed: int = 7) -> str:
    """A TLE text file containing an ISS-like station, a nearby 'visitor' that makes close
    approaches, debris clouds for four breakup events, and some payloads."""
    rng = np.random.default_rng(seed)
    blocks = []

    def add(name, l1, l2):
        blocks.append(f"{name}\n{l1}\n{l2}")

    add("ISS (ZARYA)", *make_tle(25544, epoch, 51.64, 100.0, 15.50))
    # Same altitude, different plane, same phase at the node -> repeated close passes.
    add("TEST VISITOR", *make_tle(90001, epoch, 51.70, 100.0, 15.50, mean_anomaly_deg=0.02,
                                  intl_designator="24001A"))

    norad = 40000
    for group, inc, mm, launch in EVENTS:
        for k in range(fragments_per_event):
            norad += 1
            add(f"{group.split('-debris')[0].upper()} DEB",
                *make_tle(norad, epoch, inc + rng.normal(0, 0.15), rng.uniform(0, 360),
                          mm + rng.normal(0, 0.12), abs(rng.normal(0.004, 0.002)),
                          rng.uniform(0, 360), rng.uniform(0, 360),
                          intl_designator=f"{launch}{chr(65 + k % 26)}{chr(65 + k // 26)}"))
    for k in range(40):
        norad += 1
        add(f"PAYLOAD {k}", *make_tle(norad, epoch, rng.choice([53.0, 97.6, 43.0]),
                                      rng.uniform(0, 360), rng.uniform(14.9, 15.3),
                                      mean_anomaly_deg=rng.uniform(0, 360),
                                      intl_designator=f"23{k:03d}A"))
    return "\n".join(blocks) + "\n"
