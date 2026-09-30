"""Streamlit dashboard.  Run from the project root:  streamlit run dashboard/app.py"""

import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # make `debris` importable

import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st

from debris import db
from debris.collision import risk_level
from debris.ml.clustering import load_metrics
from debris.propagator import propagate_many, teme_to_geodetic, time_grid

AMBER, SKY, SLATE, ROSE = "#F2B544", "#5FA8D3", "#8A9BB0", "#E0707A"
TYPE_COLORS = {"PAYLOAD": SKY, "DEBRIS": AMBER, "ROCKET BODY": ROSE}
PLOT_LAYOUT = dict(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                   font_color="#E6ECF2", margin=dict(l=10, r=10, t=40, b=10))

st.set_page_config(page_title="Space Debris Tracker", page_icon="🛰️", layout="wide")


@st.cache_data(ttl=600)
def load(sql: str) -> pd.DataFrame:
    return db.query_df(sql)


def styled(fig):
    fig.update_layout(**PLOT_LAYOUT)
    return fig


def load_objects() -> pd.DataFrame:
    try:
        return load("SELECT * FROM objects")
    except Exception:
        return pd.DataFrame()


st.title("Space debris tracker")
objects = load_objects()
if objects.empty:
    # First start (for example on Streamlit Community Cloud): fetch live data automatically.
    from debris import conjunctions, pipeline
    from debris.ml import clustering

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
    load.clear()
    objects = load_objects()

objects["epoch"] = pd.to_datetime(objects["epoch"])
st.caption(f"{len(objects):,} objects from CelesTrak · newest TLE "
           f"{objects['epoch'].max():%d %b %Y %H:%M} UTC")

overview, now_tab, close_tab, cluster_tab = st.tabs(
    ["Overview", "Where they are now", "Close approaches", "Breakup clusters"])

# ---------------------------------------------------------------- Overview
with overview:
    counts = objects["object_type"].value_counts()
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Objects tracked", f"{len(objects):,}")
    c2.metric("Debris fragments", f"{counts.get('DEBRIS', 0):,}")
    c3.metric("Payloads", f"{counts.get('PAYLOAD', 0):,}")
    c4.metric("In low Earth orbit", f"{(objects['orbit_class'] == 'LEO').mean():.0%}")

    density = load("SELECT * FROM v_altitude_density ORDER BY altitude_band_km")
    density = density[density["altitude_band_km"] <= 2000].melt(
        id_vars="altitude_band_km", value_vars=["debris_count", "payload_count"],
        var_name="kind", value_name="objects")
    density["kind"] = density["kind"].map({"debris_count": "DEBRIS", "payload_count": "PAYLOAD"})
    st.plotly_chart(styled(px.bar(
        density, x="altitude_band_km", y="objects", color="kind", color_discrete_map=TYPE_COLORS,
        title="How crowded each altitude is (LEO, by perigee)",
        labels={"altitude_band_km": "Perigee altitude band (km)", "kind": ""})),
        width="stretch")

    left, right = st.columns(2)
    by_orbit = load("SELECT * FROM v_summary_by_orbit")
    left.plotly_chart(styled(px.bar(
        by_orbit, x="orbit_class", y="object_count", color="object_type",
        color_discrete_map=TYPE_COLORS, title="Objects by orbit regime",
        labels={"orbit_class": "", "object_count": "Objects", "object_type": ""})),
        width="stretch")

    leo = objects[objects["orbit_class"] == "LEO"]
    sample = leo.sample(min(len(leo), 4000), random_state=0)
    right.plotly_chart(styled(px.scatter(
        sample, x="inclination_deg", y="perigee_km", color="object_type",
        color_discrete_map=TYPE_COLORS, opacity=0.6, hover_name="name",
        title="Inclination vs altitude (LEO sample)",
        labels={"inclination_deg": "Inclination (°)", "perigee_km": "Perigee (km)",
                "object_type": ""})), width="stretch")

    st.subheader("Breakup events in the catalogue")
    st.dataframe(load("SELECT * FROM v_breakup_events").round(1), hide_index=True,
                 width="stretch")

# ---------------------------------------------------------------- Where they are now
with now_tab:
    kinds = st.multiselect("Show", ["PAYLOAD", "DEBRIS", "ROCKET BODY"],
                           default=["PAYLOAD", "DEBRIS"])
    subset = objects[objects["object_type"].isin(kinds)]
    subset = subset.sample(min(len(subset), 3000), random_state=1)
    if subset.empty:
        st.info("Pick at least one object type to show.")
    else:
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        jd, fr = time_grid(now, np.array([0.0]))
        r, _, ok = propagate_many(subset["tle_line1"], subset["tle_line2"], jd, fr)
        lat, lon, alt = teme_to_geodetic(r[:, 0, :], jd[0] + fr[0])
        pos = subset.assign(lat=lat, lon=lon, altitude_km=alt)[ok[:, 0]]
        fig = px.scatter_geo(pos, lat="lat", lon="lon", color="object_type",
                             color_discrete_map=TYPE_COLORS, hover_name="name",
                             hover_data={"altitude_km": ":.0f", "lat": False, "lon": False},
                             title=f"Positions at {now:%H:%M} UTC (up to 3,000 objects)")
        fig.update_traces(marker=dict(size=4))
        fig.update_geos(projection_type="natural earth", showland=True, landcolor="#1F3350",
                        showocean=True, oceancolor="#0E1A2B", bgcolor="rgba(0,0,0,0)",
                        coastlinecolor=SLATE)
        st.plotly_chart(styled(fig), width="stretch")
        st.caption("Positions from SGP4. Refresh the page to update.")

# ---------------------------------------------------------------- Close approaches
with close_tab:
    conj = load("SELECT * FROM v_conjunctions_detail ORDER BY tca")
    if conj.empty:
        st.info("No screening results yet. Run `python -m debris.cli screen --primary 25544`.")
    else:
        conj["tca"] = pd.to_datetime(conj["tca"])
        conj["risk"] = conj["collision_probability"].map(risk_level)
        primary_name = conj["primary_name"].iloc[0]
        c1, c2, c3 = st.columns(3)
        c1.metric("Close approaches", len(conj))
        c2.metric("Closest miss", f"{conj['miss_distance_km'].min():.2f} km")
        c3.metric("Objects involved", conj["secondary_norad"].nunique())
        st.plotly_chart(styled(px.scatter(
            conj, x="tca", y="miss_distance_km", color="secondary_type",
            color_discrete_map=TYPE_COLORS, hover_name="secondary_name",
            size=np.clip(conj["relative_velocity_km_s"], 0.5, None),
            title=f"Close approaches to {primary_name} in the next 24 hours",
            labels={"tca": "Time of closest approach (UTC)", "miss_distance_km": "Miss distance (km)",
                    "secondary_type": ""})), width="stretch")
        st.dataframe(
            conj[["tca", "secondary_name", "secondary_type", "miss_distance_km",
                  "relative_velocity_km_s", "collision_probability", "risk"]],
            hide_index=True, width="stretch",
            column_config={
                "tca": st.column_config.DatetimeColumn("Closest approach (UTC)",
                                                       format="DD MMM HH:mm:ss"),
                "miss_distance_km": st.column_config.NumberColumn("Miss (km)", format="%.2f"),
                "relative_velocity_km_s": st.column_config.NumberColumn("Rel. speed (km/s)",
                                                                        format="%.2f"),
                "collision_probability": st.column_config.NumberColumn("Pc (estimate)",
                                                                       format="%.1e"),
            })
        st.caption("Pc assumes a 1 km position uncertainty because public TLEs have no "
                   "covariance data. Use it to rank events, not as an operational number.")

# ---------------------------------------------------------------- Breakup clusters
with cluster_tab:
    metrics = load_metrics()
    clusters = load("SELECT c.cluster_id, o.* FROM debris_clusters c "
                    "JOIN objects o ON o.norad_id = c.norad_id")
    if clusters.empty or not metrics:
        st.info("No clustering results yet. Run `python -m debris.cli cluster`.")
    else:
        st.write("DBSCAN groups debris by inclination, mean motion and eccentricity without "
                 "being told which breakup each fragment came from. The scores compare its "
                 "groups with the true events.")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Clusters found", f"{metrics['clusters_found']} of {metrics['true_events']}")
        c2.metric("Adjusted Rand index", f"{metrics['adjusted_rand_index']:.2f}")
        c3.metric("Homogeneity", f"{metrics['homogeneity']:.2f}")
        c4.metric("Left unclustered", f"{metrics['noise_fraction']:.0%}")

        clusters["cluster"] = clusters["cluster_id"].map(
            lambda c: "Noise" if c == -1 else f"Cluster {c}")
        st.plotly_chart(styled(px.scatter(
            clusters, x="inclination_deg", y="mean_motion_rev_day", color="cluster",
            symbol="source_group", hover_name="name", opacity=0.7,
            title="Debris coloured by DBSCAN cluster, shaped by true breakup event",
            labels={"inclination_deg": "Inclination (°)",
                    "mean_motion_rev_day": "Mean motion (rev/day)", "cluster": "",
                    "source_group": "True event"})), width="stretch")
        st.subheader("Which cluster matched which event")
        st.dataframe(pd.crosstab(clusters["source_group"], clusters["cluster"]),
                     width="stretch")
