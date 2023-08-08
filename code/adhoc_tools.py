import argparse
import glob
import logging
import os
import re
from collections import Counter

import data
import db
import geojson
import requests
import suburbs
import utils
from bs4 import BeautifulSoup
from tabulate import tabulate

NBN_UPGRADE_DATES_URL = "https://www.nbnco.com.au/residential/upgrades/more-fibre"

NBN_SUBURB_LIST_URL = (
    "https://www.nbnco.com.au/corporate-information/media-centre/media-statements/nbnco-announces-suburbs-and"
    "-towns-where-an-additional-ninty-thousand-homes-and-businesses-will-become-eligible-for-fibre-upgrades"
)


def get_nbn_suburb_dates():
    """Parse a NBN web page to get a list of all suburb upgrade dates."""
    logging.info("Fetching list of suburbs from NBN website...")
    content = requests.get(NBN_UPGRADE_DATES_URL).content

    results = {}

    soup = BeautifulSoup(content, "html.parser")
    for state_element in soup.find(id="accordion-c467de9e93").find_all("div", class_="cmp-accordion__item"):
        state = state_element.find("span", class_="cmp-accordion__title").text
        results[state] = {}
        for p in state_element.find("div", class_="cmp-text").find_all("p"):
            for suburb, date in re.findall(r"^(.*) - from (\w+ \d{4})", p.text, flags=re.MULTILINE):
                results[state][suburb] = date

    # Convert to consistent state/suburb format
    return {state: {s.title(): d for s, d in suburb_list.items()} for state, suburb_list in results.items()}


def get_nbn_suburb_list():
    """Parse a NBN web page to get a list of all suburbs announced for upgrades."""
    logging.info("Fetching list of suburb dates from NBN website...")
    content = requests.get(NBN_SUBURB_LIST_URL).content

    results = {}

    soup = BeautifulSoup(content, "html.parser")
    for state_element in soup.find_all("div", class_="cmp-accordion__item"):
        state = state_element.find("span", class_="cmp-accordion__title").text
        results[state] = []
        for p in state_element.find("div", class_="cmp-text").find_all("p"):
            if p.text.startswith("Announced "):
                continue
            # remove extra text, and sanitise suburb names
            suburbs_list = [
                re.sub(
                    r"( \(ADDITIONAL FOOTPRINT\)|ADDITIONAL AREAS OF | \(4350\))",
                    "",
                    suburb.strip("*#.\xa0\r\n").replace("’", "'"),
                    flags=re.IGNORECASE,
                )
                for suburb in re.split(r", ?", p.text)
            ]
            results[state].extend(suburbs_list)

    # Convert to consistent state/suburb format
    return {data.STATES_MAP[state]: [s.title() for s in suburbs_list] for state, suburbs_list in results.items()}


def get_db_suburb_list():
    """Get list of all states and suburbs from the database"""
    xdb = db.connect_to_db(args)
    db_suburb_counts = xdb.get_counts_by_suburb()
    return {
        state: [s.title() for s in sorted(suburb_counts.keys())] for state, suburb_counts in db_suburb_counts.items()
    }


def add_address_count_to_suburbs():
    """Add address counts to Suburb objects"""
    xdb = db.connect_to_db(args)
    db_suburb_counts = xdb.get_counts_by_suburb()

    all_suburbs = suburbs.read_all_suburbs()
    for state, suburb_list in all_suburbs.items():
        for suburb in suburb_list:
            suburb.address_count = db_suburb_counts[state].get(suburb.name.upper(), 0)
    suburbs.write_all_suburbs(all_suburbs)


def rebuild_status_file():
    """Fetch a list of all suburbs from DB, augment with announced+dates, and completed results"""
    # Load list of all suburbs from DB
    db_suburbs = get_db_suburb_list()
    db_suburbs["QLD"].append("Barwidgi")  # hack for empty suburb

    # Load list of all announced suburbs from NBN website
    announced_suburbs = get_nbn_suburb_list()

    # Load list of all suburb dates from NBN website
    suburb_dates = get_nbn_suburb_dates()
    utils.write_json_file("results/suburb-dates.json", suburb_dates)

    # TODO: Townsville not in DB. Why?  Two similar names included

    # add OT
    if "OT" not in announced_suburbs:
        announced_suburbs["OT"] = []
    if "OT" not in suburb_dates:
        suburb_dates["OT"] = {}

    # convert to sets for faster operation
    announced_suburbs = {state: set(suburb_list) for state, suburb_list in announced_suburbs.items()}
    db_suburbs = {state: set(suburb_list) for state, suburb_list in db_suburbs.items()}

    all_suburbs = {}  # state -> List[Suburb]
    for state, suburb_list in db_suburbs.items():
        all_suburbs[state] = []
        for suburb in suburb_list:
            announced = suburb in announced_suburbs[state]
            announced_date = suburb_dates[state].get(suburb, None)
            if announced_date:
                announced = True  # implicit announcement - if we have a date, then it's announced
            processed_date = geojson.get_geojson_file_generated_from_name(suburb, state)
            xsuburb = data.Suburb(
                name=suburb,
                announced=announced,
                announced_date=announced_date,
                processed_date=processed_date,
            )
            all_suburbs[state].append(xsuburb)

    suburbs.write_all_suburbs(all_suburbs)

    add_address_count_to_suburbs()


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
    db_suburbs = get_db_suburb_list()
    db_suburbs["QLD"].append("Barwidgi")  # hack for empty suburb
    db_suburbs["QLD"].sort()
    utils.write_json_file(
        "results/all_suburbs.json",
        {"states": {state: [suburb.upper() for suburb in suburb_list] for state, suburb_list in db_suburbs.items()}},
    )


def check_processing_rate():
    """Emit a table of the number of suburbs processed each day (announced vs other)"""
    announced_tally = Counter()
    other_tally = Counter()
    for state, suburb_list in suburbs.read_all_suburbs().items():
        for suburb in suburb_list:
            tally = announced_tally if suburb.announced else other_tally
            tally[suburb.processed_date.date()] += 1

    data = [
        (day, announced_tally.get(day), other_tally.get(day))
        for day in sorted(announced_tally.keys() | other_tally.keys())
    ]
    data.append(("TOTAL", sum(announced_tally.values()), sum(other_tally.values())))

    print(tabulate(data, headers=["date", "announced", "other"], tablefmt="github"))


if __name__ == "__main__":
    LOGLEVEL = os.environ.get("LOGLEVEL", "INFO").upper()
    logging.basicConfig(level=LOGLEVEL, format="%(asctime)s %(levelname)s %(threadName)s %(message)s")

    parser = argparse.ArgumentParser(description="Emit a summary of progress against the list of suburbs in the DB.")
    db.add_db_arguments(parser)
    args = parser.parse_args()

    # resort_results()
    # add_to_announced_suburbs()
    # get_suburb_extents
    # update_all_suburbs_from_db()

    # rebuild_status_file()
    check_processing_rate()
    # add_address_count_to_suburbs()
    # add_address_count_to_suburbs()
    # blah = read_all_suburbs()
    # blah = geojson.read_json_file("results/all-suburbs.json")

    # geojson.write_json_file("results/suburb-dates.json", get_nbn_suburb_dates())

    # update_suburb_dates()
    # compare_suburb_lists()
    # compare_db_suburbs()
