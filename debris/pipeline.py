"""Ingest pipeline: download TLEs -> parse -> clean with pandas -> load into SQL."""

import json
import logging
from datetime import datetime, timezone

import pandas as pd

from . import celestrak, db, tle_parser
from .config import CELESTRAK_GROUPS, SOURCE_FILE

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


def download(groups: list[str], force: bool = False) -> tuple[dict[str, str], str]:
    """TLE text per group, plus where it came from.

    Tries CelesTrak first. Groups that fail (for example because CelesTrak blocks the host)
    are filled from the daily snapshot that GitHub Actions publishes.
    """
    texts, errors = {}, {}
    blocked = None
    for group in groups:
        if blocked is not None:          # CelesTrak unreachable: don't wait on every group
            errors[group] = blocked
            continue
        try:
            texts[group] = celestrak.fetch_group(group, force=force)
        except Exception as exc:  # one failing group should not stop the rest
            logger.warning("Could not download %s from CelesTrak: %s", group, exc)
            errors[group] = exc
            if celestrak.is_unreachable(exc):
                blocked = exc
    if not errors:
        return texts, "CelesTrak (live)"

    try:
        snapshot = celestrak.fetch_snapshot(list(errors))
    except Exception as exc:
        logger.error("Snapshot download failed too: %s", exc)
        if not texts:
            first = next(iter(errors.values()))
            raise RuntimeError(f"No data downloaded. CelesTrak: {first}. Snapshot: {exc}") from exc
        return texts, "CelesTrak (live, some groups missing)"
    source = "CelesTrak (live) + daily snapshot" if texts else "Daily snapshot of CelesTrak data"
    texts.update(snapshot)
    return texts, source


def run(groups: list[str] | None = None, force_download: bool = False) -> pd.DataFrame:
    groups = groups or CELESTRAK_GROUPS
    texts, source = download(groups, force_download)
    frames = []
    for group in groups:              # keep the priority order of the groups
        if group in texts:
            frame = parse_group(texts[group], group)
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
    logger.info("Loaded %d objects into the database (source: %s)", count, source)
    SOURCE_FILE.parent.mkdir(parents=True, exist_ok=True)
    SOURCE_FILE.write_text(json.dumps({
        "source": source,
        "loaded_utc": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M"),
    }))
    return df
