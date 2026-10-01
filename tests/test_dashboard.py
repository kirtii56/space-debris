"""Render every dashboard page headlessly and exercise its main controls."""

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from debris import conjunctions
from debris.ml import clustering

ROOT = str(Path(__file__).resolve().parent.parent)


def page(name: str) -> AppTest:
    script = (f"import sys\nsys.path.insert(0, {ROOT!r})\n"
              f"from dashboard.views import {name}\n{name}.render()\n")
    return AppTest.from_string(script, default_timeout=120)


@pytest.fixture(scope="module")
def analysed(loaded_db, now):
    conjunctions.run(25544, start=now, hours=6)
    clustering.run()


@pytest.mark.parametrize("name", ["overview", "explorer", "motion", "approaches", "clusters"])
def test_page_renders(analysed, name):
    at = page(name).run()
    assert not at.exception, at.exception


def test_explorer_search(analysed):
    at = page("explorer").run()
    at.selectbox(key="ex_object").set_value(90001).run()
    assert not at.exception
    assert at.subheader[0].value == "TEST VISITOR"


def test_clusters_sliders(analysed):
    at = page("clusters").run()
    at.toggle(key="cl_auto").set_value(False).run()
    at.slider(key="cl_eps").set_value(0.05).run()
    assert not at.exception
    noise = next(m for m in at.metric if m.label == "Left unclustered").value
    assert int(noise.rstrip("%")) > 50          # tiny eps: most fragments become noise


def test_motion_flat_map(analysed):
    at = page("motion").run()
    at.segmented_control(key="mo_view").set_value("Flat map").run()
    assert not at.exception


def test_app_entry_point(analysed):
    at = AppTest.from_file(f"{ROOT}/dashboard/app.py", default_timeout=120).run()
    assert not at.exception
    assert at.title[0].value == "Space debris tracker"


def test_clicked_reads_point_without_customdata():
    """Streamlit's click payload may lack customdata; the helper must use the figure instead."""
    import plotly.graph_objects as go

    from dashboard import common as c

    class Event:
        class selection:  # noqa: N801
            points = [{"curve_number": 1, "point_index": 2}]   # no "customdata" key

    fig = go.Figure([go.Scatter(x=[0], y=[0]),
                     go.Scatter(x=[1, 2, 3], y=[1, 2, 3], customdata=[[10], [11], [12]])])
    assert c.clicked(Event, fig)[0] == 12
    assert c.clicked(None, fig) is None


def test_app_survives_code_update_while_running(analysed):
    """Simulates a deploy: a module changes on disk between two runs of the same app."""
    import os
    import time

    from dashboard import common as c

    at = AppTest.from_file(f"{ROOT}/dashboard/app.py", default_timeout=120).run()
    assert not at.exception
    stale = __import__("sys").modules["dashboard.common"]
    stale.PAGES = None                            # pretend the loaded copy is an old version
    os.utime(c.__file__, (time.time() + 5, time.time() + 5))   # file on disk is "newer"
    at.run()
    assert not at.exception, at.exception
