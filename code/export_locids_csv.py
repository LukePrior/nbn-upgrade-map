import argparse
import csv
import os
from typing import Any, Dict, Iterable, List

from utils import get_all_geojson_files

# All available fields in GeoJSON features
AVAILABLE_FIELDS = [
    "loc_id",
    "latitude",
    "longitude",
    "name",
    "tech",
    "upgrade",
    "gnaf_pid",
    "tech_change_status",
    "program_type",
    "target_eligibility_quarter",
]

# Default fields to export (maintains backward compatibility)
DEFAULT_FIELDS = ["loc_id", "latitude", "longitude"]


def iter_feature_data(show_progress: bool = True, fields: List[str] = None) -> Iterable[Dict[str, Any]]:
    """Yield feature data as a dictionary for every feature across all GeoJSON files.

    Args:
        show_progress: Whether to show progress while scanning files
        fields: List of field names to extract. If None, extracts all available fields.

    Skips features missing locID or coordinates.
    """
    if fields is None:
        fields = AVAILABLE_FIELDS

    for _filename, geojson_data in get_all_geojson_files(show_progress=show_progress, rewrite_geojson=False):
        for f in geojson_data.get("features", []):
            props = f.get("properties", {})
            loc_id = props.get("locID")
            geom = f.get("geometry") or {}
            coords = geom.get("coordinates") or [None, None]

            # Skip features without loc_id or coordinates
            if not loc_id:
                continue
            if coords is None or len(coords) < 2 or coords[0] is None or coords[1] is None:
                continue

            lng, lat = coords[0], coords[1]

            # Build field extraction mapping
            field_extractors = {
                "loc_id": loc_id,
                "latitude": float(lat),
                "longitude": float(lng),
                "name": props.get("name", ""),
                "tech": props.get("tech", ""),
                "upgrade": props.get("upgrade", ""),
                "gnaf_pid": props.get("gnaf_pid", ""),
                "tech_change_status": props.get("tech_change_status", ""),
                "program_type": props.get("program_type", ""),
                "target_eligibility_quarter": props.get("target_eligibility_quarter", ""),
            }

            # Build the result dictionary with requested fields
            result = {field: field_extractors[field] for field in fields}

            yield result


def write_csv(output_path: str, rows: Iterable[Dict[str, Any]], fields: List[str], dedupe: bool = True) -> int:
    """Write rows to CSV with specified fields. Returns count written.

    Args:
        output_path: Path to write the CSV file
        rows: Iterable of dictionaries containing feature data
        fields: List of field names to include in the CSV
        dedupe: Whether to deduplicate by loc_id
    """
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    seen = set()
    count = 0

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()

        for row in rows:
            if dedupe and "loc_id" in row:
                if row["loc_id"] in seen:
                    continue
                seen.add(row["loc_id"])

            # Format latitude and longitude with precision if they exist
            formatted_row = {}
            for field in fields:
                value = row.get(field, "")
                if field in ["latitude", "longitude"] and value != "":
                    formatted_row[field] = f"{value:.8f}"
                else:
                    formatted_row[field] = value

            writer.writerow(formatted_row)
            count += 1

    return count


def main():
    parser = argparse.ArgumentParser(description="Export NBN data with selected fields to a CSV from GeoJSON results")
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
    parser.add_argument(
        "--fields",
        nargs="+",
        choices=AVAILABLE_FIELDS,
        default=DEFAULT_FIELDS,
        help=(
            f"Fields to include in the CSV (default: {' '.join(DEFAULT_FIELDS)}). "
            f"Available: {', '.join(AVAILABLE_FIELDS)}"
        ),
    )
    parser.add_argument(
        "--all-fields",
        action="store_true",
        help="Include all available fields in the CSV",
    )

    args = parser.parse_args()

    # Determine which fields to export
    fields = AVAILABLE_FIELDS if args.all_fields else args.fields

    rows = iter_feature_data(show_progress=not args.no_progress, fields=fields)
    written = write_csv(args.output, rows, fields, dedupe=not args.no_dedupe)
    print(f"Wrote {written} rows with fields [{', '.join(fields)}] to {args.output}")


if __name__ == "__main__":
    main()
