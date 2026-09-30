"""Orbits in motion: press play and watch objects move over the next few hours."""

from datetime import datetime

import numpy as np
import plotly.graph_objects as go
import streamlit as st

from dashboard import common as c

FRAMES = 60


@st.cache_data(ttl=300, show_spinner=False)
def simulate(types: tuple, orbit: str, count: int, minutes: int, start_iso: str):
    objs = c.objects()
    pool = objs[objs["object_type"].isin(types) & (objs["orbit_class"] == orbit)]
    # A random sample caps how many points the browser has to draw.
    sample = pool.sample(min(count, len(pool)), random_state=0) if len(pool) else pool
    offsets = np.linspace(0, minutes * 60, FRAMES + 1)
    lat, lon, alt, ok = c.track(sample["tle_line1"], sample["tle_line2"],
                                datetime.fromisoformat(start_iso), offsets)
    lat[~ok], lon[~ok], alt[~ok] = np.nan, np.nan, np.nan
    return sample[["name", "object_type"]].reset_index(drop=True), lat, lon, alt, offsets


def animation_controls(offsets) -> dict:
    frame_args = dict(frame=dict(duration=110, redraw=True), transition=dict(duration=0),
                      mode="immediate", fromcurrent=True)
    return dict(
        updatemenus=[dict(
            type="buttons", direction="left", x=0, y=0, xanchor="left", yanchor="top", active=-1,
            pad=dict(t=10, r=10), bgcolor=c.PANEL, bordercolor=c.GRID, font=dict(color=c.TEXT),
            buttons=[dict(label="▶  Play", method="animate", args=[None, frame_args]),
                     dict(label="❚❚  Pause", method="animate",
                          args=[[None], dict(frame=dict(duration=0, redraw=False),
                                             mode="immediate")])])],
        sliders=[dict(
            x=0.18, y=0, len=0.8, xanchor="left", yanchor="top", pad=dict(t=10),
            currentvalue=dict(prefix="Time: ", font=dict(color=c.TEXT)),
            font=dict(color="rgba(0,0,0,0)"), bgcolor=c.PANEL, bordercolor=c.GRID,  # hide tick labels
            steps=[dict(label=f"+{o / 60:.0f} min", method="animate",
                        args=[[str(k)], dict(frame=dict(duration=0, redraw=True),
                                             mode="immediate")])
                   for k, o in enumerate(offsets)])],
    )


def render() -> None:
    c.setup_page()
    objs = c.objects()
    st.title("Orbits in motion")
    st.caption("Press ▶ Play to watch objects move. You can drag the globe while it plays.")

    present = [o for o in c.ORBIT_CLASSES if o in set(objs["orbit_class"])]
    col1, col2, col3, col4, col5 = st.columns([2.1, 1.1, 1.5, 1.5, 1.1])
    types = col1.pills("Objects", list(c.TYPE_LABELS), format_func=c.TYPE_LABELS.get,
                       selection_mode="multi", default=["PAYLOAD", "DEBRIS"], key="mo_types")
    orbit = col2.selectbox("Orbit regime", present,
                           index=present.index("LEO") if "LEO" in present else 0, key="mo_orbit")
    count = col3.slider("How many objects", 100, 3000, 800, step=100, key="mo_count")
    minutes = col4.slider("Time span (minutes)", 30, 720 if orbit != "LEO" else 240,
                          90 if orbit == "LEO" else 360, step=30, key="mo_minutes")
    view = col5.segmented_control("View", ["3D", "Flat map"], default="3D",
                                  key="mo_view") or "3D"

    if not types:
        st.info("Pick at least one object type.")
        return

    start = c.utcnow().replace(second=0)
    with st.spinner("Calculating positions..."):
        sample, lat, lon, alt, offsets = simulate(tuple(types), orbit, count, minutes,
                                                  start.isoformat())
    if sample.empty:
        st.info("No objects match these filters.")
        return

    groups = [(k, np.where(sample["object_type"].to_numpy() == k)[0]) for k in types]
    groups = [(k, idx) for k, idx in groups if len(idx)]

    if view == "3D":
        x, y, z = c.to_xyz(lat, lon, alt)
        base = c.earth_traces()
        first = len(base)

        def traces(k):
            return [go.Scatter3d(x=x[idx, k], y=y[idx, k], z=z[idx, k], mode="markers",
                                 text=sample["name"].iloc[idx],
                                 name=f"{c.TYPE_LABELS[kind]} ({len(idx):,})",
                                 hovertemplate="%{text}<extra></extra>",
                                 marker=dict(size=2.4, color=c.TYPE_COLORS[kind]))
                    for kind, idx in groups]

        fig = go.Figure(base + traces(0))
        fig.frames = [go.Frame(data=traces(k), name=str(k),
                               traces=list(range(first, first + len(groups))))
                      for k in range(len(offsets))]
        extent = 8200 if orbit == "LEO" else min(46000, float(np.nanmax(alt)) * 1.15 + 6378)
        c.globe_layout(fig, extent, height=640, revision=f"motion-{orbit}")
    else:
        def traces(k):
            return [go.Scattergeo(lat=lat[idx, k], lon=lon[idx, k], mode="markers",
                                  text=sample["name"].iloc[idx],
                                  name=f"{c.TYPE_LABELS[kind]} ({len(idx):,})",
                                  hovertemplate="%{text}<extra></extra>",
                                  marker=dict(size=4, color=c.TYPE_COLORS[kind]))
                    for kind, idx in groups]

        fig = go.Figure(traces(0))
        fig.frames = [go.Frame(data=traces(k), name=str(k), traces=list(range(len(groups))))
                      for k in range(len(offsets))]
        c.geo_style(fig, height=600)

    fig.update_layout(**animation_controls(offsets))
    fig.update_layout(margin=dict(l=0, r=0, t=0, b=70))
    st.plotly_chart(fig, width="stretch", config=c.PLOTLY_CONFIG)
    st.caption(f"{len(sample):,} randomly chosen {orbit} objects, from {start:%H:%M} UTC. "
               "Low orbits circle Earth in about 90 minutes; geostationary satellites stay "
               "over one spot.")
