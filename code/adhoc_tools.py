# parse a NBN web page to get a list of all suburb upgrade dates
import argparse
import json
import logging
import os
import re

import requests
from bs4 import BeautifulSoup

import data
import db
import suburbs
# from code.db import add_db_arguments, connect_to_db

# from code import suburbs
from suburbs import get_listed_suburbs


def update_suburb_dates():
    """Parse a NBN web page to get a list of all suburb upgrade dates."""
    URL = "https://www.nbnco.com.au/residential/upgrades/more-fibre"
    content = requests.get(URL).content

    results = {}

    soup = BeautifulSoup(content, "html.parser")
    for state_element in soup.find(id="accordion-c467de9e93").find_all("div", class_="cmp-accordion__item"):
        state = state_element.find("span", class_="cmp-accordion__title").text
        results[state] = {}
        for p in state_element.find("div", class_="cmp-text").find_all("p"):
            for suburb, date in re.findall(r"^(.*) - from (\w+ \d{4})", p.text, flags=re.MULTILINE):
                results[state][suburb] = date
        print(state, len(results[state]), results[state])

    with open("results/suburb-dates.json", "w") as outfile:
        json.dump(results, outfile, indent=4)


def update_suburb_list():
    """Parse a NBN web page to get a list of all suburbs announced for upgrades."""
    URL = "https://www.nbnco.com.au/corporate-information/media-centre/media-statements/nbnco-announces-suburbs-and-towns-where-an-additional-ninty-thousand-homes-and-businesses-will-become-eligible-for-fibre-upgrades"
    content = requests.get(URL).content
    # with open("results/suburb-list.html", "wb") as outfile:
    #     outfile.write(content)
    # with open("results/suburb-list.html", "r") as infile:
    #     content = infile.read()

    results = {}

    soup = BeautifulSoup(content, "html.parser")
    for state_element in soup.find_all("div", class_="cmp-accordion__item"):
        state = state_element.find("span", class_="cmp-accordion__title").text
        results[state] = []
        for p in state_element.find("div", class_="cmp-text").find_all("p"):
            # paragraphs starting with <b> are titles, others are lists of suburbs
            if p.text.startswith("Announced "):
                continue
            suburbs = re.split(r", ?", p.text)
            results[state].extend(suburbs)

    # convert to a state codes and uppercase suburbs
    new_results = {}
    for state, suburbs in results.items():
        state_code = data.STATES_MAP[state]
        new_results[state_code] = [
            re.sub(
                r"( \(ADDITIONAL FOOTPRINT\)|ADDITIONAL AREAS OF | \(4350\))", "", suburb.strip("*#.\xa0\r\n").upper()
            )
            for suburb in suburbs
        ]

    old_results = get_listed_suburbs()

    # compare for differences
    for state_code, suburbs in new_results.items():
        new_set = set(suburbs)
        old_set = set(old_results[state_code])
        if new_set != old_set:
            # state, new count, old count, new, old
            print(state_code, len(new_set), len(old_set), len(new_set - old_set), len(old_set - new_set))
            print("   NEW: ", new_set - old_set)
            print("   OLD: ", old_set - new_set)


def compare_db_suburbs():
    """Compare the suburbs in the DB with the list of all suburbs."""
    parser = argparse.ArgumentParser(description="Emit a summary of progress against the list of suburbs in the DB.")
    db.add_db_arguments(parser)
    args = parser.parse_args()
    xdb = db.connect_to_db(args)
    counts = xdb.get_counts_by_suburb()
    all_suburbs = suburbs.get_all_suburbs()
    # check all the DB suburbs are in the list of all suburbs
    for state, suburb_count in counts.items():
        for suburb, n in suburb_count.items():
            if suburb not in all_suburbs.get(state, set()):
                print(f"Missing {suburb}, {state} ({n} addresses)")


if __name__ == "__main__":
    LOGLEVEL = os.environ.get("LOGLEVEL", "INFO").upper()
    logging.basicConfig(level=LOGLEVEL, format="%(asctime)s %(levelname)s %(threadName)s %(message)s")

    # update_suburb_dates()
    # update_suburb_list()
    compare_db_suburbs()
