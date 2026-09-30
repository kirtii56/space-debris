import json

from debris import report
from debris.ml import clustering


def test_report_writes_results_and_readme(loaded_db, tmp_path, monkeypatch):
    clustering.run()
    readme = tmp_path / "README.md"
    readme.write_text("# Title\n\n## Tech stack\n\nstuff\n")
    monkeypatch.setattr(report, "RESULTS_DIR", tmp_path / "results")
    monkeypatch.setattr(report, "README", readme)

    summary = report.build()
    assert summary["objects_tracked"] == len(loaded_db)
    for name in ["altitude_density.png", "debris_clusters.png", "summary.json", "RESULTS.md",
                 "iss_close_approaches.csv"]:
        assert (tmp_path / "results" / name).exists()
    assert json.loads((tmp_path / "results" / "summary.json").read_text())["clustering"]

    text = readme.read_text()
    assert text.index("## Results") < text.index("## Tech stack")
    report.build()  # running again replaces the section instead of adding a second one
    assert readme.read_text().count(report.START) == 1
