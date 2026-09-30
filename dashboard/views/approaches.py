"""Close approaches: pick an event on the timeline and replay the flyby."""

from datetime import timedelta

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from dashboard import common as c
from debris.collision import risk_level
from debris.propagator import propagate_one, time_grid

RISK_COLORS = {"HIGH": "#E0707A", "MEDIUM": "#F2B544", "LOW": "#7CC47F"}


def relative_motion(primary: pd.Series, secondary: pd.Series, tca, rel_speed: float):
    """Secondary's position relative to the primary in the primary's RIC frame.

    RIC = radial (away from Earth), in-track (direction of travel), cross-track (sideways).
    This is the view conjunction analysts use: the primary sits still at the centre.
    """
    half = float(np.clip(150 / max(rel_speed, 1e-3), 20, 900))   # show roughly ±150 km of path
    start = tca - timedelta(seconds=half)
    t = np.linspace(0, 2 * half, 241)
    jd, fr = time_grid(start, t)
    rp, vp, okp = propagate_one(primary["tle_line1"], primary["tle_line2"], jd, fr)
    rs, _, oks = propagate_one(secondary["tle_line1"], secondary["tle_line2"], jd, fr)
    radial = rp / np.linalg.norm(rp, axis=1, keepdims=True)
    cross = np.cross(rp, vp)
    cross /= np.linalg.norm(cross, axis=1, keepdims=True)
    in_track = np.cross(cross, radial)
    d = rs - rp
    ric = np.stack([(d * radial).sum(1), (d * in_track).sum(1), (d * cross).sum(1)], axis=1)
    ok = okp & oks
    return t[ok] - half, ric[ok]


def replay_figure(t, ric, primary_name, secondary_name, color) -> go.Figure:
    dist = np.linalg.norm(ric, axis=1)
    k0 = int(np.argmin(dist))
    lim = float(np.abs(ric).max()) * 1.05
    fig = go.Figure([
        go.Scatter3d(x=ric[:, 1], y=ric[:, 2], z=ric[:, 0], mode="lines", name="Path",
                     line=dict(color="rgba(230,236,242,0.35)", width=3), hoverinfo="skip"),
        go.Scatter3d(x=[0], y=[0], z=[0], mode="markers+text", text=[primary_name],
                     name=primary_name, textposition="top center", textfont=dict(color=c.TEXT),
                     marker=dict(size=8, color="#5FA8D3", symbol="diamond")),
        go.Scatter3d(x=[ric[k0, 1]], y=[ric[k0, 2]], z=[ric[k0, 0]], mode="markers",
                     name="Closest point", marker=dict(size=4, color="#FFFFFF")),
        go.Scatter3d(x=[0, ric[0, 1]], y=[0, ric[0, 2]], z=[0, ric[0, 0]], mode="lines",
                     name="Distance", line=dict(color=color, width=4, dash="dot")),
        go.Scatter3d(x=[ric[0, 1]], y=[ric[0, 2]], z=[ric[0, 0]], mode="markers",
                     name=secondary_name, marker=dict(size=7, color=color)),
    ])
    step = max(1, len(t) // 60)
    frames = []
    for k in list(range(0, len(t), step)) + [len(t) - 1]:
        frames.append(go.Frame(name=str(k), traces=[3, 4], data=[
            go.Scatter3d(x=[0, ric[k, 1]], y=[0, ric[k, 2]], z=[0, ric[k, 0]]),
            go.Scatter3d(x=[ric[k, 1]], y=[ric[k, 2]], z=[ric[k, 0]],
                         hovertemplate=f"{t[k]:+.0f} s · {dist[k]:.2f} km<extra></extra>"),
        ], layout=dict(title=dict(text=f"{t[k]:+.0f} s from closest approach · "
                                       f"{dist[k]:,.2f} km apart", font=dict(size=14),
                                  x=0.16, xanchor="left"))))
    fig.frames = frames
    axis = lambda title: dict(title=title, range=[-lim, lim], gridcolor=c.GRID,  # noqa: E731
                              backgroundcolor="rgba(0,0,0,0)", color=c.MUTED)
    fig.update_layout(
        height=560, paper_bgcolor="rgba(0,0,0,0)", font_color=c.TEXT,
        margin=dict(l=0, r=0, t=40, b=0), uirevision="replay",
        title=dict(text="Press Replay to watch the pass", font=dict(size=14), x=0.16,
                   xanchor="left"),
        legend=dict(orientation="h", y=-0.02, bgcolor="rgba(0,0,0,0)"),
        scene=dict(xaxis=axis("In-track (km)"), yaxis=axis("Cross-track (km)"),
                   zaxis=axis("Radial (km)"), aspectmode="cube",
                   camera=dict(eye=dict(x=1.5, y=1.2, z=0.8))),
        updatemenus=[dict(type="buttons", direction="left", x=0, y=1.02, yanchor="bottom", active=-1,
                          bgcolor=c.PANEL, bordercolor=c.GRID, font=dict(color=c.TEXT),
                          buttons=[dict(label="▶  Replay", method="animate", args=[None, dict(
                              frame=dict(duration=70, redraw=True), transition=dict(duration=0),
                              mode="immediate", fromcurrent=False)])])],
    )
    return fig


def render() -> None:
    c.setup_page()
    conj = c.load("SELECT * FROM v_conjunctions_detail ORDER BY tca")
    st.title("Close approaches")
    if conj.empty:
        st.info("No close approaches found in the latest screening. Run "
                "`python -m debris.cli screen --primary 25544` to screen again.")
        return

    conj = conj.reset_index(drop=True)
    conj["tca"] = pd.to_datetime(conj["tca"])
    conj["risk"] = conj["collision_probability"].map(risk_level)
    conj["event"] = conj.index
    primary_name = conj["primary_name"].iloc[0]
    st.caption(f"Objects passing within 10 km of the {primary_name} in the next 24 hours. "
               "Click a dot to replay that pass.")

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Close approaches", len(conj))
    m2.metric("Closest miss", f"{conj['miss_distance_km'].min():.2f} km")
    m3.metric("Different objects", conj["secondary_norad"].nunique())
    m4.metric("Fastest pass", f"{conj['relative_velocity_km_s'].max():.2f} km/s")

    timeline = px.scatter(
        conj, x="tca", y="miss_distance_km", color="risk", color_discrete_map=RISK_COLORS,
        hover_name="secondary_name", custom_data=["event"],
        size=np.clip(conj["relative_velocity_km_s"], 1, None), size_max=16,
        labels={"tca": "Time of closest approach (UTC)", "miss_distance_km": "Miss distance (km)",
                "risk": "Risk"}, title="Timeline (bigger dot = faster pass)")
    picked = st.plotly_chart(c.style(timeline, height=330), width="stretch", key="ap_timeline",
                             on_select="rerun", selection_mode="points",
                             config=c.PLOTLY_CONFIG)

    points = picked.selection.points if picked and picked.selection else []
    if points:
        chosen = int(points[0]["customdata"][0])
        if st.session_state.get("ap_last_click") != chosen:
            st.session_state["ap_last_click"] = chosen
            st.session_state["ap_event"] = chosen

    label = lambda i: (f"{conj.at[i, 'tca']:%d %b %H:%M:%S} · {conj.at[i, 'secondary_name']} · "  # noqa: E731
                       f"{conj.at[i, 'miss_distance_km']:.2f} km")
    if st.session_state.get("ap_event") not in conj.index:   # first visit or data refreshed
        st.session_state["ap_event"] = int(conj["miss_distance_km"].idxmin())
    event_id = st.selectbox("Event to replay", conj.index.tolist(), format_func=label,
                            key="ap_event")
    ev = conj.loc[event_id]

    objs = c.objects().set_index("norad_id")
    primary, secondary = objs.loc[ev["primary_norad"]], objs.loc[ev["secondary_norad"]]
    t, ric = relative_motion(primary, secondary, ev["tca"].to_pydatetime(),
                             ev["relative_velocity_km_s"])
    color = RISK_COLORS[ev["risk"]]

    left, right = st.columns([3, 2], gap="large")
    with left:
        st.plotly_chart(replay_figure(t, ric, primary_name, ev["secondary_name"], color),
                        width="stretch", config=c.PLOTLY_CONFIG, key=f"ap_replay_{event_id}")
        st.caption(f"Seen from the {primary_name}, which sits at the centre. Radial points away "
                   "from Earth, in-track is its direction of travel.")
    with right:
        a, b = st.columns(2)
        a.metric("Miss distance", f"{ev['miss_distance_km']:.2f} km")
        b.metric("Relative speed", f"{ev['relative_velocity_km_s']:.2f} km/s")
        a.metric("Collision probability", f"{ev['collision_probability']:.1e}")
        b.metric("Risk level", ev["risk"].title())
        st.caption(f"{ev['secondary_name']} ({ev['secondary_type'].lower()}, NORAD "
                   f"{ev['secondary_norad']}) at {ev['tca']:%d %b %Y %H:%M:%S} UTC")
        dist = np.linalg.norm(ric, axis=1)
        chart = go.Figure(go.Scatter(x=t, y=dist, mode="lines", line=dict(color=color, width=3),
                                     hovertemplate="%{x:+.0f} s · %{y:.2f} km<extra></extra>"))
        chart.add_vline(x=float(t[np.argmin(dist)]), line_dash="dot", line_color=c.MUTED)
        chart.update_layout(title="Distance over time", xaxis_title="Seconds from closest "
                            "approach", yaxis_title="Distance (km)", showlegend=False)
        st.plotly_chart(c.style(chart, height=300), width="stretch", config=c.PLOTLY_CONFIG)
        st.caption("Probability assumes a 1 km position uncertainty, because public orbit "
                   "data has no uncertainty figures. Use it to compare events, not as an "
                   "operational number.")

    with st.expander(f"All {len(conj)} close approaches"):
        st.dataframe(
            conj[["tca", "secondary_name", "secondary_type", "miss_distance_km",
                  "relative_velocity_km_s", "collision_probability", "risk"]],
            hide_index=True, width="stretch",
            column_config={
                "tca": st.column_config.DatetimeColumn("Closest approach (UTC)",
                                                       format="DD MMM HH:mm:ss"),
                "secondary_name": "Object", "secondary_type": "Type",
                "miss_distance_km": st.column_config.NumberColumn("Miss (km)", format="%.2f"),
                "relative_velocity_km_s": st.column_config.NumberColumn("Rel. speed (km/s)",
                                                                        format="%.2f"),
                "collision_probability": st.column_config.NumberColumn("Probability",
                                                                       format="%.1e"),
                "risk": "Risk"})
