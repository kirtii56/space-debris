"""Streamlit dashboard.  Run from the project root:  streamlit run dashboard/app.py"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))  # make the project importable

import streamlit as st  # noqa: E402


def reload_if_code_changed() -> None:
    """Keep all project modules on the same version after an update.

    When new code is pulled while the app is running (Streamlit Cloud does this on every
    push), Streamlit re-runs this file but can keep old copies of the modules it imports,
    mixing two versions. If any project file changed since the last run, drop them all so
    they are imported fresh, and clear cached results built by the old code.
    """
    files = [*ROOT.glob("debris/**/*.py"), *ROOT.glob("dashboard/**/*.py")]
    fingerprint = max((f.stat().st_mtime for f in files), default=0)
    previous = getattr(sys, "_space_debris_code_version", None)
    if previous is not None and fingerprint != previous:
        for name in [m for m in sys.modules if m.split(".")[0] in ("debris", "dashboard")]:
            del sys.modules[name]
        st.cache_data.clear()
    sys._space_debris_code_version = fingerprint


reload_if_code_changed()
st.set_page_config(page_title="Space Debris Tracker", page_icon="🛰️", layout="wide")

from dashboard import common  # noqa: E402
from dashboard.views import approaches, clusters, explorer, motion, overview  # noqa: E402


def ensure_data() -> None:
    """On first start (for example on Streamlit Community Cloud) fetch live data automatically."""
    if not common.objects().empty:
        return
    from debris import conjunctions, pipeline
    from debris.ml import clustering

    common.setup_page()
    st.title("Space debris tracker")
    try:
        with st.spinner("Downloading live data from CelesTrak and running the analysis. "
                        "This takes about a minute on first start."):
            pipeline.run()
            conjunctions.run()
            clustering.run()
    except Exception as exc:
        st.error(f"Could not load live data ({exc}) Check the internet connection, or run "
                 "`python -m debris.cli all` in a terminal, then refresh this page.")
        st.stop()
    st.cache_data.clear()
    st.rerun()


ensure_data()

common.PAGES.update({
    "overview": st.Page(overview.render, title="Overview", icon=":material/public:",
                        url_path="overview", default=True),
    "explorer": st.Page(explorer.render, title="Satellite explorer", icon=":material/search:",
                        url_path="explorer"),
    "motion": st.Page(motion.render, title="Orbits in motion", icon=":material/play_circle:",
                      url_path="motion"),
    "approaches": st.Page(approaches.render, title="Close approaches",
                          icon=":material/warning:", url_path="close-approaches"),
    "clusters": st.Page(clusters.render, title="Debris clusters",
                        icon=":material/scatter_plot:", url_path="clusters"),
})
page = st.navigation(list(common.PAGES.values()), position="top")
page.run()
