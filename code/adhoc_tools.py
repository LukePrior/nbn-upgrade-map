#!/usr/bin/env python3
import argparse
import csv
import glob
import logging
import os
import pprint
import re
import subprocess
from collections import Counter, OrderedDict
from datetime import datetime, timedelta

import data
import db
import geojson
import main
import requests
import suburbs
import utils
from bs4 import BeautifulSoup
from tabulate import tabulate
from utils import get_all_features

NBN_UPGRADE_DATES_URL = (
    "https://www.nbnco.com.au/corporate-information/media-centre/media-statements/nbnco-announces-suburbs-and"
    "-towns-where-an-additional-ninty-thousand-homes-and-businesses-will-become-eligible-for-fibre-upgrades"
)


def get_nbn_suburb_dates():
    """Parse a NBN web page to get a list of all suburb upgrade dates."""
    logging.info("Fetching list of suburbs from NBN website...")
    content = requests.get(NBN_UPGRADE_DATES_URL).content

    results = {}

    soup = BeautifulSoup(content, "html.parser")
    for state_element in soup.find_all("div", class_="cmp-accordion__item"):
        state = state_element.find("span", class_="cmp-accordion__title").text
        results[state] = {}
        for p in state_element.find("div", class_="cmp-text").find_all("p"):
            for suburb, date in re.findall(r"^(.*) - from (\w+ \d{4})", p.text, flags=re.MULTILINE):
                results[state][suburb.title()] = date

    return results


def get_db_suburb_list(args):
    """Get list of all states and suburbs from the database"""
    xdb = db.connect_to_db(args)
    db_suburb_counts = xdb.get_counts_by_suburb()
    return {
        state: [s.title() for s in sorted(suburb_counts.keys())] for state, suburb_counts in db_suburb_counts.items()
    }


def add_address_count_to_suburbs(args):
    """Add address counts to Suburb objects"""
    xdb = db.connect_to_db(args)
    db_suburb_counts = xdb.get_counts_by_suburb()

    all_suburbs = suburbs.read_all_suburbs()
    for state, suburb_list in all_suburbs.items():
        for suburb in suburb_list:
            suburb.address_count = db_suburb_counts.get(state, {}).get(suburb.name.upper(), 0)
    suburbs.write_all_suburbs(all_suburbs)


def rebuild_status_file():
    """Fetch a list of all suburbs from DB, augment with processed+dates, and completed results"""
    # Load list of all suburbs from DB
    db_suburbs = get_db_suburb_list(args)
    db_suburbs["QLD"].append("Barwidgi")  # hack for empty suburb

    # TODO: Townsville not in DB. Why?  Two similar names included

    # convert to sets for faster operation
    db_suburbs = {state: set(suburb_list) for state, suburb_list in db_suburbs.items()}

    all_suburbs = {}  # state -> List[Suburb]
    for state, suburb_list in db_suburbs.items():
        all_suburbs[state] = []
        for suburb in suburb_list:
            processed_date = geojson.get_geojson_file_generated_from_name(suburb, state)
            xsuburb = data.Suburb(name=suburb, processed_date=processed_date)
            all_suburbs[state].append(xsuburb)

    suburbs.write_all_suburbs(all_suburbs)

    add_address_count_to_suburbs(args)


def resort_results():
    """Sort every one of the previously created geojson files by gnaf_pid"""
    for state in data.STATES:
        for file in glob.glob(f"results/{state}/*.geojson"):
            print(file)
            result = utils.read_json_file(file)
            result["features"] = sorted(result["features"], key=lambda x: x["properties"]["gnaf_pid"])
            utils.write_json_file(file, result, indent=1)


def get_suburb_extents():
    """Using the min/max lat/long of all addresses in each suburb, create a list of extents for each suburb"""
    xdb = db.connect_to_db(args)
    logging.info("Getting extents")
    result = xdb.get_extents_by_suburb()
    logging.info("Writing extents")
    # pprint.pprint(result)
    utils.write_json_file("results/suburb-extents.json", result, indent=1)


def update_all_suburbs_from_db():
    """Rewrite the (old) all_suburbs.json file from the DB.  This is a one-off."""
    db_suburbs = get_db_suburb_list(args)
    db_suburbs["QLD"].append("Barwidgi")  # hack for empty suburb
    db_suburbs["QLD"].sort()
    utils.write_json_file(
        "results/all_suburbs.json",
        {"states": {state: [suburb.upper() for suburb in suburb_list] for state, suburb_list in db_suburbs.items()}},
    )


def check_processing_rate():
    """Emit a table of the number of suburbs processed each day"""
    tally = Counter()
    for state, suburb_list in suburbs.read_all_suburbs().items():
        for suburb in suburb_list:
            if not suburb.processed_date:
                print(f"No processed date for {suburb.name}, {state}")
                continue
            tally[suburb.processed_date.date()] += 1

    items = sorted(tally.items())
    items.append(("TOTAL", sum(tally.values())))
    print(tabulate(items, headers=["date", "count"], tablefmt="github"))
    return items


def remove_duplicate_addresses():
    """Read all suburbs, and remove duplicate addresses from each suburb."""
    all_suburbs = suburbs.read_all_suburbs()
    for state, suburb_list in all_suburbs.items():
        for suburb in suburb_list:
            addresses, generated = geojson.read_geojson_file_addresses(suburb.name, state)
            new_addresses = main.remove_duplicate_addresses(addresses)
            if len(addresses) != len(new_addresses):
                geojson.write_geojson_file(suburb.name.upper(), state, new_addresses, generated)

    # No need to update progress, combined-suburbs: they are based on DB counts


def fix_gnaf_pid_mismatch():
    """Read all suburbs, and fix any gnaf_pid mismatches between the DB and the geojson files."""
    xdb = db.connect_to_db(args)

    all_suburbs = suburbs.read_all_suburbs()
    for state, suburb_list in all_suburbs.items():
        for suburb in suburb_list:
            logging.info("Processing %s, %s", suburb.name, state)
            db_addresses = xdb.get_addresses(suburb.name.upper(), state)
            db_lookup = {a.name: a.gnaf_pid for a in db_addresses}

            file_addresses, generated = geojson.read_geojson_file_addresses(suburb.name, state)

            changed = 0
            for a in file_addresses:
                db_gnaf_pid = db_lookup.get(a.name)
                if db_gnaf_pid and db_gnaf_pid != a.gnaf_pid:
                    # logging.info('Mismatch: %s db=%s file=%s', a.name, a.gnaf_pid, db_gnaf_pid)
                    a.gnaf_pid = db_gnaf_pid
                    changed += 1

            if changed:
                logging.info("Writing %s, %s - updated %d addresses", suburb.name, state, changed)
                geojson.write_geojson_file(suburb.name.upper(), state, file_addresses, generated)


def get_tech_and_upgrade_breakdown(root_dir=".") -> dict:
    """Generate some tallies for tech-type and upgrade-status for all addresses (slow)."""
    all_tech = Counter()
    all_upgrade = Counter()
    suburb_tech = {s: {} for s in data.STATES}  # [State][Suburb] = Counter()
    filenames = glob.glob(f"{root_dir}/results/**/*.geojson")
    for i, filename in enumerate(filenames):
        info = utils.read_json_file(filename)
        addresses = list(map(geojson.feature_to_address, info["features"]))
        all_tech.update(a.tech for a in addresses)
        all_upgrade.update(a.upgrade for a in addresses if a.tech != "FTTP")

        state = filename.split("/")[-2].upper()
        suburb = filename.split("/")[-1].replace(".geojson", "").replace("-", " ").title()
        suburb_tech[state][suburb] = Counter(a.tech for a in addresses)

        if i % 100 == 0:
            utils.print_progress_bar(i, len(filenames), prefix="Progress:", suffix="Complete", length=50)

    return {
        "tech": OrderedDict(all_tech.most_common()),
        "upgrade": OrderedDict(all_upgrade.most_common()),
        "suburb_tech": suburb_tech,
    }


def update_historical_tech_and_upgrade_breakdown():
    """Using git, generate/update a list of tech and upgrade breakdowns over time."""
    # use a separate checkout of the repo, so we don't have to worry about uncommitted changes
    checkout_dir = "../new-checkout"
    if not os.path.isdir(checkout_dir):
        subprocess.run(f"git clone git@github.com:LukePrior/nbn-upgrade-map.git {checkout_dir}", check=True, shell=True)

    # starting from ancient history, move forward 7 days at a time
    breakdown_file = "results/breakdown.json"
    breakdowns = utils.read_json_file(breakdown_file, True)
    breakdown_suburbs_file = "results/breakdown-suburbs.json"
    breakdown_suburbs = utils.read_json_file(breakdown_suburbs_file, True)

    co_date = datetime(2023, 5, 23)
    while co_date < datetime.now():
        date_key = co_date.date().isoformat()
        if date_key in breakdowns:
            logging.info("Skipping %s", date_key)
        else:
            logging.info("Processing %s", date_key)
            cmd = f"git checkout `git rev-list -n 1 --before=\"{co_date.strftime('%Y-%m-%d %H:%M')}\" main`"
            subprocess.run(cmd, check=True, cwd=checkout_dir, shell=True)
            breakdowns[date_key] = get_tech_and_upgrade_breakdown(checkout_dir)
            breakdown_suburbs[date_key] = breakdowns[date_key].pop("suburb_tech")
            utils.write_json_file(breakdown_file, breakdowns)  # save each time
            utils.write_json_file(breakdown_suburbs_file, breakdown_suburbs, indent=None)  # save each time
        co_date += timedelta(days=7)

    # print tech+upgrade breakdown
    for key in {"tech", "upgrade"}:
        rows = [{"date": run_date} | breakdowns[run_date][key] for run_date in sorted(breakdowns)]
        print()
        print(tabulate(rows, headers="keys", tablefmt="github"))


def generate_all_suburbs_nbn_tallies():
    """Create a file containing a tally of all suburbs by property (tech, upgrade, etc)"""
    exclude_properties = {"name", "locID", "gnaf_pid"}
    tallies = {}  # property-name -> Counter()
    for _, _, feature in get_all_features():
        for prop, value in feature["properties"].items():
            if prop not in exclude_properties:
                if prop not in tallies:
                    tallies[prop] = Counter()
                tallies[prop][value] += 1

    def _parse_quarter(item: tuple[str, int]):
        """Parse a quarter string into a datetime object.  If NA, return epoch."""
        try:
            return datetime.strptime(item[0], "%b %Y")
        except ValueError:
            return datetime.fromtimestamp(0)

    # sort tallies by frequency, except 'target_eligibility_quarter' which is sorted by date
    tallies = {
        k: OrderedDict(sorted(v.items(), key=_parse_quarter) if k == "target_eligibility_quarter" else v.most_common())
        for k, v in tallies.items()
    }

    # Add percentages and missing items
    total_count = sum(tallies["tech"].values())  # everything has a tech+NULL
    tallies["percent"] = {}
    for prop, kvs in tallies.items():
        if prop in {"tech", "upgrade", "percent"}:
            continue
        kvs["None"] = total_count - sum(kvs.values())
        tallies["percent"][prop] = {k: f"{100 * v / total_count:.2f}%" for k, v in kvs.items()}

    utils.write_json_file("results/all-suburbs-nbn-tallies.json", tallies, indent=1)


def generate_state_breakdown():
    """Generate results/breakdown.STATE.csv containing history of connection-types by state"""
    output = {}
    all_ctypes = set()
    for date, state_info in utils.read_json_file("results/breakdown-suburbs.json").items():
        logging.info("Processing %s", date)
        output[date] = {}
        for state, suburb_list in state_info.items():
            # logging.info("  State: %s", state)
            state_tally = {}
            for suburb, connections in suburb_list.items():
                # logging.info("    State: %s", suburb)
                for ctype, ccount in connections.items():
                    state_tally[ctype] = state_tally.get(ctype, 0) + ccount
                    all_ctypes.add(ctype)
            output[date][state] = state_tally
    utils.write_json_file("results/breakdown-state.json", output)

    # write CSV per state
    for state in data.STATES:
        rows = [
            {"date": date} | {ctype: output[date].get(state, {}).get(ctype, 0) for ctype in all_ctypes}
            for date in output
        ]
        with open(f"results/breakdown.{state}.csv", "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(rows[0].keys())
            writer.writerows(r.values() for r in rows)


def fix_fw_tech_type():
    """Fix any tech-type 'fw' should be 'wireless'."""
    for _, _, feature in get_all_features(rewrite_geojson=True):
        if feature["properties"]["tech"] == "FW":
            feature["properties"]["tech"] = "WIRELESS"


def fix_fw_tech_type_breakdowns():
    """Fix any tech-type 'FW' should be 'WIRELES' in breakdown files."""

    def fix_tech_breakdown(tech):
        """Move any FW values to WIRELESS."""
        if "FW" in tech:
            tech["WIRELESS"] += tech["FW"]
            del tech["FW"]

    # breakdown.json
    breakdowns = utils.read_json_file("results/breakdown.json")
    for date, date_info in breakdowns.items():
        fix_tech_breakdown(date_info["tech"])
    utils.write_json_file("results/breakdown.json", breakdowns)

    # breakdown-suburbs.json
    breakdowns = utils.read_json_file("results/breakdown-suburbs.json")
    for date, date_info in breakdowns.items():
        for state, suburb_list in date_info.items():
            for suburb, breakdown in suburb_list.items():
                fix_tech_breakdown(breakdown)
    utils.write_json_file("results/breakdown-suburbs.json", breakdowns, indent=None)

    # breakdown-state.json and breakdown.STATE.csv (uses breakdown-suburbs.json)
    generate_state_breakdown()


def check_tech_change_status_upgrade():
    """Emit tally on the upgrade field for all locations with tech_change_status."""
    tallies = {}
    for _, _, feature in get_all_features():
        tech_change = feature["properties"].get("tech_change_status")
        if tech_change:
            if tech_change not in tallies:
                tallies[tech_change] = Counter()
            tallies[tech_change][feature["properties"].get("upgrade")] += 1

    pprint.pprint(tallies)


def fix_ct_upgrades():
    """Update all locations with upgrade=XXX_CT and tech=OTHER to be tech=XXX and upgrade=OTHER"""
    for _, _, feature in get_all_features(rewrite_geojson=True):
        upgrade_val = feature["properties"]["upgrade"]
        if upgrade_val in main.CT_UPGRADE_MAP:
            feature["properties"]["upgrade"] = feature["properties"]["tech"]
            feature["properties"]["tech"] = main.CT_UPGRADE_MAP[upgrade_val]

    # update breakdown.json and breakdown-suburbs.json
    update_breakdown()
    # update breakdown-state.json and breakdown.STATE.csv
    generate_state_breakdown()


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
        utils.write_json_file(breakdown_suburbs_file, breakdown_suburbs, indent=None)

    return breakdowns


def dump_status_tech_upgrade():
    """Dump the tech and upgrade breakdowns to the console."""
    tallies = {}  # status -> tech -> upgrade:count
    for _, _, feature in get_all_features():
        status = feature["properties"].get("tech_change_status", "?")
        tech = feature["properties"]["tech"]
        upgrade = feature["properties"]["upgrade"]
        if status not in tallies:
            tallies[status] = {}
        if tech not in tallies[status]:
            tallies[status][tech] = {}
        tallies[status][tech][upgrade] = tallies[status][tech].get(upgrade, 0) + 1

    pprint.pprint(tallies)


def generate_local_website():
    """Generate a version of the website with all data local."""
    # copy index.html -> index-local.html
    with open("./site/index.html") as f:
        index_html = f.read().replace("main.js", "main-local.js")
        with open("./site/index-local.html", "w") as f:
            f.write(index_html)

    # copy main.js -> main-local.js
    with open("./site/main.js") as f:
        gh_prefix = "https://raw.githubusercontent.com/LukePrior/nbn-upgrade-map"
        main_js = (
            f.read()
            # use local results files
            .replace(gh_prefix + "/main/results", "../results")
            .replace(gh_prefix + '/" + commit + "/results', "../results")
            # disable serviceworkerr
            .replace("navigator.serviceWorker.", "// ")
            # disable date selector
            .replace("addControlWithHTML('date-selector'", "// ")
            .replace("fetch(commits_url)", "new Promise( () => {} )")
            # disable gtags
            .replace("gtag(", "// gtag(")
        )

        with open("./site/main-local.js", "w") as f:
            f.write(main_js)

    # to view this locally, start a simple web-server with the following command (from the top level directory):
    #     python -m http.server 8000
    # and open http://localhost:8000/site/index-local.html


if __name__ == "__main__":
    LOGLEVEL = os.environ.get("LOGLEVEL", "INFO").upper()
    logging.basicConfig(level=LOGLEVEL, format="%(asctime)s %(levelname)s %(threadName)s %(message)s")

    parser = argparse.ArgumentParser(
        description="Run adhoc utility functions to do various maintenence-type activitirs."
    )
    parser.add_argument("run_functions", help="Comma-separated list of no-arg functions to run")
    db.add_db_arguments(parser)
    args = parser.parse_args()

    for f in args.run_functions.split(","):
        if f not in globals():
            raise Exception(f"Unknown function: {f}")
        globals()[f]()
