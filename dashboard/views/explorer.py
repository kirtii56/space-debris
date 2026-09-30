"""Satellite explorer: search any object and see its orbit, ground track and details."""

import numpy as np
import plotly.graph_objects as go
import streamlit as st

from dashboard import common as c
from debris.config import DEFAULT_PRIMARY_NORAD, EVENT_NAMES


def break_at_dateline(lat: np.ndarray, lon: np.ndarray):
    """Insert gaps where the track wraps from +180 to -180 so the map has no stray lines."""
    lat, lon = lat.astype(float), lon.astype(float)
    jumps = np.where(np.abs(np.diff(lon)) > 180)[0] + 1
    return np.insert(lat, jumps, np.nan), np.insert(lon, jumps, np.nan)


def render() -> None:
    c.setup_page()
    objs = c.objects().sort_values("name")
    st.title("Satellite explorer")

    ids = objs["norad_id"].tolist()
    names = dict(zip(objs["norad_id"], objs["name"]))
    default = ids.index(DEFAULT_PRIMARY_NORAD) if DEFAULT_PRIMARY_NORAD in names else 0
    norad = st.selectbox("Search by name or NORAD ID (for example ISS, HUBBLE, STARLINK, "
                         "FENGYUN)", ids, index=default, key="ex_object",
                         format_func=lambda i: f"{names[i]}  ·  {i}")
    row = objs.set_index("norad_id").loc[norad]

    now = c.utcnow()
    period_s = float(row["period_min"]) * 60
    orbit_off = np.linspace(0, period_s, 241)
    lat, lon, alt, ok = c.track([row["tle_line1"]], [row["tle_line2"]], now, orbit_off)
    lat, lon, alt, ok = lat[0], lon[0], alt[0], ok[0]
    if not ok[0]:
        st.error("This object's orbit data can't be projected to the current time. It has "
                 "probably re-entered the atmosphere or the data is too old.")
        return

    tle_age = (now - row["epoch"]).total_seconds() / 86400
    color = c.TYPE_COLORS.get(row["object_type"], c.TEXT)
    left, right = st.columns([1, 2.3], gap="large")

    with left:
        st.subheader(row["name"])
        st.markdown(f"<span style='color:{color};font-weight:600'>{row['object_type'].title()}"
                    f"</span> · {row['orbit_class']} · NORAD {norad}", unsafe_allow_html=True)
        a, b = st.columns(2)
        a.metric("Altitude now", f"{alt[0]:,.0f} km")
        b.metric("Speed (km/s)", f"{c.orbital_speed(alt[0], row['semi_major_axis_km']):.2f}")
        a.metric("One orbit takes", f"{row['period_min']:.0f} min")
        b.metric("Inclination", f"{row['inclination_deg']:.1f}°")
        a.metric("Lowest point", f"{row['perigee_km']:,.0f} km")
        b.metric("Highest point", f"{row['apogee_km']:,.0f} km")
        st.caption(f"Latitude {lat[0]:.2f}°, longitude {lon[0]:.2f}° at {now:%H:%M} UTC")
        source = EVENT_NAMES.get(row["source_group"], row["source_group"])
        st.caption(f"Launch {row['intl_designator']} · CelesTrak group: {source} · orbit data "
                   f"is {tle_age:.1f} days old" + (" (old, so positions are less accurate)"
                                                   if tle_age > 14 else ""))
        with st.expander("Raw orbit data (TLE)"):
            st.code(f"{row['name']}\n{row['tle_line1']}\n{row['tle_line2']}", language=None)

    with right:
        orbit_tab, track_tab = st.tabs(["3D orbit", "Ground track"])
        with orbit_tab:
            x, y, z = c.to_xyz(lat, lon, alt)
            fig = go.Figure(c.earth_traces())
            fig.add_trace(go.Scatter3d(x=x, y=y, z=z, mode="lines", name="Next orbit",
                                       line=dict(color=color, width=4), hoverinfo="skip"))
            fig.add_trace(go.Scatter3d(
                x=[x[0]], y=[y[0]], z=[z[0]], mode="markers+text", name="Now",
                text=[row["name"]], textposition="top center", textfont=dict(color=c.TEXT),
                marker=dict(size=7, color="#FFFFFF", line=dict(color=color, width=3)),
                hovertemplate=f"<b>{row['name']}</b><br>{alt[0]:,.0f} km<extra></extra>"))
            extent = max(7400.0, (6378 + float(np.nanmax(alt))) * 1.08)
            c.globe_layout(fig, extent, height=540, revision=f"orbit-{norad}")
            st.plotly_chart(fig, width="stretch", config=c.PLOTLY_CONFIG)
            st.caption("One full orbit starting now, in an Earth-fixed frame. Drag to rotate.")

        with track_tab:
            view = st.segmented_control("Map style", ["Flat map", "Globe"], default="Flat map",
                                        key="ex_map") or "Flat map"
            span = min(3 * period_s, 86400)
            t_off = np.linspace(0, span, int(min(900, max(240, span / 20))))
            glat, glon, _, gok = c.track([row["tle_line1"]], [row["tle_line2"]], now, t_off)
            glat, glon = glat[0][gok[0]], glon[0][gok[0]]
            tlat, tlon = break_at_dateline(glat, glon)
            fig = go.Figure()
            fig.add_trace(go.Scattergeo(lat=tlat, lon=tlon, mode="lines", hoverinfo="skip",
                                        line=dict(color=color, width=2),
                                        name=f"Next {span / 60:.0f} minutes"))
            fig.add_trace(go.Scattergeo(lat=[lat[0]], lon=[lon[0]], mode="markers", name="Now",
                                        marker=dict(size=12, color="#FFFFFF",
                                                    line=dict(color=color, width=3)),
                                        hovertemplate=f"{row['name']}<extra></extra>"))
            projection = "orthographic" if view == "Globe" else "natural earth"
            c.geo_style(fig, projection, center=(lat[0], lon[0]) if view == "Globe" else None)
            st.plotly_chart(fig, width="stretch", config=c.PLOTLY_CONFIG)
            st.caption("The path over the ground: it shifts west each orbit because Earth "
                       "turns underneath.")

    siblings = objs[(objs["launch_id"] == row["launch_id"]) & (objs["norad_id"] != norad)]
    if not siblings.empty:
        st.subheader(f"{len(siblings):,} other objects from the same launch ({row['launch_id']})")
        st.dataframe(
            siblings.head(500)[["name", "norad_id", "object_type", "perigee_km", "apogee_km",
                                "inclination_deg"]],
            hide_index=True, width="stretch", height=260,
            column_config={"name": "Name", "norad_id": st.column_config.NumberColumn(
                "NORAD", format="%d"), "object_type": "Type",
                "perigee_km": st.column_config.NumberColumn("Perigee (km)", format="%.0f"),
                "apogee_km": st.column_config.NumberColumn("Apogee (km)", format="%.0f"),
                "inclination_deg": st.column_config.NumberColumn("Incl. (°)", format="%.2f")})
        if len(siblings) > 500:
            st.caption("Showing the first 500.")
        st.caption("Pick any of these names in the search box above to explore it.")
