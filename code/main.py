"""Main script for fetching NBN data for a suburb from the NBN API and writing to a GeoJSON file."""

import argparse
import itertools
import json
import logging
import os
import traceback
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from threading import Lock

import requests

from db import AddressDB
from geojson import write_geojson_file
from nbn import NBNApi


@dataclass
class Address:
    name: str
    gnaf_pid: str
    location: tuple
    loc_id: str = None
    tech: str = None
    upgrade: str = None

    @staticmethod
    def from_dict(address_info):
        return Address(
            name=address_info["name"],
            gnaf_pid=address_info["gnaf_pid"],
            location=address_info["location"],
        )


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


def get_address(nbn: NBNApi, address_info: dict) -> Address:
    """Return an Address for the given db address, probably augmented with data from the NBN API."""
    address = Address.from_dict(address_info)
    try:
        loc_id = nbn.extended_get_nbn_loc_id(address.gnaf_pid, address.name)
        if loc_id:
            status = nbn.get_nbn_loc_details(loc_id)
            address.loc_id = loc_id
            address.tech = status["addressDetail"]["techType"]
            address.upgrade = status["addressDetail"].get("altReasonCode", "UNKNOWN")
    except requests.exceptions.RequestException as err:
        logging.warning("Error fetching NBN data for %s: %s", address.name, err)
    except Exception:
        # gobble all exceptions so we can continue processing!
        logging.warning(traceback.format_exc())

    return address


def get_all_addresses(db: AddressDB, suburb: str, state: str, max_threads: int = 10) -> list:
    """Fetch all addresses for suburb+state from the DB and then fetch the upgrade+tech details for each address."""
    logging.info("Fetching all addresses for %s, %s", suburb.title(), state)
    db_addresses = db.get_addresses(suburb, state)
    db_addresses.sort(key=lambda k: k["name"])
    logging.info("Fetched %d addresses from database", len(db_addresses))

    chunk_size = 200
    chunks_completed = 0
    lock = Lock()

    def process_chunk(addresses_chunk):
        """Process a chunk of DB addresses, augmenting them with NBN data."""
        nbn = NBNApi()
        addresses = [get_address(nbn, address) for address in addresses_chunk]

        # show progress
        with lock:
            nonlocal chunks_completed
            chunks_completed += 1
            logging.info("Completed %d requests", chunks_completed * chunk_size)

        return addresses

    logging.info("Submitting %d requests to add NBNco data...", len(db_addresses))
    with ThreadPoolExecutor(max_workers=max_threads, thread_name_prefix="nbn") as executor:
        chunks = (db_addresses[i : i + chunk_size] for i in range(0, len(db_addresses), chunk_size))
        chunk_results = executor.map(process_chunk, chunks)

    addresses = list(itertools.chain.from_iterable(chunk_results))

    tech_tally = Counter(address.tech for address in addresses)
    logging.info("Completed. Tally of tech types: %s", dict(tech_tally))

    loc_tally = Counter()
    for address in addresses:
        tag = "None" if address.loc_id is None else "LOC" if address.loc_id.startswith("LOC") else "Other"
        loc_tally[tag] += 1

    logging.info("Location ID types: %s", dict(loc_tally))

    return addresses


def process_suburb(db: AddressDB, target_suburb: str, target_state: str, max_threads: int = 10):
    """Query the DB for addresses, augment them with upgrade+tech details, and write the results to a file."""
    suburb, state = select_suburb(target_suburb, target_state)
    if suburb == "NA":
        logging.error("No more suburbs to process")
    else:
        addresses = get_all_addresses(db, suburb, state, max_threads)
        write_geojson_file(suburb, state, addresses)


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
    process_suburb(db, args.target_suburb, args.target_state, args.threads)


if __name__ == "__main__":
    LOGLEVEL = os.environ.get("LOGLEVEL", "INFO").upper()
    logging.basicConfig(level=LOGLEVEL, format="%(asctime)s %(levelname)s %(threadName)s %(message)s")
    main()
