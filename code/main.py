"""Main script for fetching NBN data for a suburb from the NBN API and writing to a GeoJSON file."""

import argparse
import itertools
import logging
import os
import time
import traceback
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from threading import Lock

import requests
from data import Address, AddressList
from db import AddressDB, add_db_arguments, connect_to_db
from geojson import write_geojson_file
from nbn import NBNApi
from suburbs import read_all_suburbs, update_suburb_in_all_suburbs


def select_suburb(target_suburb: str, target_state: str) -> tuple[str, str]:
    """Return a (state,suburb) tuple based on the provided input or the next suburb in the list."""
    suburbs = [
        (state, sorted(suburb_list, key=lambda s: s.announced, reverse=True))
        for state, suburb_list in read_all_suburbs().items()
    ]

    if target_suburb is None or target_state is None:
        for state, suburb_list in suburbs:
            for suburb in suburb_list:
                if suburb.processed_date is None:
                    return suburb.name.upper(), state
    else:
        target_suburb = target_suburb.title()
        target_state = target_state.upper()
        for state, suburb_list in suburbs:
            if state == target_state:
                for suburb in suburb_list:
                    if suburb.name == target_suburb:
                        return suburb.name.upper(), state
        # TODO: maybe fuzzy search?
        logging.error("Suburb %s, %s not found in suburbs list", target_suburb, target_state)

    return None, None


def get_address(nbn: NBNApi, address: Address, get_status=True) -> Address:
    """Return an Address for the given db address, probably augmented with data from the NBN API."""
    try:
        address.loc_id = nbn.extended_get_nbn_loc_id(address.gnaf_pid, address.name)
        if address.loc_id and get_status:
            status = nbn.get_nbn_loc_details(address.loc_id)
            address.tech = status["addressDetail"]["techType"]
            address.upgrade = status["addressDetail"].get("altReasonCode", "UNKNOWN")
    except requests.exceptions.RequestException as err:
        logging.warning("Error fetching NBN data for %s: %s", address.name, err)
    except Exception:
        # gobble all exceptions so we can continue processing!
        logging.warning(traceback.format_exc())

    return address


def print_progress_bar(iteration, total, prefix="", suffix="", decimals=1, length=100, fill="█", printEnd="\r"):
    """
    Call in a loop to create terminal progress bar.
    Borrowed from https://stackoverflow.com/questions/3173320/text-progress-bar-in-terminal-with-block-characters
    @params:
        iteration   - Required  : current iteration (Int)
        total       - Required  : total iterations (Int)
        prefix      - Optional  : prefix string (Str)
        suffix      - Optional  : suffix string (Str)
        decimals    - Optional  : positive number of decimals in percent complete (Int)
        length      - Optional  : character length of bar (Int)
        fill        - Optional  : bar fill character (Str)
        printEnd    - Optional  : end character (e.g. "\r", "\r\n") (Str)
    """
    percent = ("{0:." + str(decimals) + "f}").format(100 * (iteration / float(total)))
    filled_length = int(length * iteration // total)
    bar = fill * filled_length + "-" * (length - filled_length)
    print(f"\r{prefix} |{bar}| {percent}% {suffix}", end=printEnd)
    # Print New Line on Complete
    if iteration == total:
        print()


def get_all_addresses(
    db_addresses: AddressList, max_threads: int = 10, get_status: bool = True, progress_bar: bool = False
) -> AddressList:
    """Fetch all addresses for suburb+state from the DB and then fetch the upgrade+tech details for each address."""
    # return list of Address
    chunk_size = 200
    sub_chunk_size = chunk_size // 10
    addresses_completed = 0
    lock = Lock()

    def process_chunk(addresses_chunk: AddressList):
        """Process a chunk of DB addresses, augmenting them with NBN data."""
        nbn = NBNApi()

        results = []
        sub_chunks = (addresses_chunk[i : i + sub_chunk_size] for i in range(0, len(addresses_chunk), sub_chunk_size))
        for sub_chunk in sub_chunks:
            results.extend(get_address(nbn, address, get_status) for address in sub_chunk)
            with lock:
                nonlocal addresses_completed
                addresses_completed += len(sub_chunk)
                if progress_bar:
                    print_progress_bar(
                        addresses_completed, len(db_addresses), prefix="Progress:", suffix="Complete", length=50
                    )

        if not progress_bar:
            logging.info("Completed %d requests", addresses_completed)

        return results

    logging.info("Submitting %d requests to add NBNco data...", len(db_addresses))
    with ThreadPoolExecutor(max_workers=max_threads, thread_name_prefix="nbn") as executor:
        chunks = (db_addresses[i : i + chunk_size] for i in range(0, len(db_addresses), chunk_size))
        chunk_results = executor.map(process_chunk, chunks)

    addresses = list(itertools.chain.from_iterable(chunk_results))
    return addresses


def process_suburb(
    db: AddressDB,
    target_suburb: str | None,
    target_state: str | None,
    max_threads: int = 10,
    progress_bar: bool = False,
):
    """Query the DB for addresses, augment them with upgrade+tech details, and write the results to a file."""
    suburb, state = select_suburb(target_suburb, target_state)
    if suburb is None:
        logging.error("No more suburbs to process")
    else:
        # get addresses from DB
        logging.info("Fetching all addresses for %s, %s", suburb.title(), state)
        db_addresses = db.get_addresses(suburb, state)
        db_addresses.sort(key=lambda k: k.name)
        logging.info("Fetched %d addresses from database", len(db_addresses))

        # get NBN data for addresses
        addresses = get_all_addresses(db_addresses, max_threads, progress_bar=progress_bar)

        # emit some tallies
        tech_tally = Counter(address.tech for address in addresses)
        logging.info("Completed. Tally of tech types: %s", dict(tech_tally))

        types = [
            "None" if address.loc_id is None else "LOC" if address.loc_id.startswith("LOC") else "Other"
            for address in addresses
        ]
        loc_tally = Counter(types)
        logging.info("Location ID types: %s", dict(loc_tally))

        write_geojson_file(suburb, state, addresses)
        update_suburb_in_all_suburbs(suburb, state)


def timer(run_time: int, db: AddressDB, max_threads: int = 10, progress_bar: bool = False):
    """Process suburbs for a given amount of minutes."""
    start = time.time()
    while time.time() - start < run_time * 60:
        logging.info("Time elapsed: %d minutes", (time.time() - start) // 60)
        logging.info("Time remaining: %d minutes", run_time - (time.time() - start) // 60)
        process_suburb(db, None, None, max_threads, progress_bar)
    logging.info("Total time elapsed: %d minutes", (time.time() - start) // 60)


def main():
    """Parse command line arguments and start processing selected suburb."""
    parser = argparse.ArgumentParser(
        description="Create GeoJSON files containing FTTP upgrade details for the prescribed suburb."
    )
    parser.add_argument("--suburb", help='The name of a suburb, for example "Bli Bli"')
    parser.add_argument("--state", help='The name of a state, for example "QLD"')
    parser.add_argument(
        "-n",
        "--threads",
        help="The number of threads to use",
        default=10,
        type=int,
        choices=range(1, 41),
    )
    parser.add_argument("--progress", help="Show a progress bar", action=argparse.BooleanOptionalAction)
    parser.add_argument("-t", "--time", help="When on auto mode for how many minutes to process suburbs", type=int)
    add_db_arguments(parser)
    args = parser.parse_args()

    db = connect_to_db(args)
    if args.time and args.time >= 5:
        timer(args.time, db, args.threads, progress_bar=args.progress)
    else:
        process_suburb(db, args.suburb, args.state, args.threads, progress_bar=args.progress)


if __name__ == "__main__":
    LOGLEVEL = os.environ.get("LOGLEVEL", "INFO").upper()
    logging.basicConfig(level=LOGLEVEL, format="%(asctime)s %(levelname)s %(threadName)s %(message)s")
    main()
