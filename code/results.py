import argparse
import glob
import logging
import os
from collections import Counter
from datetime import datetime

import data
from suburbs import get_completed_suburbs, read_all_suburbs, write_results_json


def update_existing_suburbs(suburbs: list):
    """Update the suburb list with the latest results from the results folder."""
    # TODO: refactor this to use the Suburb class
    existing = get_completed_suburbs()
    for new_suburb in suburbs:
        add_suburb = True
        for existing_suburb in existing:
            if (
                new_suburb["internal"] == existing_suburb["internal"]
                and new_suburb["state"] == existing_suburb["state"]
            ):
                existing_suburb.update(new_suburb)
                add_suburb = False
                break
        if add_suburb:
            existing.append(new_suburb)
    return existing


def collect_completed_suburbs():
    """Collect the list of completed suburbs from the results folder."""
    # This should only be used in extreme cases, e.g. when the results file is corrupted.
    suburbs = []
    for state in data.STATES:
        logging.info("Collecting completed suburbs for %s", state)
        for file in glob.glob(f"results/{state}/*.geojson"):
            filename, _ = os.path.splitext(os.path.basename(file))
            result = data.read_json_file(file)

            # Check if result has a "suburb" field
            suburb = result.get("suburb", filename.replace("-", " "))

            suburbs.append(
                {
                    "internal": suburb.upper(),
                    "state": state,
                    "name": suburb.title(),
                    "file": filename,
                    "date": datetime.fromisoformat(result["generated"]),
                }
            )
    return suburbs


def print_progress(message: str, tally: dict):
    """print each row of a done/total/percent tally with a grant total at the bottom"""
    total_done = total = 0
    print(f"{message}:")
    for key, info in tally.items():
        total_done += info["done"]
        total += info["total"]
        print(f"{key:>5}: {info['done']} / {info['total']} = {info['percent']:.1f}%")
    if "TOTAL" not in tally:
        print(f"Total: {total_done} / {total}  = {total_done / total * 100.0:.1f}%")
    print()


def _format_percent(numerator: int, denominator: int, default=100.0):
    """Format a percentage as a string."""
    return round(numerator / denominator * 100.0, 1) if denominator else default


def _get_completion_progress(suburb_list) -> dict:
    """Return done/total/progress dict for all suburbs in the given list"""
    tally = Counter(suburb.processed_date is not None for suburb in suburb_list)
    return {
        "done": tally.get(True, 0),
        "total": tally.total(),
        "percent": _format_percent(tally.get(True, 0), tally.total()),
    }


def _add_total_progress(progress: dict):
    """Add a TOTAL entry to the given progress dict."""
    progress["TOTAL"] = {
        "done": sum(p["done"] for p in progress.values()),
        "total": sum(p["total"] for p in progress.values()),
    }
    progress["TOTAL"]["percent"] = _format_percent(progress["TOTAL"]["done"], progress["TOTAL"]["total"])


def get_suburb_progress():
    """Calculate a state-by-state progress indicator vs the named list of states+suburbs."""
    progress = {"listed": {}, "all": {}}
    for state, suburb_list in read_all_suburbs().items():
        progress["listed"][state] = _get_completion_progress(suburb for suburb in suburb_list if suburb.announced)
        progress["all"][state] = _get_completion_progress(suburb_list)

    _add_total_progress(progress["listed"])
    _add_total_progress(progress["all"])
    return progress


def update_progress():
    """Update the progress.json file with the latest results."""
    results = {
        "suburbs": get_suburb_progress(),
        # "addresses": address_vs,
    }
    logging.info("Updating progress.json")
    data.write_json_file("results/progress.json", results)  # indent=1 is to minimise size increase
    return results["suburbs"]


def main():
    parser = argparse.ArgumentParser(description="Emit a summary of progress against the list of suburbs in the DB.")
    parser.add_argument(
        "-s",
        "--simple",
        help="Whether to only update results.json and not the other files",
        action="store_true",
    )
    args = parser.parse_args()

    # TODO: shouldn't need to read all the results!  This takes so long!
    suburbs = collect_completed_suburbs()
    if args.simple:
        suburbs = update_existing_suburbs(suburbs)
        write_results_json(suburbs)
        return
    write_results_json(suburbs)

    suburb_progress = update_progress()
    print_progress("Progress vs Listed Suburbs", suburb_progress["listed"])
    print_progress("Progress vs All Suburbs", suburb_progress["all"])


if __name__ == "__main__":
    main()
