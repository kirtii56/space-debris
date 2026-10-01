"""Download TLE data from CelesTrak, with a local cache to respect their usage policy."""

import io
import logging
import tarfile
import time
from pathlib import Path

import requests

from .config import CACHE_HOURS, RAW_DIR, SNAPSHOT_URL

logger = logging.getLogger(__name__)

BASE_URL = "https://celestrak.org/NORAD/elements/gp.php"
HEADERS = {"User-Agent": "space-debris-tracker (portfolio project)"}


def _cache_path(group: str) -> Path:
    return RAW_DIR / f"{group}.tle"


def _is_fresh(path: Path) -> bool:
    return path.exists() and (time.time() - path.stat().st_mtime) < CACHE_HOURS * 3600


def is_unreachable(exc: Exception) -> bool:
    """True for failures that will repeat for every group (no connection, timeout, blocked)."""
    if isinstance(exc, (requests.ConnectionError, requests.Timeout)):
        return True
    status = getattr(getattr(exc, "response", None), "status_code", None)
    return status in (401, 403, 429)


def fetch_group(group: str, force: bool = False, timeout: int = 30) -> str:
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


def fetch_snapshot(groups: list[str], timeout: int = 120) -> dict[str, str]:
    """Download the daily snapshot published by the GitHub Actions workflow and return the
    TLE text for each requested group it contains."""
    logger.info("Downloading data snapshot from %s", SNAPSHOT_URL)
    response = requests.get(SNAPSHOT_URL, headers=HEADERS, timeout=timeout)
    response.raise_for_status()
    texts = {}
    with tarfile.open(fileobj=io.BytesIO(response.content), mode="r:gz") as archive:
        for member in archive.getmembers():
            group = Path(member.name).stem
            if member.isfile() and member.name.endswith(".tle") and group in groups:
                texts[group] = archive.extractfile(member).read().decode()
    if not texts:
        raise ValueError("The snapshot file contains no TLE data")
    return texts
