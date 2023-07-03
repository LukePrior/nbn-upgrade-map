import argparse
import dataclasses
import logging
import os
import re
from datetime import datetime

import data
import db
import geojson
import requests
from bs4 import BeautifulSoup


def get_nbn_suburb_dates():
    """Parse a NBN web page to get a list of all suburb upgrade dates."""
    URL = "https://www.nbnco.com.au/residential/upgrades/more-fibre"
    logging.info("Fetching list of suburbs from NBN website...")
    content = requests.get(URL).content

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
    URL = (
        "https://www.nbnco.com.au/corporate-information/media-centre/media-statements/nbnco-announces-suburbs-and"
        "-towns-where-an-additional-ninty-thousand-homes-and-businesses-will-become-eligible-for-fibre-upgrades"
    )
    logging.info("Fetching list of suburb dates from NBN website...")
    content = requests.get(URL).content

    results = {}

    soup = BeautifulSoup(content, "html.parser")
    for state_element in soup.find_all("div", class_="cmp-accordion__item"):
        state = state_element.find("span", class_="cmp-accordion__title").text
        results[state] = []
        for p in state_element.find("div", class_="cmp-text").find_all("p"):
            if p.text.startswith("Announced "):
                continue
            # remove extra text, and sanitise suburb names
            suburbs = [
                re.sub(
                    r"( \(ADDITIONAL FOOTPRINT\)|ADDITIONAL AREAS OF | \(4350\))",
                    "",
                    suburb.strip("*#.\xa0\r\n").replace("’", "'"),
                    flags=re.IGNORECASE,
                )
                for suburb in re.split(r", ?", p.text)
            ]
            results[state].extend(suburbs)

    # Convert to consistent state/suburb format
    return {data.STATES_MAP[state]: [s.title() for s in suburbs] for state, suburbs in results.items()}


def get_db_suburb_list():
    """Get list of all states and suburbs from the database"""
    xdb = db.connect_to_db(args)
    db_suburb_counts = xdb.get_counts_by_suburb()
    return {
        state: [s.title() for s in sorted(suburb_counts.keys())] for state, suburb_counts in db_suburb_counts.items()
    }


def rebuild_status_file():
    """Fetch a list of all suburbs from DB, augment with announced+dates, and completed results"""
    # Load list of all suburbs from DB
    db_suburbs = get_db_suburb_list()
    # geojson.write_json_file("results/db-counts.json", db_suburbs)
    # db_suburbs = geojson.read_json_file("results/db-counts.json")

    # Load list of all announced suburbs from NBN website
    announced_suburbs = get_nbn_suburb_list()
    # geojson.write_json_file("results/announced.json", announced_suburbs)
    # with open("results/announced.json", "r", encoding="utf-8") as file:
    #     announced_suburbs = json.load(file)
    # announced_suburbs = geojson.read_json_file("results/announced.json")

    # Load list of all suburb dates from NBN website
    suburb_dates = get_nbn_suburb_dates()
    # geojson.write_json_file("results/suburb-dates.json", suburb_dates)
    # suburb_dates = geojson.read_json_file("results/suburb-dates.json")

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
            processed_date = geojson.get_geojson_file_generated(suburb, state)
            xsuburb = data.Suburb(
                name=suburb,
                state=state,
                announced=announced,
                announced_date=announced_date,
                processed_date=processed_date,
            )
            all_suburbs[state].append(xsuburb)

            if announced and announced_date is None:
                print(f"Announced {suburb}, {state} - but no date")

    write_all_suburbs(all_suburbs)


def write_all_suburbs(all_suburbs: dict):  # Dict[str, List[data.Suburb]]
    """Write the list of all suburbs to a file."""

    def _suburb_to_dict(s: data.Suburb) -> dict:
        d = dataclasses.asdict(s)
        if d["processed_date"]:
            d["processed_date"] = d["processed_date"].isoformat()
        return d

    all_suburbs_dicts = {
        state: [_suburb_to_dict(xsuburb) for xsuburb in suburbs_list] for state, suburbs_list in all_suburbs.items()
    }
    geojson.write_json_file("results/all-suburbs.json", all_suburbs_dicts)


def read_all_suburbs() -> dict:
    """Read the list of all suburbs from a file."""

    def _dict_to_suburb(d: dict) -> data.Suburb:
        d["processed_date"] = datetime.fromisoformat(d["processed_date"]) if d["processed_date"] else None
        return data.Suburb(**d)

    results = geojson.read_json_file("results/all-suburbs.json")
    return {state: [_dict_to_suburb(d) for d in suburbs_list] for state, suburbs_list in results.items()}


if __name__ == "__main__":
    LOGLEVEL = os.environ.get("LOGLEVEL", "INFO").upper()
    logging.basicConfig(level=LOGLEVEL, format="%(asctime)s %(levelname)s %(threadName)s %(message)s")

    parser = argparse.ArgumentParser(description="Emit a summary of progress against the list of suburbs in the DB.")
    db.add_db_arguments(parser)
    args = parser.parse_args()

    rebuild_status_file()
    # blah = read_all_suburbs()
    # blah = geojson.read_json_file("results/all-suburbs.json")

    # geojson.write_json_file("results/suburb-dates.json", get_nbn_suburb_dates())

    # update_suburb_dates()
    # compare_suburb_lists()
    # compare_db_suburbs()
