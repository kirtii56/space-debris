"""Overview: every tracked object on a 3D Earth, plus catalogue statistics."""

import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from dashboard import common as c
from debris.config import EVENT_NAMES


@st.fragment(run_every="60s")
def live_globe() -> None:
    """Re-drawn every minute so positions stay current. The camera angle is kept."""
    col1, col2, col3 = st.columns([2.2, 2.4, 1.6])
    types = col1.pills("Objects", list(c.TYPE_LABELS), format_func=c.TYPE_LABELS.get,
                       selection_mode="multi", default=list(c.TYPE_LABELS), key="ov_types")
    orbits = col2.pills("Orbit regime", c.ORBIT_CLASSES, selection_mode="multi",
                        default=["LEO", "MEO", "GEO", "HEO"], key="ov_orbits")
    view = col3.segmented_control("Zoom", ["Low orbit", "Out to GEO"], default="Low orbit",
                                  key="ov_view") or "Low orbit"

    now = c.utcnow()
    pos = c.positions_at(now.strftime("%Y-%m-%dT%H:%M"))
    shown = pos[pos["object_type"].isin(types or []) & pos["orbit_class"].isin(orbits or [])]

    fig = go.Figure(c.earth_traces())
    for kind in types or []:
        sub = shown[shown["object_type"] == kind]
        fig.add_trace(go.Scatter3d(
            x=sub["x"], y=sub["y"], z=sub["z"], mode="markers", text=sub["name"],
            name=f"{c.TYPE_LABELS[kind]} ({len(sub):,})",
            marker=dict(size=1.8 if len(sub) > 3000 else 2.6, color=c.TYPE_COLORS[kind]),
            customdata=sub[["norad_id", "alt", "orbit_class"]],
            hovertemplate="<b>%{text}</b><br>NORAD %{customdata[0]}<br>"
                          "Altitude %{customdata[1]:,.0f} km<br>%{customdata[2]}<extra></extra>",
        ))
    c.globe_layout(fig, 8200 if view == "Low orbit" else 44000, height=660)
    st.plotly_chart(fig, width="stretch", config=c.PLOTLY_CONFIG, key="ov_globe")
    st.caption(f"Positions at {now:%H:%M} UTC, updated every minute. Drag to rotate, scroll to "
               f"zoom, click a legend entry to hide it. Showing {len(shown):,} objects.")


def render() -> None:
    c.setup_page()
    objs = c.objects()
    counts = objs["object_type"].value_counts()

    st.title("Space debris tracker")
    st.caption(f"{len(objs):,} objects from CelesTrak · newest orbit data "
               f"{objs['epoch'].max():%d %b %Y %H:%M} UTC")

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Objects tracked", f"{len(objs):,}")
    m2.metric("Debris fragments", f"{counts.get('DEBRIS', 0):,}")
    m3.metric("Payloads", f"{counts.get('PAYLOAD', 0):,}")
    m4.metric("In low Earth orbit", f"{(objs['orbit_class'] == 'LEO').mean():.0%}")

    live_globe()

    st.subheader("Where it's crowded")
    density = c.load("SELECT * FROM v_altitude_density ORDER BY altitude_band_km")
    density = density[density["altitude_band_km"] <= 2000].melt(
        id_vars="altitude_band_km", value_vars=["debris_count", "payload_count"],
        var_name="kind", value_name="objects")
    density["kind"] = density["kind"].map({"debris_count": "Debris",
                                           "payload_count": "Payloads"})
    label_colors = {c.TYPE_LABELS[k]: v for k, v in c.TYPE_COLORS.items()}
    left, right = st.columns([3, 2])
    left.plotly_chart(c.style(px.bar(
        density, x="altitude_band_km", y="objects", color="kind",
        color_discrete_map=label_colors, title="Objects per 100 km altitude band (LEO)",
        labels={"altitude_band_km": "Perigee altitude (km)", "objects": "Objects", "kind": ""})),
        width="stretch", config=c.PLOTLY_CONFIG)
    by_orbit = c.load("SELECT * FROM v_summary_by_orbit")
    by_orbit = by_orbit.assign(object_type=by_orbit["object_type"].map(c.TYPE_LABELS))
    right.plotly_chart(c.style(px.bar(
        by_orbit, x="orbit_class", y="object_count", color="object_type", log_y=True,
        barmode="group", category_orders={"orbit_class": c.ORBIT_CLASSES},
        color_discrete_map=label_colors, title="Objects by orbit regime (log scale)",
        labels={"orbit_class": "", "object_count": "Objects", "object_type": ""})),
        width="stretch", config=c.PLOTLY_CONFIG)

    events = c.load("SELECT * FROM v_breakup_events ORDER BY fragments_tracked DESC")
    if not events.empty:
        st.subheader("Breakup events still in orbit")
        events = events.assign(event=events["source_group"].map(EVENT_NAMES).fillna(
            events["source_group"]))
        st.dataframe(
            events[["event", "fragments_tracked", "lowest_perigee_km", "highest_apogee_km",
                    "avg_inclination_deg"]], hide_index=True, width="stretch",
            column_config={
                "event": "Event",
                "fragments_tracked": st.column_config.ProgressColumn(
                    "Fragments still tracked", format="%d", min_value=0,
                    max_value=int(events["fragments_tracked"].max())),
                "lowest_perigee_km": st.column_config.NumberColumn("Lowest perigee (km)",
                                                                   format="%.0f"),
                "highest_apogee_km": st.column_config.NumberColumn("Highest apogee (km)",
                                                                   format="%.0f"),
                "avg_inclination_deg": st.column_config.NumberColumn("Avg inclination (°)",
                                                                     format="%.1f"),
            })
