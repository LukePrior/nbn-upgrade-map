# api for managing the list of suburbs, which ones have been completed, dates announced, etc.
import dataclasses
import itertools
import logging
from collections import Counter
from datetime import datetime

import data


def get_completed_suburbs() -> list[dict]:
    """Return a flat of all suburbs by state that have been completed. (compatibility api)"""
    # deprecated
    #         {
    #             "internal": "ACTON",
    #             "state": "ACT",
    #             "name": "Acton",
    #             "file": "acton",
    #             "date": "07-07-2023"  # replaced with ISO format
    #         },
    by_state = [
        [
            {
                "internal": suburb.internal,
                "state": state,
                "name": suburb.name,
                "file": suburb.file,
                "date": suburb.processed_date.isoformat() if suburb.processed_date else None,
            }
            for suburb in suburb_list
            if suburb.processed_date
        ]
        for state, suburb_list in read_all_suburbs().items()
    ]
    return list(itertools.chain.from_iterable(by_state))


def write_results_json(suburbs: list[dict]):
    """Write the list of completed suburbs to a JSON file."""
    # Compatibility with previous API. To be refactored.

    # make state->suburb->date lookup
    suburb_dates_by_state = {state: {} for state in data.STATES}
    for suburb in suburbs:
        suburb_dates_by_state[suburb["state"]][suburb["name"]] = suburb["date"]

    # update date field in results only
    all_suburbs = read_all_suburbs()
    for state, suburb_list in all_suburbs.items():
        for suburb in suburb_list:
            suburb.processed_date = suburb_dates_by_state[state].get(suburb.name, None)

    write_all_suburbs(all_suburbs)


def write_all_suburbs(all_suburbs: dict[str, list[data.Suburb]]):
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
    data.write_json_file("results/combined-suburbs.json", all_suburbs_dicts, indent=1)


def read_all_suburbs() -> dict[str, list[data.Suburb]]:
    """Read the new combined file list of all suburbs."""

    def _dict_to_suburb(d: dict) -> data.Suburb:
        d["processed_date"] = datetime.fromisoformat(d["processed_date"]) if d["processed_date"] else None
        return data.Suburb(**d)

    results = data.read_json_file("results/combined-suburbs.json")
    # TODO: convert to dict[str, dict[str, data.Suburb]]  (state->suburub_name->Suburb)
    return {state: sorted(_dict_to_suburb(d) for d in results[state]) for state in sorted(results)}


def update_suburb_in_all_suburbs(suburb: str, state: str) -> dict[str, list[data.Suburb]]:
    """Update the suburb in the combined file."""
    suburb = suburb.title()

    all_suburbs = read_all_suburbs()
    found_suburb = next(s for s in all_suburbs[state.upper()] if s.name == suburb)
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
