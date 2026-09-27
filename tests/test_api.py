from fastapi.testclient import TestClient

from api.main import app
from debris import conjunctions

client = TestClient(app)


def test_health(loaded_db):
    assert client.get("/health").json()["objects"] == len(loaded_db)


def test_objects_filter_and_404(loaded_db):
    rows = client.get("/objects", params={"object_type": "debris", "limit": 5}).json()
    assert len(rows) == 5 and all(r["object_type"] == "DEBRIS" for r in rows)
    assert client.get("/objects/1").status_code == 404


def test_position(loaded_db):
    body = client.get("/objects/25544/position").json()
    assert 380 < body["altitude_km"] < 450
    assert -52 < body["latitude_deg"] < 52


def test_conjunctions_endpoint(loaded_db, now):
    conjunctions.run(25544, start=now, hours=6)
    rows = client.get("/conjunctions", params={"primary": 25544}).json()
    assert rows and rows[0]["secondary_name"] == "TEST VISITOR"
    assert rows[0]["risk_level"] in {"LOW", "MEDIUM", "HIGH"}
