import io
import tarfile

import pytest
import requests

from debris import celestrak, pipeline
from debris.config import SOURCE_FILE
from tests.conftest import load_synthetic
from tests.fixtures import synthetic_catalogue


def _tarball(files: dict[str, str]) -> bytes:
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        for name, text in files.items():
            data = text.encode()
            info = tarfile.TarInfo(f"raw/{name}.tle")
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
    return buf.getvalue()


class FakeResponse:
    def __init__(self, content):
        self.content = content

    def raise_for_status(self):
        pass


def test_fetch_snapshot_reads_requested_groups(monkeypatch):
    blob = _tarball({"stations": "ISS", "active": "SATS", "other": "X"})
    monkeypatch.setattr(celestrak.requests, "get", lambda *a, **k: FakeResponse(blob))
    assert celestrak.fetch_snapshot(["stations", "active"]) == {"stations": "ISS", "active": "SATS"}


def test_blocked_celestrak_falls_back_to_snapshot(loaded_db, now, monkeypatch):
    text = synthetic_catalogue(now)
    calls = []

    def blocked(group, force=False):
        calls.append(group)
        raise requests.ConnectionError("blocked")

    monkeypatch.setattr(celestrak, "fetch_group", blocked)
    monkeypatch.setattr(celestrak, "fetch_snapshot",
                        lambda groups: {g: text for g in groups if g == "stations"})
    try:
        df = pipeline.run()
        assert calls == ["fengyun-1c-debris"]          # stops trying after the first failure
        assert 25544 in set(df["norad_id"])
        assert "snapshot" in SOURCE_FILE.read_text()
    finally:
        monkeypatch.undo()
        load_synthetic(now)                            # restore the shared test database


def test_clear_error_when_everything_fails(monkeypatch):
    def fail(*a, **k):
        raise requests.ConnectionError("blocked")
    monkeypatch.setattr(celestrak, "fetch_group", fail)
    monkeypatch.setattr(celestrak, "fetch_snapshot", fail)
    with pytest.raises(RuntimeError, match="Snapshot"):
        pipeline.run()
