# api for managing the list of suburbs, which ones have been completed, dates announced, etc.
import dataclasses
import glob
import logging
import os
from collections import Counter
from datetime import datetime

import data
import utils
from geojson import get_geojson_file_generated, get_geojson_file_generated_from_name


def write_all_suburbs(all_suburbs: data.SuburbsByState):
    """Write the new combined file containing all suburbs to a file."""

    def _suburb_to_dict(s: data.Suburb) -> dict:
        d = dataclasses.asdict(s)
        if d["processed_date"]:
            d["processed_date"] = d["processed_date"].isoformat()
        return d

    all_suburbs_dicts = {
        state: [_suburb_to_dict(xsuburb) for xsuburb in sorted(suburbs_list)]
        for state, suburbs_list in sorted(all_suburbs.items())
    }
    utils.write_json_file("results/combined-suburbs.json", all_suburbs_dicts, indent=1)


def read_all_suburbs() -> data.SuburbsByState:
    """Read the new combined file list of all suburbs."""

    def _dict_to_suburb(d: dict) -> data.Suburb:
        d["processed_date"] = datetime.fromisoformat(d["processed_date"]) if d["processed_date"] else None
        return data.Suburb(**d)

    results = utils.read_json_file("results/combined-suburbs.json")
    # TODO: convert to dict[str, dict[str, data.Suburb]]  (state->suburub_name->Suburb)
    return {state: sorted(_dict_to_suburb(d) for d in results[state]) for state in sorted(results)}


def update_processed_dates():
    """Check if any new/updated geojson files need to be updated in the all-suburbs file."""
    logging.info("Checking for externally updated geojson results...")
    all_suburbs = read_all_suburbs()
    changed = False
    for state in data.STATES:
        file_suburb_map = {suburb.file: suburb for suburb in all_suburbs.get(state, [])}
        for file in glob.glob(f"results/{state}/*.geojson"):
            this_file = os.path.splitext(os.path.basename(file))[0]
            this_suburb = file_suburb_map.get(this_file)
            generated = get_geojson_file_generated(file)

            if this_suburb.processed_date is None or (generated - this_suburb.processed_date).total_seconds() > 0:
                logging.info("   Updating %s/%s processed date %s", state, this_suburb.name, generated)
                this_suburb.processed_date = generated
                changed = True
    if changed:
        write_all_suburbs(all_suburbs)
    logging.info("...done")


def update_suburb_in_all_suburbs(suburb: str, state: str) -> data.SuburbsByState:
    """Update the suburb in the combined file."""
    suburb = suburb.title()

    all_suburbs = read_all_suburbs()
    found_suburb = next(s for s in all_suburbs[state.upper()] if s.name == suburb)
    found_suburb.processed_date = get_geojson_file_generated_from_name(suburb, state)
    if found_suburb.processed_date is None:
        found_suburb.processed_date = datetime.now()
    write_all_suburbs(all_suburbs)

    update_progress()
    return all_suburbs


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


def get_suburb_progress() -> dict:
    """Calculate a state-by-state progress indicator vs the named list of states+suburbs."""
    progress = {"listed": {}, "all": {}}
    for state, suburb_list in read_all_suburbs().items():
        progress["listed"][state] = _get_completion_progress(suburb for suburb in suburb_list if suburb.announced)
        progress["all"][state] = _get_completion_progress(suburb_list)

    _add_total_progress(progress["listed"])
    _add_total_progress(progress["all"])
    return progress


def get_address_progress() -> dict:
    """Calculate a state-by-state progress indicator vs the named list of states+suburbs."""
    progress = {"listed": {}, "all": {}}
    for state, suburb_list in read_all_suburbs().items():
        tot_addresses = tot_listed = 0
        tot_done = tot_listed_done = 0
        for suburb in suburb_list:
            tot_addresses += suburb.address_count
            if suburb.announced:
                tot_listed += suburb.address_count

            if suburb.processed_date is not None:
                tot_done += suburb.address_count
                if suburb.announced:
                    tot_listed_done += suburb.address_count

        progress["listed"][state] = {
            "done": tot_listed_done,
            "total": tot_listed,
            "percent": _format_percent(tot_listed_done, tot_listed),
        }
        progress["all"][state] = {
            "done": tot_done,
            "total": tot_addresses,
            "percent": _format_percent(tot_done, tot_addresses),
        }

    _add_total_progress(progress["listed"])
    _add_total_progress(progress["all"])
    return progress


def update_progress():
    """Update the progress.json file with the latest results."""
    results = {
        "suburbs": get_suburb_progress(),
        "addresses": get_address_progress(),
    }
    logging.info("Updating progress.json")
    utils.write_json_file("results/progress.json", results)  # indent=1 is to minimise size increase
    return results["suburbs"]
