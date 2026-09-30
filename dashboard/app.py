"""Streamlit dashboard.  Run from the project root:  streamlit run dashboard/app.py"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # make the project importable

import streamlit as st  # noqa: E402

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

page = st.navigation([
    st.Page(overview.render, title="Overview", icon=":material/public:", url_path="overview",
            default=True),
    st.Page(explorer.render, title="Satellite explorer", icon=":material/search:",
            url_path="explorer"),
    st.Page(motion.render, title="Orbits in motion", icon=":material/play_circle:",
            url_path="motion"),
    st.Page(approaches.render, title="Close approaches", icon=":material/warning:",
            url_path="close-approaches"),
    st.Page(clusters.render, title="Debris clusters", icon=":material/scatter_plot:",
            url_path="clusters"),
], position="top")
page.run()
