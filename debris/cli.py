"""Command line entry point.

    python -m debris.cli ingest            # download real data from CelesTrak into the database
    python -m debris.cli screen --primary 25544
    python -m debris.cli cluster
    python -m debris.cli all               # all three in order
"""

import argparse
import logging

from . import conjunctions, pipeline
from .config import DEFAULT_PRIMARY_NORAD, MISS_THRESHOLD_KM, SCREEN_HOURS
from .ml import clustering


def main() -> None:
    parser = argparse.ArgumentParser(prog="debris", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    ingest = sub.add_parser("ingest", help="download TLEs and load the database")
    ingest.add_argument("--force", action="store_true", help="ignore the 2-hour download cache")

    screen = sub.add_parser("screen", help="find close approaches for one object")
    screen.add_argument("--primary", type=int, default=DEFAULT_PRIMARY_NORAD)
    screen.add_argument("--hours", type=float, default=SCREEN_HOURS)
    screen.add_argument("--threshold", type=float, default=MISS_THRESHOLD_KM, help="km")

    clus = sub.add_parser("cluster", help="cluster debris into breakup events with DBSCAN")
    clus.add_argument("--eps", type=float, default=None, help="default: chosen automatically")
    clus.add_argument("--min-samples", type=int, default=10)

    sub.add_parser("all", help="ingest, screen the ISS, then cluster")

    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    if args.command in ("ingest", "all"):
        pipeline.run(force_download=getattr(args, "force", False))
    if args.command in ("screen", "all"):
        result = conjunctions.run(getattr(args, "primary", DEFAULT_PRIMARY_NORAD),
                                  hours=getattr(args, "hours", SCREEN_HOURS),
                                  threshold_km=getattr(args, "threshold", MISS_THRESHOLD_KM))
        print(result.to_string(index=False) if not result.empty else "No close approaches found.")
    if args.command in ("cluster", "all"):
        metrics = clustering.run(getattr(args, "eps", None), getattr(args, "min_samples", 10))
        for key, value in metrics.items():
            print(f"{key:>22}: {value}")


if __name__ == "__main__":
    main()
