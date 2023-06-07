import argparse
import glob
import json
import os
from collections import Counter
from datetime import datetime
from typing import Dict, List

import data
from db import add_db_arguments, connect_to_db

UPGRADE_TALLY = Counter()


def collect_completed_suburbs():
    """Collect the list of completed suburbs from the results folder."""
    suburbs = []
    for state in data.STATES:
        for file in glob.glob(f"results/{state}/*.geojson"):
            filename, _ = os.path.splitext(os.path.basename(file))
            with open(file, "r", encoding="utf-8") as infile:
                result = json.load(infile)

            # Check if result has a "suburb" field
            suburb = result.get("suburb", filename.replace("-", " "))

            # fixup any missing generated dates
            if "generated" not in result:
                result["generated"] = datetime.now().isoformat()
                with open(file, "w", encoding="utf-8") as outfile:
                    json.dump(result, outfile, indent=1)  # indent=1 is to minimise size increase

            UPGRADE_TALLY.update(feature["properties"].get("upgrade", "") for feature in result["features"])

            suburbs.append(
                {
                    "internal": suburb.upper(),
                    "state": state,
                    "name": suburb.title(),
                    "file": filename,
                    "date": datetime.fromisoformat(result["generated"]).strftime("%d-%m-%Y"),
                }
            )
    return suburbs


def write_results_json(suburbs: List[Dict]):
    """Write the list of completed suburbs to a JSON file."""
    suburb_record = {"suburbs": sorted(suburbs, key=lambda k: (k["state"], k["name"]))}

    with open("results/results.json", "w") as outfile:
        json.dump(suburb_record, outfile, indent=4)


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
        results[state] = {"done": completed, "total": total, "percent": round(completed / total * 100,1)}
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
    with open("results/suburbs.json", "r", encoding="utf-8") as file:
        listed_suburbs = json.load(file)["states"]
    with open("results/all_suburbs.json", "r", encoding="utf-8") as file:
        all_suburbs = json.load(file)["states"]
    with open("results/results.json", "r", encoding="utf-8") as file:
        completed_suburbs = {state: set() for state in data.STATES}
        for suburb in json.load(file)["suburbs"]:
            completed_suburbs[suburb["state"]].add(suburb["internal"])

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


def get_suburb_progess(done_all_suburbs, vs_file: str):
    """Calculate a state-by-state progress indicator vs the named list of states+suburbs."""
    # load suburbs list and convert to dict of suburb-sets
    with open(vs_file, "r", encoding="utf-8") as infile:
        vs_json = json.load(infile)
        vs_all_suburbs = {state: set(vs_json["states"].get(state, set())) for state in data.STATES}

    # we may have done suburbs that are not in the vs list: don't count them
    results = {}
    total_done = total_count = 0
    for state in data.STATES:
        state_done = done_all_suburbs[state] & vs_all_suburbs[state]
        done_percent = len(state_done) / len(vs_all_suburbs[state]) * 100
        total_done += len(state_done)
        total_count += len(vs_all_suburbs[state])
        results[state] = {"done": len(state_done), "total": len(vs_all_suburbs[state]), "percent": round(done_percent,1)}
    results["TOTAL"] = {
        "done": total_done,
        "total": total_count,
        "percent": round(total_done / total_count * 100,1),
    }
    return results


def print_upgrade_types():
    print("Upgrade types:")
    for k, v in sorted(UPGRADE_TALLY.items()):
        print(f"  {k}: {v}")


def main():
    suburbs = collect_completed_suburbs()
    write_results_json(suburbs)

    # convert suburbs to same format as json files
    done_suburbs = {}
    for state in data.STATES:
        done_suburbs[state] = {suburb["internal"] for suburb in suburbs if suburb["state"] == state}

    print("Progress vs Listed Suburbs:")
    suburb_vs_listed = get_suburb_progess(done_suburbs, "results/suburbs.json")
    print_progress(suburb_vs_listed)

    print("Progress vs All Suburbs")
    suburb_vs_all = get_suburb_progess(done_suburbs, "results/all_suburbs.json")
    print_progress(suburb_vs_all)

    print_upgrade_types()

    address_vs = collect_address_progress()
    print("Progress vs Addresses in Listed Suburbs")
    print_progress(address_vs["listed"])
    print("Progress vs Addresses in All Suburbs")
    print_progress(address_vs["all"])

    with open("results/progress.json", "w") as outfile:
        results = {
            "suburbs": {
                "listed": suburb_vs_listed,
                "all": suburb_vs_all,
            },
            "addresses": address_vs,
        }
        json.dump(results, outfile, indent=4)


if __name__ == "__main__":
    main()
