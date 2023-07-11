import argparse
import glob
import os
from collections import Counter
from datetime import datetime

import data
from db import add_db_arguments, connect_to_db
from suburbs import (
    get_all_suburbs,
    get_completed_suburbs,
    get_completed_suburbs_by_state,
    get_listed_suburbs,
    write_results_json,
)

UPGRADE_TALLY = Counter()


def update_existing_suburbs(suburbs: list):
    """Update the suburb list with the latest results from the results folder."""
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
    suburbs = []
    for state in data.STATES:
        for file in glob.glob(f"results/{state}/*.geojson"):
            filename, _ = os.path.splitext(os.path.basename(file))
            result = data.read_json_file(file)

            # Check if result has a "suburb" field
            suburb = result.get("suburb", filename.replace("-", " "))

            UPGRADE_TALLY.update(feature["properties"].get("upgrade", "") for feature in result["features"])

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


def compare_address_counts(completed_suburbs: dict, vs_suburbs: dict, counts: dict):
    """Calculate a summary of progress against the list of suburbs in the DB."""
    results = {}
    all_completed = all_total = 0
    for state, suburbs in vs_suburbs.items():
        completed = total = 0
        for suburb in suburbs:
            suburb_count = counts[state].get(suburb, 0)
            if suburb in completed_suburbs.get(state, set()):
                completed += suburb_count
            total += suburb_count
        fraction_completed = (completed / total * 100) if total else 0
        results[state] = {"done": completed, "total": total, "percent": round(fraction_completed, 1)}
        all_completed += completed
        all_total += total
    results["TOTAL"] = {"done": all_completed, "total": all_total, "percent": round(all_completed / all_total * 100, 1)}
    return results


def collect_address_progress():
    """Collect a summary of progress against the list of suburbs in the DB."""
    # connect to the DB and get a count of addresses by suburb
    parser = argparse.ArgumentParser(description="Emit a summary of progress against the list of suburbs in the DB.")
    add_db_arguments(parser)
    args = parser.parse_args()
    db = connect_to_db(args)
    counts = db.get_counts_by_suburb()

    # load the suburb lists and the list of completed suburbs
    listed_suburbs = get_listed_suburbs()
    all_suburbs = get_all_suburbs()
    completed_suburbs = get_completed_suburbs_by_state()

    return {
        "listed": compare_address_counts(completed_suburbs, listed_suburbs, counts),
        "all": compare_address_counts(completed_suburbs, all_suburbs, counts),
    }


def print_progress(tally: dict):
    """print each row of a done/total/percent tally with a grant total at the bottom"""
    total_done = total = 0
    for key, info in tally.items():
        total_done += info["done"]
        total += info["total"]
        print(f"{key:>5}: {info['done']} / {info['total']} = {info['percent']:.1f}%")
    if "TOTAL" not in tally:
        print(f"Total: {total_done} / {total}  = {total_done / total * 100.0:.1f}%")


def get_suburb_progress(done_all_suburbs, vs_suburbs: dict):
    """Calculate a state-by-state progress indicator vs the named list of states+suburbs."""
    # convert state/suburb list to dict of suburb-sets
    vs_all_suburbs = {state: set(vs_suburbs.get(state, set())) for state in data.STATES}

    # we may have done suburbs that are not in the vs list: don't count them
    results = {}
    total_done = total_count = 0
    for state in data.STATES:
        state_done = done_all_suburbs[state] & vs_all_suburbs[state]
        done_percent = (len(state_done) / len(vs_all_suburbs[state]) * 100) if vs_all_suburbs[state] else 0
        total_done += len(state_done)
        total_count += len(vs_all_suburbs[state])
        results[state] = {
            "done": len(state_done),
            "total": len(vs_all_suburbs[state]),
            "percent": round(done_percent, 1),
        }
    results["TOTAL"] = {
        "done": total_done,
        "total": total_count,
        "percent": round(total_done / total_count * 100, 1),
    }
    return results


def print_upgrade_types():
    print("Upgrade types:")
    for k, v in sorted(UPGRADE_TALLY.items()):
        print(f"  {k}: {v}")


def main():
    parser = argparse.ArgumentParser(description="Emit a summary of progress against the list of suburbs in the DB.")
    parser.add_argument(
        "-s",
        "--simple",
        help="Whether to only update results.json and not the other files",
        action="store_true",
    )
    args = parser.parse_args()

    suburbs = collect_completed_suburbs()

    if args.simple:
        suburbs = update_existing_suburbs(suburbs)
        write_results_json(suburbs)
        return

    write_results_json(suburbs)

    # convert suburbs to same format as json files
    done_suburbs = {}
    for state in data.STATES:
        done_suburbs[state] = {suburb["internal"] for suburb in suburbs if suburb["state"] == state}

    print("Progress vs Listed Suburbs:")
    suburb_vs_listed = get_suburb_progress(done_suburbs, get_listed_suburbs())
    print_progress(suburb_vs_listed)

    print("Progress vs All Suburbs")
    suburb_vs_all = get_suburb_progress(done_suburbs, get_all_suburbs())
    print_progress(suburb_vs_all)

    print_upgrade_types()

    address_vs = collect_address_progress()
    print("Progress vs Addresses in Listed Suburbs")
    print_progress(address_vs["listed"])
    print("Progress vs Addresses in All Suburbs")
    print_progress(address_vs["all"])

    results = {
        "suburbs": {
            "listed": suburb_vs_listed,
            "all": suburb_vs_all,
        },
        "addresses": address_vs,
    }
    data.write_json_file("results/progress.json", results)  # indent=1 is to minimise size increase


if __name__ == "__main__":
    main()
