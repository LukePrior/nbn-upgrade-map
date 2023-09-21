#!/usr/bin/env python3
"""a cut-down version of update_historical_tech_and_upgrade_breakdown() that processes the current checkout"""

import logging
import os
from datetime import datetime

import utils
from adhoc_tools import get_tech_and_upgrade_breakdown
from tabulate import tabulate

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    breakdown_file = "results/breakdown.json"
    co_date = datetime.now().date()
    breakdowns = utils.read_json_file(breakdown_file) if os.path.exists(breakdown_file) else {}
    if co_date.isoformat() in breakdowns:
        logging.info("Skipping %s", co_date)
    else:
        logging.info("Processing %s", co_date)
        breakdowns[co_date.isoformat()] = get_tech_and_upgrade_breakdown()
        utils.write_json_file(breakdown_file, breakdowns)

    for key in {"tech", "upgrade"}:
        rows = [{"date": run_date} | breakdowns[run_date][key] for run_date in sorted(breakdowns)]
        print()
        print(tabulate(rows, headers="keys", tablefmt="github"))
