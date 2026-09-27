"""Ingest pipeline: download TLEs -> parse -> clean with pandas -> load into SQL."""

import logging
from datetime import datetime, timezone

import pandas as pd

from . import celestrak, db, tle_parser
from .config import CELESTRAK_GROUPS

logger = logging.getLogger(__name__)


def parse_group(text: str, group: str) -> pd.DataFrame:
    rows, bad = [], 0
    for name, line1, line2 in tle_parser.split_tle_text(text):
        try:
            row = tle_parser.parse(line1, line2, name)
        except ValueError:
            bad += 1
            continue
        row["source_group"] = group
        rows.append(row)
    if bad:
        logger.warning("%s: skipped %d TLEs that failed validation", group, bad)
    return pd.DataFrame(rows)


def clean(df: pd.DataFrame) -> pd.DataFrame:
    """Deduplicate, drop impossible orbits and add derived columns."""
    before = len(df)
    # Groups are loaded in priority order, so keep the first (most specific) label.
    df = df.drop_duplicates(subset="norad_id", keep="first")
    # Perigee below ~100 km means the object is re-entering; the TLE is not usable.
    df = df[df["perigee_km"] > 100].copy()
    df["altitude_band_km"] = (df["perigee_km"] // 100 * 100).astype(int)
    df["ingested_at"] = datetime.now(timezone.utc).replace(tzinfo=None)
    logger.info("Cleaning: %d rows in, %d rows out", before, len(df))
    return df


def run(groups: list[str] | None = None, force_download: bool = False) -> pd.DataFrame:
    groups = groups or CELESTRAK_GROUPS
    frames = []
    for group in groups:
        try:
            text = celestrak.fetch_group(group, force=force_download)
        except Exception as exc:  # one failing group should not stop the rest
            logger.error("Could not load %s: %s", group, exc)
            continue
        frame = parse_group(text, group)
        logger.info("%s: %d objects parsed", group, len(frame))
        frames.append(frame)

    if not frames:
        raise RuntimeError("No data downloaded. Check your internet connection and try again.")

    df = clean(pd.concat(frames, ignore_index=True))
    db.init_schema()
    # Conjunctions and clusters refer to object IDs, so clear them with the old catalogue.
    db.execute("DELETE FROM conjunctions")
    db.execute("DELETE FROM debris_clusters")
    count = db.replace_rows(df, "objects", "DELETE FROM objects")
    logger.info("Loaded %d objects into the database", count)
    return df
