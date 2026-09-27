from debris import db
from debris.ml import clustering


def test_ingest_loads_and_deduplicates(loaded_db):
    counts = db.query_df("SELECT source_group, COUNT(*) AS n FROM objects GROUP BY source_group")
    counts = dict(zip(counts["source_group"], counts["n"]))
    assert counts["stations"] == 2
    assert counts["fengyun-1c-debris"] == 60
    assert db.query_df("SELECT COUNT(*) AS n FROM objects")["n"].iloc[0] == len(loaded_db)


def test_sql_views_work(loaded_db):
    by_type = db.query_df("SELECT * FROM v_summary_by_type")
    assert set(by_type["object_type"]) == {"DEBRIS", "PAYLOAD"}
    events = db.query_df("SELECT * FROM v_breakup_events")
    assert len(events) == 4 and (events["fragments_tracked"] == 60).all()


def test_dbscan_recovers_breakup_events(loaded_db):
    metrics = clustering.run()
    assert metrics["clusters_found"] == 4
    assert metrics["adjusted_rand_index"] > 0.8
    stored = db.query_df("SELECT COUNT(*) AS n FROM debris_clusters")["n"].iloc[0]
    assert stored == metrics["fragments"]
