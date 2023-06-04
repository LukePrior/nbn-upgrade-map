import logging
import urllib.parse

import diskcache
import requests
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry

# 1GB LRU cache of gnaf_pid->loc_id and loc_id->details
CACHE = diskcache.Cache("cache")


class NBNApi:
    """Interacts with NBN's unofficial API."""

    LOOKUP_URL = "https://places.nbnco.net.au/places/v1/autocomplete?query="
    DETAIL_URL = "https://places.nbnco.net.au/places/v2/details/"
    HEADERS = {"referer": "https://www.nbnco.com.au/"}

    def __init__(self):
        self.session = requests.Session()
        self.session.mount("http://", HTTPAdapter(max_retries=(Retry(total=5))))

    def close(self):
        """Close the cache."""
        # TODO Each thread that accesses a cache should also call close on the cache.
        CACHE.close()

    def get_nbn_data_json(self, url):
        """Gets a JSON response from a URL."""
        return self.session.get(url, stream=True, headers=self.HEADERS).json()

    def get_nbn_loc_id(self, key: str, address: str) -> str:
        """Return the NBN locID for the provided address, or None if there was an error."""
        if key in CACHE:
            return CACHE[key]
        result = self.get_nbn_data_json(self.LOOKUP_URL + urllib.parse.quote(address))
        if "suggestions" not in result:
            logging.warning("No suggestions for %s", address)
        elif len(result["suggestions"]) == 0:
            logging.warning("Zero suggestions for %s", address)
        elif "id" not in result["suggestions"][0]:
            logging.warning("No id for %s", address)
        else:
            loc_id = result["suggestions"][0]["id"]
            CACHE[key] = loc_id  # cache indefinitely
            return loc_id

    def extended_get_nbn_loc_id(self, key: str, address: str) -> str:
        """Return the NBN locID for the provided address, following the addressSplitDetails if required."""
        loc_id = self.get_nbn_loc_id(key, address)
        if loc_id and not loc_id.startswith("LOC"):
            details = self.get_nbn_loc_details(loc_id)
            # sometimes addressSplitDetails.address1 is None
            if details and None not in details["addressSplitDetails"].values():
                new_address = " ".join(details["addressSplitDetails"].values())
                if new_address.lower() != address.lower():
                    loc_id = self.get_nbn_loc_id("X" + key, new_address)
        return loc_id

    def get_nbn_loc_details(self, id: str) -> dict:
        """Return the NBN details for the provided id, or None if there was an error."""
        if id in CACHE:
            return CACHE[id]
        details = self.get_nbn_data_json(self.DETAIL_URL + id)
        CACHE.set(id, details, expire=60 * 60 * 24 * 7)  # cache for 7 days
        return details
