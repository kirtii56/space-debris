"""Shared data loading, styling and 3D Earth helpers for the dashboard pages."""

from datetime import datetime, timezone

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from debris import db
from debris.config import EARTH_RADIUS_KM, MU_EARTH
from debris.propagator import propagate_many, teme_to_geodetic, time_grid

TYPE_COLORS = {"PAYLOAD": "#5FA8D3", "DEBRIS": "#F2B544", "ROCKET BODY": "#E0707A"}
TYPE_LABELS = {"PAYLOAD": "Payloads", "DEBRIS": "Debris", "ROCKET BODY": "Rocket bodies"}
ORBIT_CLASSES = ["LEO", "MEO", "GEO", "HEO", "OTHER"]
TEXT, MUTED, PANEL, GRID = "#E6ECF2", "#8A9BB0", "#16263B", "#243A55"
CLUSTER_PALETTE = ["#5FA8D3", "#F2B544", "#7CC47F", "#E0707A", "#B08AD9", "#4FC1B6",
                   "#E89B5E", "#D9D36A", "#8FA3F2", "#E27FB5"]

CSS = f"""
<style>
div[data-testid="stMetric"] {{
    background: {PANEL}; border: 1px solid {GRID}; border-radius: 10px; padding: 10px 14px;
}}
div[data-testid="stMetricLabel"] p {{ color: {MUTED}; }}
.block-container {{ padding-top: 3.2rem; }}
</style>
"""


def setup_page() -> None:
    st.markdown(CSS, unsafe_allow_html=True)


# ------------------------------------------------------------------ data
@st.cache_data(ttl=600, show_spinner=False)
def load(sql: str) -> pd.DataFrame:
    return db.query_df(sql)


def objects() -> pd.DataFrame:
    try:
        df = load("SELECT * FROM objects").copy()
    except Exception:
        return pd.DataFrame()
    if not df.empty:
        df["epoch"] = pd.to_datetime(df["epoch"])
    return df


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None, microsecond=0)


def to_xyz(lat, lon, alt):
    """Latitude/longitude/altitude -> Earth-fixed x, y, z in km (spherical Earth, for plots)."""
    r = EARTH_RADIUS_KM + np.asarray(alt)
    la, lo = np.radians(lat), np.radians(lon)
    return r * np.cos(la) * np.cos(lo), r * np.cos(la) * np.sin(lo), r * np.sin(la)


def track(line1s, line2s, start: datetime, offsets_s: np.ndarray):
    """Latitude, longitude, altitude arrays shaped (objects, times) and a success mask."""
    jd, fr = time_grid(start, offsets_s)
    r, _, ok = propagate_many(list(line1s), list(line2s), jd, fr)
    lat, lon, alt = teme_to_geodetic(r, jd + fr)
    return lat, lon, alt, ok


def orbital_speed(altitude_km, semi_major_axis_km):
    """Vis-viva equation: speed in km/s at a given altitude."""
    r = EARTH_RADIUS_KM + altitude_km
    return np.sqrt(MU_EARTH * (2 / r - 1 / semi_major_axis_km))


@st.cache_data(ttl=90, show_spinner=False)
def positions_at(minute_iso: str) -> pd.DataFrame:
    """Every object's position at the given minute (cached so page switches are instant)."""
    df = objects()
    lat, lon, alt, ok = track(df["tle_line1"], df["tle_line2"],
                              datetime.fromisoformat(minute_iso), np.array([0.0]))
    out = df[["norad_id", "name", "object_type", "orbit_class"]].assign(
        lat=lat[:, 0], lon=lon[:, 0], alt=alt[:, 0])[ok[:, 0]]
    x, y, z = to_xyz(out["lat"], out["lon"], out["alt"])
    return out.assign(x=x, y=y, z=z)


# ------------------------------------------------------------------ figures
def earth_traces() -> list:
    """A shaded sphere with a latitude/longitude grid."""
    u = np.linspace(0, 2 * np.pi, 73)
    v = np.linspace(-np.pi / 2, np.pi / 2, 37)
    uu, vv = np.meshgrid(u, v)
    R = EARTH_RADIUS_KM * 0.995  # slightly inside so grid lines and orbits draw on top
    sphere = go.Surface(
        x=R * np.cos(vv) * np.cos(uu), y=R * np.cos(vv) * np.sin(uu), z=R * np.sin(vv),
        surfacecolor=np.cos(vv), colorscale=[[0, "#0F2E4A"], [1, "#1F5F8B"]],
        showscale=False, hoverinfo="skip", name="Earth",
        lighting=dict(ambient=0.75, diffuse=0.6, specular=0.05, roughness=0.9),
    )
    xs, ys, zs = [], [], []
    t = np.linspace(0, 2 * np.pi, 121)
    for lat in range(-60, 61, 30):
        la = np.radians(lat)
        xs += list(EARTH_RADIUS_KM * np.cos(la) * np.cos(t)) + [None]
        ys += list(EARTH_RADIUS_KM * np.cos(la) * np.sin(t)) + [None]
        zs += [EARTH_RADIUS_KM * np.sin(la)] * len(t) + [None]
    p = np.linspace(-np.pi / 2, np.pi / 2, 61)
    for lon in range(0, 360, 30):
        lo = np.radians(lon)
        xs += list(EARTH_RADIUS_KM * np.cos(p) * np.cos(lo)) + [None]
        ys += list(EARTH_RADIUS_KM * np.cos(p) * np.sin(lo)) + [None]
        zs += list(EARTH_RADIUS_KM * np.sin(p)) + [None]
    grid = go.Scatter3d(x=xs, y=ys, z=zs, mode="lines", hoverinfo="skip", showlegend=False,
                        line=dict(color="rgba(230,236,242,0.18)", width=1))
    return [sphere, grid]


def globe_layout(fig: go.Figure, extent_km: float, height: int = 640,
                 revision: str = "globe") -> go.Figure:
    axis = dict(visible=False, range=[-extent_km, extent_km])
    fig.update_layout(
        height=height, margin=dict(l=0, r=0, t=0, b=0), paper_bgcolor="rgba(0,0,0,0)",
        font_color=TEXT, uirevision=revision,
        scene=dict(xaxis=axis, yaxis=axis, zaxis=axis, aspectmode="cube",
                   bgcolor="rgba(0,0,0,0)", camera=dict(eye=dict(x=1.05, y=1.05, z=0.55))),
        legend=dict(orientation="h", x=0, y=1, font=dict(color=TEXT),
                    bgcolor="rgba(0,0,0,0)", itemsizing="constant"),
    )
    return fig


def style(fig: go.Figure, height: int | None = None) -> go.Figure:
    fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                      font_color=TEXT, margin=dict(l=10, r=10, t=40, b=10),
                      legend=dict(bgcolor="rgba(0,0,0,0)"))
    fig.update_xaxes(gridcolor=GRID, zerolinecolor=GRID)
    fig.update_yaxes(gridcolor=GRID, zerolinecolor=GRID)
    if height:
        fig.update_layout(height=height)
    return fig


def geo_style(fig: go.Figure, projection: str = "natural earth", center=None,
              height: int = 520) -> go.Figure:
    geo = dict(projection_type=projection, showland=True, landcolor="#1F3350",
               showocean=True, oceancolor="#0E1A2B", showcountries=True,
               countrycolor="#2E4868", coastlinecolor=MUTED, bgcolor="rgba(0,0,0,0)",
               showframe=False, lataxis=dict(showgrid=True, gridcolor=GRID),
               lonaxis=dict(showgrid=True, gridcolor=GRID))
    if center:
        geo["projection_rotation"] = dict(lat=center[0], lon=center[1])
    fig.update_layout(geo=geo, height=height, paper_bgcolor="rgba(0,0,0,0)", font_color=TEXT,
                      margin=dict(l=0, r=0, t=10, b=0), legend=dict(bgcolor="rgba(0,0,0,0)"))
    return fig


PLOTLY_CONFIG = {"displaylogo": False,
                 "modeBarButtonsToRemove": ["toImage", "lasso2d", "select2d"]}
