"""Point the app at a throwaway SQLite database before anything imports it."""

import os
import tempfile

_TMP = tempfile.mkdtemp(prefix="debris-tests-")
os.environ["DATA_DIR"] = _TMP
os.environ["DATABASE_URL"] = f"sqlite:///{_TMP}/test.db"

from datetime import datetime, timezone  # noqa: E402

import pytest  # noqa: E402

from tests.fixtures import synthetic_catalogue  # noqa: E402


@pytest.fixture(scope="session")
def now():
    return datetime.now(timezone.utc).replace(tzinfo=None, microsecond=0)


@pytest.fixture(scope="session")
def loaded_db(now):
    """Run the real ingest pipeline, with the download replaced by synthetic TLE text."""
    from debris import celestrak, pipeline

    text = synthetic_catalogue(now)
    lines = text.strip().split("\n")
    by_group: dict[str, list[str]] = {}
    for i in range(0, len(lines), 3):
        name = lines[i]
        if "DEB" in name:
            group = name.split(" DEB")[0].lower() + "-debris"
        elif name.startswith("PAYLOAD"):
            group = "active"
        else:
            group = "stations"
        by_group.setdefault(group, []).append("\n".join(lines[i:i + 3]))

    original = celestrak.fetch_group
    celestrak.fetch_group = lambda group, force=False: "\n".join(by_group.get(group, []))
    try:
        df = pipeline.run()
    finally:
        celestrak.fetch_group = original
    return df
