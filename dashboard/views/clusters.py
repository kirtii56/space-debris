"""Debris clusters: tune DBSCAN live and see how well it rediscovers breakup events."""

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from sklearn.preprocessing import StandardScaler

from dashboard import common as c
from debris.config import EVENT_NAMES
from debris.ml import clustering

FEATURE_LABELS = {
    "inclination_deg": "Inclination",
    "mean_motion_rev_day": "Mean motion (orbits/day)",
    "eccentricity": "Eccentricity",
    "raan_deg": "RAAN (orbit plane angle)",
    "arg_perigee_deg": "Argument of perigee",
    "perigee_km": "Perigee altitude",
    "apogee_km": "Apogee altitude",
}


@st.cache_data(ttl=600, show_spinner=False)
def debris() -> pd.DataFrame:
    df = clustering.load_debris()
    return df.assign(event=df["source_group"].map(EVENT_NAMES).fillna(df["source_group"]))


@st.cache_data(ttl=600, show_spinner=False)
def auto_eps(features: tuple, min_samples: int) -> float:
    X = StandardScaler().fit_transform(debris()[list(features)])
    return clustering.suggest_eps(X, min_samples)


@st.cache_data(ttl=600, show_spinner=False)
def k_distance_curve(features: tuple, min_samples: int) -> np.ndarray:
    X = StandardScaler().fit_transform(debris()[list(features)])
    return clustering.k_distances(X, min_samples)


@st.cache_data(ttl=600, show_spinner=False)
def run(features: tuple, eps: float, min_samples: int):
    return clustering.cluster(debris(), eps, min_samples, list(features))


def render() -> None:
    c.setup_page()
    st.title("Debris clusters")
    df = debris()
    if len(df) < 20:
        st.info("Not enough debris fragments loaded to cluster. Run `python -m debris.cli all`.")
        return

    st.write("When a satellite explodes or collides, its fragments start in almost the same "
             "orbit. **DBSCAN** groups fragments with similar orbits *without being told which "
             "event they came from*. The scores compare its groups with the real events. "
             "Move the controls and watch what happens.")

    ctrl, _, scores = st.columns([1.25, 0.05, 2])
    with ctrl:
        features = st.multiselect("Features the model uses", list(FEATURE_LABELS),
                                  default=clustering.FEATURES, format_func=FEATURE_LABELS.get,
                                  key="cl_features")
        if not features:
            st.warning("Pick at least one feature.")
            return
        min_samples = st.slider("min_samples: fragments needed to form a cluster", 3, 40, 10,
                                key="cl_min_samples")
        suggested = auto_eps(tuple(features), min_samples)
        auto = st.toggle(f"Choose eps automatically ({suggested:.2f})", value=True,
                         key="cl_auto")
        eps = st.slider("eps: how close fragments must be (in standard deviations)", 0.02,
                        2.0, float(round(min(max(suggested, 0.02), 2.0), 2)), step=0.01,
                        disabled=auto, key="cl_eps")
        eps = suggested if auto else eps

    labels, metrics = run(tuple(features), round(float(eps), 4), min_samples)
    df = df.assign(cluster=np.where(labels == -1, "No cluster", np.char.add("Cluster ", labels.astype(str))))

    with scores:
        a, b, d = st.columns(3)
        a.metric("Clusters found", metrics["clusters_found"],
                 f"{metrics['clusters_found'] - metrics['true_events']:+d} vs "
                 f"{metrics['true_events']} real events", delta_color="off")
        b.metric("Adjusted Rand index", f"{metrics['adjusted_rand_index']:.2f}",
                 help="Agreement with the real events. 1 = perfect, 0 = no better than random.")
        d.metric("Left unclustered", f"{metrics['noise_fraction']:.0%}",
                 help="Fragments DBSCAN treats as noise because too few neighbours are close.")
        a.metric("Homogeneity", f"{metrics['homogeneity']:.2f}",
                 help="1 = every cluster contains fragments from only one event.")
        b.metric("Completeness", f"{metrics['completeness']:.2f}",
                 help="1 = each event's fragments all ended up in one cluster.")
        d.metric("Silhouette", f"{metrics.get('silhouette', float('nan')):.2f}",
                 help="How well separated the clusters are, from -1 to 1. Does not use the "
                      "real labels.")

    order = sorted(df["cluster"].unique(), key=lambda s: (s == "No cluster", len(s), s))
    colors = {name: c.CLUSTER_PALETTE[i % len(c.CLUSTER_PALETTE)] for i, name in
              enumerate(k for k in order if k != "No cluster")}
    colors["No cluster"] = "#5B6B80"

    left, right = st.columns([3, 2], gap="large")
    with left:
        axes = (features + [f for f in clustering.FEATURES if f not in features])[:3]
        fig = px.scatter_3d(df, x=axes[0], y=axes[1], z=axes[2], color="cluster",
                            category_orders={"cluster": order}, color_discrete_map=colors,
                            hover_name="name", hover_data={"event": True, "cluster": False},
                            labels={**FEATURE_LABELS, "cluster": "", "event": "Real event"})
        fig.update_traces(marker=dict(size=2.2))
        fig.update_layout(height=560, uirevision="clusters", paper_bgcolor="rgba(0,0,0,0)",
                          font_color=c.TEXT, margin=dict(l=0, r=0, t=10, b=0),
                          legend=dict(itemsizing="constant", bgcolor="rgba(0,0,0,0)"),
                          scene=dict(bgcolor="rgba(0,0,0,0)",
                                     **{k: dict(gridcolor=c.GRID, color=c.MUTED,
                                                backgroundcolor="rgba(0,0,0,0)")
                                        for k in ("xaxis", "yaxis", "zaxis")}))
        st.plotly_chart(fig, width="stretch", config=c.PLOTLY_CONFIG)
        st.caption("Each dot is one fragment, coloured by the cluster DBSCAN put it in. Hover "
                   "to see which event it really came from.")
    with right:
        table = pd.crosstab(df["event"], df["cluster"]).reindex(columns=order)
        heat = px.imshow(table, text_auto=True, aspect="auto",
                         color_continuous_scale=[[0, c.PANEL], [1, "#F2B544"]],
                         labels=dict(x="", y="", color="Fragments"),
                         title="Real event vs DBSCAN cluster")
        heat.update_coloraxes(showscale=False)
        st.plotly_chart(c.style(heat, height=330), width="stretch", config=c.PLOTLY_CONFIG)
        st.caption("A perfect result has one bright cell per row and per column.")

        k_dist = k_distance_curve(tuple(features), min_samples)
        curve = go.Figure(go.Scatter(y=k_dist, mode="lines", line=dict(color="#5FA8D3"),
                                     hovertemplate="%{y:.3f}<extra></extra>"))
        curve.add_hline(y=eps, line_dash="dot", line_color="#F2B544",
                        annotation_text=f"eps = {eps:.2f}", annotation_font_color="#F2B544")
        curve.update_layout(title="How eps is chosen (k-distance plot)",
                            xaxis_title="Fragments, sorted", showlegend=False,
                            yaxis_title=f"Distance to {min_samples}th neighbour")
        st.plotly_chart(c.style(curve, height=260), width="stretch", config=c.PLOTLY_CONFIG)
        st.caption("The automatic eps sits at the bend: below it, points are in dense groups; "
                   "above it, they are isolated.")

    with st.expander("Things to try"):
        st.markdown(
            "- **Add RAAN as a feature.** Scores usually drop. Earth's bulge slowly rotates "
            "each fragment's orbital plane at a different rate, so after a few years fragments "
            "from one event no longer share a RAAN. Choosing features needs domain knowledge.\n"
            "- **Make eps very small.** Almost everything becomes noise.\n"
            "- **Make eps very large.** Separate events merge into one cluster.\n"
            "- **Use only inclination.** Often enough on its own, because each event happened "
            "in a different orbital plane.")
