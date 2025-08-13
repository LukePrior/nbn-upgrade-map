import argparse
import csv
import os
from typing import Iterable, Tuple

from utils import get_all_geojson_files


def iter_locid_coords(results_dir: str, show_progress: bool = True) -> Iterable[Tuple[str, float, float]]:
    """Yield (loc_id, lat, lng) for every feature across all GeoJSON files under results_dir.

    Skips features missing locID or coordinates.
    """
    # Temporarily change CWD for utils.get_all_geojson_files which uses a relative glob
    # to keep behavior identical whether run locally or in GitHub Actions.
    orig_cwd = os.getcwd()
    try:
        os.chdir(results_dir)
    except FileNotFoundError:
        # If the directory doesn't exist, nothing to yield
        return

    try:
        for _filename, geojson_data in get_all_geojson_files(show_progress=show_progress, rewrite_geojson=False):
            for f in geojson_data.get("features", []):
                props = f.get("properties", {})
                loc_id = props.get("locID")
                geom = f.get("geometry") or {}
                coords = (geom.get("coordinates") or [None, None])
                if not loc_id:
                    continue
                if coords is None or len(coords) < 2 or coords[0] is None or coords[1] is None:
                    continue
                lng, lat = coords[0], coords[1]
                yield loc_id, float(lat), float(lng)
    finally:
        os.chdir(orig_cwd)


def write_csv(output_path: str, rows: Iterable[Tuple[str, float, float]], dedupe: bool = True) -> int:
    """Write rows to CSV with header: loc_id,latitude,longitude. Returns count written."""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    seen = set()
    count = 0
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["loc_id", "latitude", "longitude"])
        for loc_id, lat, lng in rows:
            if dedupe:
                if loc_id in seen:
                    continue
                seen.add(loc_id)
            writer.writerow([loc_id, f"{lat:.8f}", f"{lng:.8f}"])
            count += 1
    return count


def main():
    parser = argparse.ArgumentParser(description="Export NBN locIDs with coordinates to a CSV from GeoJSON results")
    parser.add_argument(
        "--results-dir",
        default="results",
        help="Directory containing GeoJSON results (default: results)",
    )
    parser.add_argument(
        "--output",
        default=os.path.join("results", "locids.csv"),
        help="Path to write the CSV (default: results/locids.csv)",
    )
    parser.add_argument(
        "--no-dedupe",
        action="store_true",
        help="Do not deduplicate by loc_id (default is to dedupe)",
    )
    parser.add_argument(
        "--no-progress",
        action="store_true",
        help="Disable progress output while scanning files",
    )

    args = parser.parse_args()
    rows = iter_locid_coords(args.results_dir, show_progress=not args.no_progress)
    written = write_csv(args.output, rows, dedupe=not args.no_dedupe)
    print(f"Wrote {written} rows to {args.output}")


if __name__ == "__main__":
    main()
