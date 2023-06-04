"""Main script for fetching NBN data for a suburb from the NBN API and writing to a GeoJSON file."""

import argparse
import json
import logging
import os
import traceback
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from threading import Lock

import requests
from db import AddressDB
from nbn import NBNApi


def augment_address_with_nbn_data(nbn: NBNApi, address: dict):
    """Fetch the upgrade+tech details for the provided address from the NBN API and add to the address dict."""
    try:
        loc_id = nbn.extended_get_nbn_loc_id(address["gnaf_pid"], address["name"])
        if loc_id:
            status = nbn.get_nbn_loc_details(loc_id)
            address["locID"] = loc_id
            address["tech"] = status["addressDetail"]["techType"]
            address["upgrade"] = status["addressDetail"].get("altReasonCode", "UNKNOWN")
    except requests.exceptions.RequestException as err:
        logging.warning("Error fetching NBN data for %s: %s", address["name"], err)


def select_suburb(target_suburb: str, target_state: str) -> tuple:
    """Return a (state,suburb) tuple based on the provided input or the next suburb in the list."""
    target_suburb = target_suburb.upper()
    target_state = target_state.upper()
    if target_suburb == "NA":
        # load the list of previously completed suburbs
        with open("results/results.json", "r", encoding="utf-8") as file:
            completed_suburbs = {}  # state -> set-of-suburbs
            for completed in json.load(file)["suburbs"]:
                state, suburb = completed["state"], completed["internal"]
                if state not in completed_suburbs:
                    completed_suburbs[state] = set()
                completed_suburbs[state].add(suburb)
        # load the list of all suburbs
        with open("results/suburbs.json", "r", encoding="utf-8") as file:
            suburb_list = json.load(file)
            for state, suburbs in suburb_list["states"].items():
                for suburb in suburbs:
                    if state not in completed_suburbs or suburb not in completed_suburbs[state]:
                        return suburb, state

    return target_suburb, target_state


def get_all_addresses(db: AddressDB, suburb: str, state: str, max_threads: int = 10) -> list:
    """Fetch all addresses for suburb+state from the DB and then fetch the upgrade+tech details for each address."""
    logging.info("Fetching all addresses for %s, %s", suburb.title(), state)
    addresses = db.get_addresses(suburb, state)
    addresses = sorted(addresses, key=lambda k: k["name"])
    logging.info("Fetched %d addresses from database", len(addresses))

    chunk_size = 200
    chunks_completed = 0
    lock = Lock()

    def process_chunk(chunk):
        nbn = NBNApi()
        for address in chunk:
            try:
                augment_address_with_nbn_data(nbn, address)
            except Exception as e:
                logging.error(traceback.format_exc())  # gobble all exceptions so we can continue processing

        with lock:
            nonlocal chunks_completed
            chunks_completed += 1
            logging.info("Completed %d requests", chunks_completed * chunk_size)

    logging.info("Submitting %d requests to add NBNco data...", len(addresses))
    threads = []
    with ThreadPoolExecutor(max_workers=max_threads) as executor:
        for i in range(0, len(addresses), chunk_size):
            chunk = addresses[i : i + chunk_size]
            future = executor.submit(process_chunk, chunk)
            threads.append(future)
    exceptions = [thread.exception() for thread in threads if thread.exception() is not None]
    logging.info("All threads completed, %d exceptions", len(exceptions))
    # TODO: not the most elegant way to handle this
    for e in exceptions:
        if not isinstance(e, requests.exceptions.RequestException):
            logging.error("Unhandled exception: %s", e)
    tech_tally = Counter([address.get("tech") for address in addresses])
    logging.info("Completed. Tally of tech types: %s", dict(tech_tally))

    loc_tally = Counter()
    for address in addresses:
        loc_id = address.get("locID", None)
        tag = "None" if loc_id is None else "LOC" if loc_id.startswith("LOC") else "Other"
        loc_tally[tag] += 1

    logging.info("Location ID types: %s", dict(loc_tally))

    return addresses


def format_addresses(addresses: list, suburb: str) -> dict:
    """Convert the list of addresses (with upgrade+tech fields) into a GeoJSON FeatureCollection."""
    formatted_addresses = {
        "type": "FeatureCollection",
        "generated": datetime.now().isoformat(),
        "suburb": suburb,
        "features": [],
    }
    for address in addresses:
        if "upgrade" in address and "tech" in address:
            formatted_address = {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": address["location"]},
                "properties": {
                    "name": address["name"],
                    "locID": address["locID"],
                    "tech": address["tech"],
                    "upgrade": address["upgrade"],
                },
            }
            formatted_addresses["features"].append(formatted_address)

    return formatted_addresses


def write_geojson_file(suburb: str, state: str, formatted_addresses: dict):
    """Write the GeoJSON FeatureCollection to a file."""
    if formatted_addresses["features"]:
        if not os.path.exists(f"results/{state}"):
            os.makedirs(f"results/{state}")
        target_suburb_file = suburb.lower().replace(" ", "-")
        with open(f"results/{state}/{target_suburb_file}.geojson", "w", encoding="utf-8") as outfile:
            logging.info("Writing results to %s", outfile.name)
            json.dump(formatted_addresses, outfile, indent=1)  # indent=1 is to minimise size increase
    else:
        logging.warning("No addresses found for %s, %s", suburb.title(), state)


def process_suburb(db: AddressDB, target_suburb: str, target_state: str, max_threads: int = 10):
    """Query the DB for addresses, augment them with upgrade+tech details, and write the results to a file."""
    suburb, state = select_suburb(target_suburb, target_state)
    if suburb == "NA":
        logging.error("No more suburbs to process")
    else:
        addresses = get_all_addresses(db, suburb, state, max_threads)
        formatted_addresses = format_addresses(addresses, suburb)
        write_geojson_file(suburb, state, formatted_addresses)


def main():
    """Parse command line arguments and start processing selected suburb."""
    parser = argparse.ArgumentParser(
        description="Create GeoJSON files containing FTTP upgrade details for the prescribed suburb."
    )
    parser.add_argument(
        "target_suburb",
        help='The name of a suburb, for example "bli-bli", or "NA" to process the next suburb',
        default="NA",
    )
    parser.add_argument("target_state", help='The name of a state, for example "QLD"', default="NA")
    parser.add_argument("-u", "--dbuser", help="The name of the database user", default="postgres")
    parser.add_argument(
        "-p",
        "--dbpassword",
        help="The password for the database user",
        default="password",
    )
    parser.add_argument("-H", "--dbhost", help="The hostname for the database", default="localhost")
    parser.add_argument("-P", "--dbport", help="The port number for the database", default="5433")
    parser.add_argument(
        "-i",
        "--create_index",
        help="Whether to disable adding an index to the DB to help speed up queries (only used for GitHub Actions)",
        action="store_false",
    )
    parser.add_argument(
        "-n",
        "--threads",
        help="The number of threads to use",
        default=10,
        type=int,
        choices=range(1, 41),
    )
    args = parser.parse_args()

    db = AddressDB(
        "postgres",
        args.dbhost,
        args.dbport,
        args.dbuser,
        args.dbpassword,
        args.create_index,
    )
    # process_suburb(db, args.target_suburb, args.target_state, args.threads)
    with open("results/suburbs.json", "r", encoding="utf-8") as file:
        suburb_list = json.load(file)
        state = "VIC"
        for suburb in suburb_list["states"][state]:
            process_suburb(db, suburb, state, args.threads)


if __name__ == "__main__":
    LOGLEVEL = os.environ.get("LOGLEVEL", "INFO").upper()
    logging.basicConfig(level=LOGLEVEL, format="%(asctime)s %(levelname)s %(message)s")
    main()
