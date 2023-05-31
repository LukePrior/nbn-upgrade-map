import glob
import json
import os
from datetime import datetime

STATES = ["ACT", "NSW", "NT", "QLD", "SA", "TAS", "VIC", "WA"]


def collect_completed_suburbs():
    """Collect the list of completed suburbs from the results folder."""
    suburbs = []
    for state in STATES:
        for file in glob.glob(f"results/{state}/*.geojson"):
            filename, _ = os.path.splitext(os.path.basename(file))
            with open(file, "r", encoding="utf-8") as infile:
                result = json.load(infile)

            # fixup any missing generated dates
            if "generated" not in result:
                result["generated"] = datetime.now().isoformat()
                with open(file, "w", encoding="utf-8") as outfile:
                    json.dump(result, outfile, indent=1)  # indent=1 is to minimise size increase

            suburbs.append(
                {
                    "internal": filename.replace("-", " ").upper(),
                    "state": state,
                    "name": filename.replace("-", " ").title(),
                    "file": filename,
                    "date": datetime.fromisoformat(result["generated"]).strftime("%d-%m-%Y"),
                }
            )
    return suburbs


def write_results_json(suburbs: list):
    """Write the list of completed suburbs to a JSON file."""
    suburb_record = {"suburbs": sorted(suburbs, key=lambda k: (k["state"], k["name"]))}

    with open("results/results.json", "w") as outfile:
        json.dump(suburb_record, outfile, indent=4)


def print_progress(done_all_suburbs, vs_description: str, vs_file: str):
    """Display a state-by-state progress indicator vs the named list of states+suburbs."""
    # load suburbs list and convert to dict of suburb-sets
    with open(vs_file, "r", encoding="utf-8") as infile:
        vs_json = json.load(infile)
        vs_all_suburbs = {state: set(vs_json["states"].get(state, set())) for state in STATES}

    # we may have done suburbs that are not in the vs list: don't count them
    print(f"Progress vs {vs_description}:")
    total_done = total_count = 0
    for state in STATES:
        state_done = done_all_suburbs[state] & vs_all_suburbs[state]
        done_percent = len(state_done) / len(vs_all_suburbs[state]) * 100
        total_done += len(state_done)
        total_count += len(vs_all_suburbs[state])
        print(f"  {state}: {len(state_done)} / {len(vs_all_suburbs[state])}  ({done_percent:.1f}%)")
    print(f"  TOTAL: {total_done} / {total_count}  ({total_done / total_count * 100:.1f}%)")


if __name__ == "__main__":
    suburbs = collect_completed_suburbs()
    write_results_json(suburbs)

    # convert suburbs to same format as json files
    done_suburbs = {}
    for state in STATES:
        done_suburbs[state] = {suburb["internal"] for suburb in suburbs if suburb["state"] == state}

    print_progress(done_suburbs, "Listed Suburbs", "results/suburbs.json")
    print_progress(done_suburbs, "All Suburbs", "results/all_suburbs.json")
