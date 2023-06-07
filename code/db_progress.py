"""Emit a summary of progress against the list of suburbs in the DB."""
import argparse
import json
import logging
import os

from db import add_db_arguments, connect_to_db


def main():
    parser = argparse.ArgumentParser(description="Emit a summary of progress against the list of suburbs in the DB.")
    add_db_arguments(parser)
    args = parser.parse_args()
    db = connect_to_db(args)

    with open("results/suburbs.json", "r", encoding="utf-8") as file:
        suburb_list = json.load(file)

        progress = db.get_progress(suburb_list["states"])
        for state, sp in progress.items():
            s_completed, s_total = sp.get("completed", 0), sp.get("total", 0)
            logging.info("%5s: %d/%d (%.1f%%)", state, s_completed, s_total, s_completed / s_total * 100)

    # TODO: write progress to a file, to be used by badges etc


if __name__ == "__main__":
    LOGLEVEL = os.environ.get("LOGLEVEL", "INFO").upper()
    logging.basicConfig(level=LOGLEVEL, format="%(asctime)s %(levelname)s %(threadName)s %(message)s")
    main()
