"""Orbits in motion: press play and watch objects move over the next few hours."""

from datetime import datetime

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from dashboard import common as c
from debris.config import DEFAULT_PRIMARY_NORAD

FRAMES = 180                     # more frames = smaller jumps between them = smoother motion
SPEEDS = {"Slow": 90, "Normal": 50, "Fast": 25}   # milliseconds per frame


@st.cache_data(ttl=300, show_spinner=False)
def simulate(types: tuple, orbit: str, count: int, minutes: int, follow: int | None,
             start_iso: str):
    objs = c.objects()
    pool = objs[objs["object_type"].isin(types) & (objs["orbit_class"] == orbit)]
    # A random sample caps how many points the browser has to draw.
    sample = pool.sample(min(count, len(pool)), random_state=0) if len(pool) else pool
    if follow is not None and follow not in set(sample["norad_id"]):
        # Make sure the highlighted object is included (it replaces one random object).
        sample = pd.concat([sample.iloc[:count - 1], objs[objs["norad_id"] == follow]])
    sample = sample.reset_index(drop=True)
    offsets = np.linspace(0, minutes * 60, FRAMES + 1)
    lat, lon, alt, ok = c.track(sample["tle_line1"], sample["tle_line2"],
                                datetime.fromisoformat(start_iso), offsets)
    lat[~ok], lon[~ok], alt[~ok] = np.nan, np.nan, np.nan
    x, y, z = c.to_xyz(lat, lon, alt)
    rnd = lambda a: np.round(a, 1)  # noqa: E731  (0.1 km precision keeps frames small)
    return (sample[["norad_id", "name", "object_type"]], rnd(lat), rnd(lon), rnd(x), rnd(y),
            rnd(z), offsets)


def controls(offsets, frame_ms: int) -> dict:
    play = dict(frame=dict(duration=frame_ms, redraw=True), transition=dict(duration=0),
                mode="immediate", fromcurrent=True)
    return dict(
        updatemenus=[dict(
            type="buttons", direction="left", x=0, y=0, xanchor="left", yanchor="top", active=-1, showactive=False,
            pad=dict(t=10, r=10), bgcolor=c.PANEL, bordercolor=c.GRID, font=dict(color=c.TEXT),
            buttons=[dict(label="▶  Play", method="animate", args=[None, play]),
                     dict(label="❚❚  Pause", method="animate",
                          args=[[None], dict(frame=dict(duration=0, redraw=False),
                                             mode="immediate")])])],
        sliders=[dict(
            x=0.18, y=0, len=0.8, xanchor="left", yanchor="top", pad=dict(t=10),
            currentvalue=dict(prefix="Time: ", font=dict(color=c.TEXT)),
            font=dict(color="rgba(0,0,0,0)"), bgcolor=c.PANEL, bordercolor=c.GRID,
            tickcolor="rgba(0,0,0,0)",
            steps=[dict(label=f"+{o / 60:.0f} min", method="animate",
                        args=[[str(k)], dict(frame=dict(duration=0, redraw=True),
                                             mode="immediate")])
                   for k, o in enumerate(offsets)])],
    )


def render() -> None:
    c.setup_page()
    objs = c.objects()
    st.title("Orbits in motion")
    st.caption("Press ▶ Play to watch objects move. You can drag and zoom the globe while it "
               "plays.")

    present = [o for o in c.ORBIT_CLASSES if o in set(objs["orbit_class"])]
    row1 = st.columns([2.1, 1.1, 1.5, 1.5])
    types = row1[0].pills("Objects", list(c.TYPE_LABELS), format_func=c.TYPE_LABELS.get,
                          selection_mode="multi", default=["PAYLOAD", "DEBRIS"], key="mo_types")
    orbit = row1[1].selectbox("Orbit regime", present,
                              index=present.index("LEO") if "LEO" in present else 0,
                              key="mo_orbit")
    count = row1[2].slider("How many objects", 100, 2000, 500, step=100, key="mo_count")
    minutes = row1[3].slider("Time span (minutes)", 30, 720 if orbit != "LEO" else 240,
                             90 if orbit == "LEO" else 360, step=30, key="mo_minutes")

    in_regime = objs[objs["orbit_class"] == orbit].sort_values("name")
    names = dict(zip(in_regime["norad_id"], in_regime["name"]))
    options = [None] + in_regime["norad_id"].tolist()
    default = options.index(DEFAULT_PRIMARY_NORAD) if DEFAULT_PRIMARY_NORAD in names else 0
    row2 = st.columns([2.6, 1.4, 1.4])
    follow = row2[0].selectbox("Highlight one object (its path is drawn)", options,
                               index=default, key=f"mo_follow_{orbit}",
                               format_func=lambda i: "None" if i is None else
                               f"{names[i]}  ·  {i}")
    speed = row2[1].segmented_control("Playback speed", list(SPEEDS), default="Normal",
                                      key="mo_speed") or "Normal"
    view = row2[2].segmented_control("View", ["3D", "Flat map"], default="3D",
                                     key="mo_view") or "3D"

    if not types:
        st.info("Pick at least one object type.")
        return

    start = c.utcnow().replace(second=0)
    with st.spinner("Calculating positions..."):
        sample, lat, lon, x, y, z, offsets = simulate(tuple(types), orbit, count, minutes,
                                                      follow, start.isoformat())
    if sample.empty:
        st.info("No objects match these filters.")
        return

    kinds = sample["object_type"].to_numpy()
    groups = [(k, np.where((kinds == k) & (sample["norad_id"].to_numpy() != follow))[0])
              for k in types]
    groups = [(k, idx) for k, idx in groups if len(idx)]
    hi = np.where(sample["norad_id"].to_numpy() == follow)[0] if follow is not None else []
    three_d = view == "3D"

    def dots(k: int, full: bool):
        """Traces for frame k. Frames after the first carry positions only (much lighter)."""
        out = []
        for kind, idx in groups:
            if three_d:
                trace = go.Scatter3d(x=x[idx, k], y=y[idx, k], z=z[idx, k])
            else:
                trace = go.Scattergeo(lat=lat[idx, k], lon=lon[idx, k])
            if full:
                trace.update(mode="markers", text=sample["name"].iloc[idx],
                             name=f"{c.TYPE_LABELS[kind]} ({len(idx):,})",
                             hovertemplate="%{text}<extra></extra>",
                             marker=dict(size=2.4 if three_d else 4,
                                         color=c.TYPE_COLORS[kind], opacity=0.9))
            out.append(trace)
        if len(hi):
            i = hi[0]
            if three_d:
                trace = go.Scatter3d(x=[x[i, k]], y=[y[i, k]], z=[z[i, k]])
            else:
                trace = go.Scattergeo(lat=[lat[i, k]], lon=[lon[i, k]])
            if full:
                trace.update(mode="markers+text", text=[sample["name"].iloc[i]],
                             name=sample["name"].iloc[i], textposition="top center",
                             textfont=dict(color=c.TEXT), hoverinfo="text",
                             marker=dict(size=8 if three_d else 11, color="#FFFFFF",
                                         line=dict(color="#F2B544", width=3)))
            out.append(trace)
        return out

    static = c.earth_traces(grid=False) if three_d else []
    if len(hi):   # the highlighted object's whole path, drawn once
        i = hi[0]
        path_style = dict(mode="lines", hoverinfo="skip", showlegend=False,
                          line=dict(color="rgba(242,181,68,0.55)", width=3))
        if three_d:
            static.append(go.Scatter3d(x=x[i], y=y[i], z=z[i], **path_style))
        else:
            from dashboard.views.explorer import break_at_dateline
            plat, plon = break_at_dateline(lat[i], lon[i])
            static.append(go.Scattergeo(lat=plat, lon=plon, **path_style))

    first = len(static)
    moving = list(range(first, first + len(groups) + (1 if len(hi) else 0)))
    fig = go.Figure(static + dots(0, full=True))
    fig.frames = [go.Frame(data=dots(k, full=False), name=str(k), traces=moving)
                  for k in range(len(offsets))]
    if three_d:
        extent = 8200 if orbit == "LEO" else min(46000, float(np.nanmax(np.abs(x))) * 1.15)
        c.globe_layout(fig, extent, height=640, revision=f"motion-{orbit}")
    else:
        c.geo_style(fig, height=600)
        fig.update_layout(hoverlabel=c.HOVERLABEL)
    fig.update_layout(**controls(offsets, SPEEDS[speed]))
    fig.update_layout(margin=dict(l=0, r=0, t=0, b=70))
    st.plotly_chart(fig, width="stretch", config=c.PLOTLY_CONFIG)
    st.caption(f"{len(sample):,} randomly chosen {orbit} objects from {start:%H:%M} UTC, one "
               f"frame every {minutes * 60 / FRAMES:.0f} seconds of orbit time. Low orbits "
               "circle Earth in about 90 minutes; geostationary satellites stay over one spot.")
