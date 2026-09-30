"""Rediscover satellite breakup events from orbital elements with DBSCAN.

Fragments from the same explosion or collision start in nearly the same orbital
plane, so they share inclination and have similar mean motion and eccentricity.
DBSCAN groups them without being told the answer; we then score the clusters
against the true event labels (the CelesTrak debris group each fragment came from).
"""

import json
import logging
from datetime import datetime, timezone

import numpy as np
import pandas as pd
from sklearn.cluster import DBSCAN
from sklearn.metrics import (adjusted_rand_score, completeness_score, homogeneity_score,
                             silhouette_score)
from sklearn.neighbors import NearestNeighbors
from sklearn.preprocessing import StandardScaler

from .. import db
from ..config import DATA_DIR, DEBRIS_GROUPS

logger = logging.getLogger(__name__)

FEATURES = ["inclination_deg", "mean_motion_rev_day", "eccentricity"]
# Extra orbital elements the dashboard lets you try as features.
EXTRA_COLUMNS = ["raan_deg", "arg_perigee_deg", "perigee_km", "apogee_km"]
METRICS_FILE = DATA_DIR / "cluster_metrics.json"


def load_debris() -> pd.DataFrame:
    placeholders = ", ".join(f"'{g}'" for g in DEBRIS_GROUPS)
    return db.query_df(
        f"SELECT norad_id, name, source_group, {', '.join(FEATURES + EXTRA_COLUMNS)} "
        f"FROM objects "
        f"WHERE object_type = 'DEBRIS' AND source_group IN ({placeholders})"
    )


def k_distances(X: np.ndarray, min_samples: int) -> np.ndarray:
    """Each point's distance to its k-th nearest neighbour, sorted (the 'k-distance plot')."""
    distances, _ = NearestNeighbors(n_neighbors=min_samples).fit(X).kneighbors(X)
    return np.sort(distances[:, -1])


def suggest_eps(X: np.ndarray, min_samples: int) -> float:
    """k-distance 'elbow': the point furthest below the straight line joining the first
    and last k-distances."""
    k_dist = k_distances(X, min_samples)
    x = np.arange(len(k_dist))
    line = k_dist[0] + (k_dist[-1] - k_dist[0]) * x / max(len(k_dist) - 1, 1)
    return float(k_dist[int(np.argmax(line - k_dist))])


def cluster(df: pd.DataFrame, eps: float | None = None, min_samples: int = 10,
            features: list[str] | None = None):
    X = StandardScaler().fit_transform(df[features or FEATURES])
    eps = eps or suggest_eps(X, min_samples)
    labels = DBSCAN(eps=eps, min_samples=min_samples).fit_predict(X)

    true = df["source_group"].to_numpy()
    clustered = labels != -1
    metrics = {
        "eps": round(eps, 4),
        "min_samples": min_samples,
        "fragments": int(len(df)),
        "clusters_found": int(len(set(labels)) - (1 if -1 in labels else 0)),
        "true_events": int(df["source_group"].nunique()),
        "noise_fraction": round(float(1 - clustered.mean()), 4),
        "homogeneity": round(float(homogeneity_score(true, labels)), 4),
        "completeness": round(float(completeness_score(true, labels)), 4),
        "adjusted_rand_index": round(float(adjusted_rand_score(true, labels)), 4),
    }
    if len(set(labels[clustered])) > 1:
        # Silhouette is O(n^2), so score a fixed random sample of up to 3,000 points.
        n = int(clustered.sum())
        metrics["silhouette"] = round(float(silhouette_score(
            X[clustered], labels[clustered], sample_size=min(n, 3000), random_state=0)), 4)
    return labels, metrics


def run(eps: float | None = None, min_samples: int = 10) -> dict:
    df = load_debris()
    if len(df) < min_samples * 2:
        raise RuntimeError("Not enough debris in the database to cluster. Run ingest first.")
    labels, metrics = cluster(df, eps, min_samples)

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    out = pd.DataFrame({"norad_id": df["norad_id"], "cluster_id": labels, "run_at": now})
    db.replace_rows(out, "debris_clusters", "DELETE FROM debris_clusters")

    metrics["run_at"] = now.isoformat(timespec="seconds")
    METRICS_FILE.parent.mkdir(parents=True, exist_ok=True)
    METRICS_FILE.write_text(json.dumps(metrics, indent=2))
    logger.info("Clustering metrics: %s", metrics)
    return metrics


def load_metrics() -> dict | None:
    return json.loads(METRICS_FILE.read_text()) if METRICS_FILE.exists() else None
