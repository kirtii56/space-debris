"""Collision probability estimate.

Public TLEs come without covariance (uncertainty) data, so real Pc cannot be computed
from them. This module uses the standard simplification: a 2-D isotropic Gaussian
position error of POSITION_SIGMA_KM in the encounter plane and a small combined
hard-body radius (Foster-style, small-object approximation):

    Pc ~ (R^2 / (2 * sigma^2)) * exp(-d^2 / (2 * sigma^2))

It is useful for ranking events against each other, not as an operational number.
"""

import numpy as np

from .config import HARD_BODY_RADIUS_KM, POSITION_SIGMA_KM


def collision_probability(miss_distance_km, sigma_km: float = POSITION_SIGMA_KM,
                          hard_body_radius_km: float = HARD_BODY_RADIUS_KM):
    d = np.asarray(miss_distance_km, dtype=float)
    pc = (hard_body_radius_km ** 2 / (2 * sigma_km ** 2)) * np.exp(-d ** 2 / (2 * sigma_km ** 2))
    return np.minimum(pc, 1.0)


def risk_level(pc: float) -> str:
    if pc >= 1e-4:
        return "HIGH"
    if pc >= 1e-6:
        return "MEDIUM"
    return "LOW"
