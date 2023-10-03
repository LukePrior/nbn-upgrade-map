#!/usr/bin/env python3
"""a cut-down version of update_historical_tech_and_upgrade_breakdown() that processes the current checkout"""

import logging
from datetime import datetime

import utils
from adhoc_tools import get_tech_and_upgrade_breakdown
from tabulate import tabulate


def update_breakdown():
    """Update the breakdown.json file with the latest results (vs current checkout)."""
    breakdown_file = "results/breakdown.json"
    breakdowns = utils.read_json_file(breakdown_file, True)
    breakdown_suburbs_file = "results/breakdown-suburbs.json"
    breakdown_suburbs = utils.read_json_file(breakdown_suburbs_file, True)
    date_key = datetime.now().date().isoformat()
    if date_key in breakdowns:
        logging.info("Skipping %s", date_key)
    else:
        logging.info("Processing %s", date_key)
        breakdowns[date_key] = get_tech_and_upgrade_breakdown()
        breakdown_suburbs[date_key] = breakdowns[date_key].pop("suburb_tech")
        utils.write_json_file(breakdown_file, breakdowns)
        utils.write_json_file(breakdown_suburbs_file, breakdown_suburbs)

    return breakdowns


def print_breakdowns(breakdowns):
    """Dump the breakdowns to the console as tables."""
    for key in {"tech", "upgrade"}:
        rows = [{"date": run_date} | breakdowns[run_date][key] for run_date in sorted(breakdowns)]
        print()
        print(tabulate(rows, headers="keys", tablefmt="github"))


if __name__ == "__main__":  # pragma: no cover
    logging.basicConfig(level=logging.INFO)
    bd = update_breakdown()
    print_breakdowns(bd)
