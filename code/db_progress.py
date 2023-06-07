"""Emit a summary of progress against the list of suburbs in the DB."""
import argparse
import json
import logging
import os

import data
from db import add_db_arguments, connect_to_db


def print_progress_vs(label: str, completed_suburbs: dict, vs_suburbs: dict, counts: dict):
    """Print a summary of progress against the list of suburbs in the DB."""
    logging.info("Address progress vs %s:", label)
    all_completed = all_total = 0
    for state, suburbs in vs_suburbs.items():
        completed = total = 0
        for suburb in suburbs:
            suburb_count = counts[state].get(suburb, 0)
            if suburb in completed_suburbs.get(state, set()):
                completed += suburb_count
            total += suburb_count
        logging.info("  %s: %d / %d  (%.1f%%)", state, completed, total, completed / total * 100)
        all_completed += completed
        all_total += total

    logging.info("  %s: %d / %d  (%.1f%%)", "Total", all_completed, all_total, all_completed / all_total * 100)


def main():
    parser = argparse.ArgumentParser(description="Emit a summary of progress against the list of suburbs in the DB.")
    add_db_arguments(parser)
    args = parser.parse_args()
    db = connect_to_db(args)

    counts = db.get_counts_by_suburb()

    with open("results/suburbs.json", "r", encoding="utf-8") as file:
        listed_suburbs = json.load(file)["states"]
    with open("results/all_suburbs.json", "r", encoding="utf-8") as file:
        all_suburbs = json.load(file)["states"]
    with open("results/results.json", "r", encoding="utf-8") as file:
        completed_suburbs = {state: set() for state in data.STATES}
        for suburb in json.load(file)["suburbs"]:
            completed_suburbs[suburb["state"]].add(suburb["internal"])

    print_progress_vs("Listed Suburbs", completed_suburbs, listed_suburbs, counts)
    print_progress_vs("All Suburbs", completed_suburbs, all_suburbs, counts)
    # TODO: write progress to a file, to be used by badges etc


if __name__ == "__main__":
    LOGLEVEL = os.environ.get("LOGLEVEL", "INFO").upper()
    logging.basicConfig(level=LOGLEVEL, format="%(asctime)s %(message)s")
    main()
