import difflib
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

    def get_nbn_data_json(self, url) -> dict:
        """Gets a JSON response from a URL."""
        r = self.session.get(url, stream=True, headers=self.HEADERS)
        r.raise_for_status()
        return r.json()

    def get_nbn_loc_id(self, key: str, address: str) -> str:
        """Return the NBN locID for the provided address, or None if there was an error."""
        if key in CACHE:
            return CACHE[key]
        result = self.get_nbn_data_json(self.LOOKUP_URL + urllib.parse.quote(address))
        suggestions = result.get("suggestions", [])
        suggestions = [s for s in suggestions if "id" in s and s["id"].startswith("LOC")]
        suggestions = sorted(
            suggestions,
            key=lambda s: difflib.SequenceMatcher(None, address, s["formattedAddress"]).ratio(),
            reverse=True,
        )
        if suggestions:
            loc_id = suggestions[0]["id"]
            CACHE[key] = loc_id  # cache indefinitely
            return loc_id
        else:
            # In future use the NBN Nearby API with lat/long to get suggestions.
            logging.warning("No valid suggestions for %s", address)

    def get_nbn_loc_details(self, place_id: str) -> dict:
        """Return the NBN details for the provided id, or None if there was an error."""
        if place_id in CACHE:
            return CACHE[place_id]
        if not place_id.startswith("LOC"):
            raise ValueError(f"Invalid place_id: {place_id}")
        details = self.get_nbn_data_json(self.DETAIL_URL + place_id)
        CACHE.set(place_id, details, expire=60 * 60 * 24 * 7)  # cache for 7 days
        return details
