"""Download TLE data from CelesTrak, with a local cache to respect their usage policy."""

import logging
import time
from pathlib import Path

import requests

from .config import CACHE_HOURS, RAW_DIR

logger = logging.getLogger(__name__)

BASE_URL = "https://celestrak.org/NORAD/elements/gp.php"
HEADERS = {"User-Agent": "space-debris-tracker (portfolio project)"}


def _cache_path(group: str) -> Path:
    return RAW_DIR / f"{group}.tle"


def _is_fresh(path: Path) -> bool:
    return path.exists() and (time.time() - path.stat().st_mtime) < CACHE_HOURS * 3600


def fetch_group(group: str, force: bool = False, timeout: int = 60) -> str:
    """Return the raw TLE text for one CelesTrak group, using the cache when fresh."""
    path = _cache_path(group)
    if not force and _is_fresh(path):
        logger.info("Using cached %s (less than %.0f h old)", group, CACHE_HOURS)
        return path.read_text()

    logger.info("Downloading %s from CelesTrak", group)
    response = requests.get(
        BASE_URL, params={"GROUP": group, "FORMAT": "tle"}, headers=HEADERS, timeout=timeout
    )
    response.raise_for_status()
    text = response.text

    # CelesTrak answers unknown or empty groups with a plain-text message instead of an error code.
    if "1 " not in text[:500]:
        raise ValueError(f"CelesTrak returned no TLEs for group '{group}': {text[:120]!r}")

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return text
