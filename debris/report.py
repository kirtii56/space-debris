"""Write a results snapshot from the current database: charts, CSV/JSON files and a
Results section in README.md.

    python -m debris.report
"""

import json
import logging
import re
from datetime import datetime, timezone

import matplotlib

matplotlib.use("Agg")  # no screen needed
import matplotlib.pyplot as plt
import pandas as pd

from . import db
from .collision import risk_level
from .config import EVENT_NAMES, ROOT_DIR
from .ml.clustering import load_metrics

logger = logging.getLogger(__name__)

RESULTS_DIR = ROOT_DIR / "results"
README = ROOT_DIR / "README.md"
START, END = "<!-- RESULTS:START -->", "<!-- RESULTS:END -->"

DEBRIS_COLOR, PAYLOAD_COLOR, NOISE_COLOR = "#D98E04", "#2E6F9E", "#B8B8B8"


def _style(ax, title, xlabel, ylabel):
    ax.set_title(title, loc="left", fontsize=12, fontweight="bold")
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(axis="y", alpha=0.3)


def altitude_chart(path):
    df = db.query_df("SELECT * FROM v_altitude_density WHERE altitude_band_km <= 2000 "
                     "ORDER BY altitude_band_km")
    fig, ax = plt.subplots(figsize=(10, 4.5))
    ax.bar(df["altitude_band_km"], df["debris_count"], width=90, color=DEBRIS_COLOR,
           label="Debris")
    ax.bar(df["altitude_band_km"], df["payload_count"], width=90, bottom=df["debris_count"],
           color=PAYLOAD_COLOR, label="Payloads")
    _style(ax, "Objects per 100 km altitude band (low Earth orbit)", "Perigee altitude (km)",
           "Objects")
    ax.legend(frameon=False)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def cluster_chart(clusters, path):
    fig, ax = plt.subplots(figsize=(10, 5))
    noise = clusters[clusters["cluster_id"] == -1]
    ax.scatter(noise["inclination_deg"], noise["mean_motion_rev_day"], s=6, c=NOISE_COLOR,
               label="No cluster")
    for cid, group in clusters[clusters["cluster_id"] != -1].groupby("cluster_id"):
        ax.scatter(group["inclination_deg"], group["mean_motion_rev_day"], s=6,
                   label=f"Cluster {cid}")
    _style(ax, "Debris fragments grouped by DBSCAN", "Inclination (degrees)",
           "Mean motion (orbits per day)")
    ax.legend(frameon=False, markerscale=3, fontsize=8, ncol=2)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def _table(df: pd.DataFrame) -> str:
    """DataFrame -> Markdown table (no extra dependency needed)."""
    head = "| " + " | ".join(df.columns) + " |"
    rule = "|" + "|".join("---" for _ in df.columns) + "|"
    rows = ["| " + " | ".join(str(v) for v in row) + " |" for row in df.itertuples(index=False)]
    return "\n".join([head, rule, *rows])


def build() -> dict:
    RESULTS_DIR.mkdir(exist_ok=True)
    objects = db.query_df("SELECT norad_id, object_type, orbit_class, epoch FROM objects")
    if objects.empty:
        raise RuntimeError("The database is empty. Run `python -m debris.cli all` first.")

    by_type = objects["object_type"].value_counts()
    events = db.query_df("SELECT * FROM v_breakup_events ORDER BY fragments_tracked DESC")
    conj = db.query_df("SELECT * FROM v_conjunctions_detail ORDER BY miss_distance_km")
    clusters = db.query_df("SELECT c.cluster_id, o.norad_id, o.source_group, o.inclination_deg, "
                           "o.mean_motion_rev_day FROM debris_clusters c "
                           "JOIN objects o ON o.norad_id = c.norad_id")
    metrics = load_metrics() or {}
    run_time = datetime.now(timezone.utc)

    altitude_chart(RESULTS_DIR / "altitude_density.png")
    if not clusters.empty:
        cluster_chart(clusters, RESULTS_DIR / "debris_clusters.png")
    conj.to_csv(RESULTS_DIR / "iss_close_approaches.csv", index=False)

    summary = {
        "data_downloaded_utc": run_time.strftime("%Y-%m-%d %H:%M"),
        "objects_tracked": int(len(objects)),
        "by_type": {k: int(v) for k, v in by_type.items()},
        "leo_share": round(float((objects["orbit_class"] == "LEO").mean()), 3),
        "close_approaches_under_10km": int(len(conj)),
        "closest_miss_km": round(float(conj["miss_distance_km"].min()), 2) if len(conj) else None,
        "clustering": metrics,
    }
    (RESULTS_DIR / "summary.json").write_text(json.dumps(summary, indent=2))

    # ---- Markdown for the README
    lines = [
        f"Latest run: **{summary['data_downloaded_utc']} UTC**, using live CelesTrak data. "
        "Refreshed automatically every week by GitHub Actions.",
        "",
        "| Measure | Value |",
        "|---|---|",
        f"| Objects tracked | {len(objects):,} |",
        f"| Debris fragments | {by_type.get('DEBRIS', 0):,} |",
        f"| Payloads | {by_type.get('PAYLOAD', 0):,} |",
        f"| Rocket bodies | {by_type.get('ROCKET BODY', 0):,} |",
        f"| Share in low Earth orbit | {summary['leo_share']:.0%} |",
        f"| ISS close approaches under 10 km (next 24 h) | {len(conj)} |",
    ]
    if len(conj):
        lines.append(f"| Closest ISS approach | {summary['closest_miss_km']} km |")
    lines += ["", "![Objects per altitude band](results/altitude_density.png)", ""]

    if not events.empty:
        ev = events.assign(
            event=events["source_group"].map(EVENT_NAMES).fillna(events["source_group"]),
            fragments=events["fragments_tracked"],
            perigee_range_km=events["lowest_perigee_km"].round(0).astype(int).astype(str) + " – "
            + events["highest_apogee_km"].round(0).astype(int).astype(str),
            avg_inclination=events["avg_inclination_deg"].round(1),
        )[["event", "fragments", "perigee_range_km", "avg_inclination"]]
        ev.columns = ["Breakup event", "Fragments still tracked", "Altitude range (km)",
                      "Avg inclination (°)"]
        lines += ["**Breakup events in the catalogue**", "", _table(ev), ""]

    if metrics:
        lines += [
            "**DBSCAN breakup clustering** (the model is never told which event a fragment "
            "came from)",
            "",
            "| Metric | Value |",
            "|---|---|",
            f"| Fragments clustered | {metrics['fragments']:,} |",
            f"| Clusters found / true events | {metrics['clusters_found']} / "
            f"{metrics['true_events']} |",
            f"| Adjusted Rand index (1 = perfect) | {metrics['adjusted_rand_index']:.2f} |",
            f"| Homogeneity | {metrics['homogeneity']:.2f} |",
            f"| Completeness | {metrics['completeness']:.2f} |",
            f"| Left as noise | {metrics['noise_fraction']:.0%} |",
            "",
            "![DBSCAN clusters](results/debris_clusters.png)",
            "",
        ]
        cross = pd.crosstab(clusters["source_group"].map(EVENT_NAMES).fillna(
            clusters["source_group"]), clusters["cluster_id"].map(
            lambda c: "noise" if c == -1 else f"cluster {c}"))
        cross = cross.reset_index().rename(columns={"source_group": "True event"})
        lines += ["**Which cluster matched which event**", "", _table(cross), ""]

    if len(conj):
        top = conj.head(5).assign(
            when=pd.to_datetime(conj["tca"]).dt.strftime("%d %b %H:%M UTC"),
            miss=conj["miss_distance_km"].round(2),
            speed=conj["relative_velocity_km_s"].round(2),
            risk=conj["collision_probability"].map(risk_level),
        )[["when", "secondary_name", "secondary_type", "miss", "speed", "risk"]]
        top.columns = ["Closest approach", "Object", "Type", "Miss (km)", "Rel. speed (km/s)",
                       "Risk"]
        lines += ["**Closest approaches to the ISS**", "", _table(top), "",
                  "Full list: [results/iss_close_approaches.csv](results/iss_close_approaches.csv)",
                  ""]

    block = "\n".join(lines).strip()
    (RESULTS_DIR / "RESULTS.md").write_text(f"# Results\n\n{block}\n")
    _update_readme(block)
    logger.info("Results written to %s", RESULTS_DIR)
    return summary


def _update_readme(block: str) -> None:
    text = README.read_text()
    section = f"{START}\n{block}\n{END}"
    if START in text:
        text = re.sub(re.escape(START) + ".*?" + re.escape(END), lambda _: section, text,
                      flags=re.S)
    else:
        text = text.replace("## Tech stack", f"## Results\n\n{section}\n\n## Tech stack", 1)
    README.write_text(text)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    print(json.dumps(build(), indent=2))
