"""Main script for fetching NBN data for a suburb from the NBN API and writing to a GeoJSON file."""

import argparse
import itertools
import logging
import os
import traceback
from collections import Counter
from collections.abc import Generator
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from threading import Lock

import geojson
import requests
from data import Address, AddressList
from db import AddressDB, add_db_arguments, connect_to_db
from geojson import write_geojson_file
from nbn import NBNApi
from suburbs import (
    read_all_suburbs,
    update_processed_dates,
    update_suburb_in_all_suburbs,
)
from utils import print_progress_bar

# a cache of gnaf_pid -> loc_id mappings (from previous results), and a max-age for that cache
GNAF_PID_TO_LOC: dict[str, str] = {}
MAX_LOC_CACHE_AGE_DAYS = 180


def select_suburb(target_suburb: str, target_state: str) -> Generator[tuple[str, str], None, None]:
    """Return a generator(suburb,state) tuple based on the provided input or the next suburb in the list."""

    # 0. If suburb/state are given return that (only)
    all_suburbs = read_all_suburbs()
    if target_suburb is not None and target_state is not None:
        target_suburb = target_suburb.title()
        target_state = target_state.upper()
        for suburb in all_suburbs[target_state]:
            if suburb.name == target_suburb:
                yield suburb.name.upper(), target_state
                return

    # 1. find suburbs that have not been processed
    for state, suburb_list in all_suburbs.items():
        for suburb in suburb_list:
            if suburb.processed_date is None:
                yield suburb.name.upper(), state

    # 2. find announced suburbs that have not been updated in 30 days
    cutoff_date = datetime.now() - timedelta(days=30)
    announced_by_date = {}
    for state, suburb_list in all_suburbs.items():
        for s in suburb_list:
            if s.processed_date is not None and s.announced and s.processed_date < cutoff_date:
                announced_by_date[s.processed_date] = (s.name.upper(), state)
    for processed_date in sorted(announced_by_date):
        yield announced_by_date[processed_date]

    # 3. find suburbs for reprocessing
    # TODO: prefer suburbs with closer announced dates
    by_date = {}
    for state, suburb_list in all_suburbs.items():
        by_date |= {
            s.processed_date: (s.name.upper(), state)
            for s in suburb_list
            if s.processed_date and s.processed_date not in announced_by_date
        }
    for processed_date in sorted(by_date):
        yield by_date[processed_date]


def get_address(nbn: NBNApi, address: Address, get_status=True) -> Address:
    """Return an Address for the given db address, probably augmented with data from the NBN API."""
    global GNAF_PID_TO_LOC
    try:
        if loc_id := GNAF_PID_TO_LOC.get(address.gnaf_pid):
            address.loc_id = loc_id
        else:
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
    state: str,
    suburb: str,
    max_threads: int = 10,
    progress_bar: bool = False,
):
    """Query the DB for addresses, augment them with upgrade+tech details, and write the results to a file."""
    # get addresses from DB
    logging.info("Fetching all addresses for %s, %s", suburb.title(), state)
    db_addresses = db.get_addresses(suburb, state)
    db_addresses.sort(key=lambda k: k.name)
    logging.info("Fetched %d addresses from database", len(db_addresses))

    # if the output file exists already the use it to cache locid lookup
    global GNAF_PID_TO_LOC
    if results := geojson.read_geojson_file(suburb, state):
        file_generated = datetime.fromisoformat(results["generated"])
        if (datetime.now() - file_generated).days < MAX_LOC_CACHE_AGE_DAYS:
            logging.info("Loaded %d addresses from output file", len(results["features"]))
            GNAF_PID_TO_LOC = {
                feature["properties"]["gnaf_pid"]: feature["properties"]["locID"] for feature in results["features"]
            }
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

    update_processed_dates()

    db = connect_to_db(args)

    # if runtime is specified, then run for that duration, otherwise run for just one suburb
    runtime = timedelta(minutes=args.time) if args.time else timedelta()
    start_time = datetime.now()
    for suburb, state in select_suburb(args.suburb, args.state):
        logging.info("Processing %s, %s", suburb.title(), state)
        if runtime.total_seconds() > 0:
            elapsed_seconds = timedelta(seconds=round((datetime.now() - start_time).total_seconds()))
            logging.info("Time elapsed: %s/%s", elapsed_seconds, runtime)
        process_suburb(db, state, suburb, args.threads, progress_bar=args.progress)
        if datetime.now() > (start_time + runtime):
            break


if __name__ == "__main__":
    LOGLEVEL = os.environ.get("LOGLEVEL", "INFO").upper()
    logging.basicConfig(level=LOGLEVEL, format="%(asctime)s %(levelname)s %(threadName)s %(message)s")
    main()
