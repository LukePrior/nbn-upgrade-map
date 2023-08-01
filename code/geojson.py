import json
import logging
import os
from datetime import datetime

from data import AddressList
from utils import read_json_file, write_json_file


def format_addresses(addresses: AddressList, suburb: str) -> dict:
    """Convert the list of addresses (with upgrade+tech fields) into a GeoJSON FeatureCollection."""
    features = [
        {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [address.longitude, address.latitude]},
            "properties": {
                "name": address.name,
                "locID": address.loc_id,
                "tech": address.tech,
                "upgrade": address.upgrade,
                "gnaf_pid": address.gnaf_pid,
            },
        }
        for address in addresses
        if address.upgrade and address.tech
    ]

    return {
        "type": "FeatureCollection",
        "generated": datetime.now().isoformat(),
        "suburb": suburb,
        "features": sorted(features, key=lambda x: x["properties"]["gnaf_pid"]),
    }


def get_geojson_filename(suburb: str, state: str) -> str:
    """Get the filename for the GeoJSON file."""
    return f"results/{state.upper()}/{suburb.lower().replace(' ', '-')}.geojson"


def write_geojson_file(suburb: str, state: str, addresses: AddressList):
    """Write the GeoJSON FeatureCollection to a file."""
    filename = get_geojson_filename(suburb, state)
    os.makedirs(os.path.dirname(filename), exist_ok=True)
    logging.info("Writing results to %s", filename)
    write_json_file(filename, format_addresses(addresses, suburb), indent=1)  # indent=1 is to minimise size increase


def read_geojson_file(suburb: str, state: str) -> dict:
    """Read the GeoJSON FeatureCollection from a file, or return None"""
    filename = get_geojson_filename(suburb, state)
    if os.path.exists(filename):
        return read_json_file(filename)


def get_geojson_file_generated_from_name(suburb: str, state: str) -> datetime:
    """Given a suburb and state, get the generated date from the GeoJSON file (faster than reading whole file)."""
    return get_geojson_file_generated(get_geojson_filename(suburb, state))


def get_geojson_file_generated(filename) -> datetime:
    """Get the generated date from the GeoJSON file (faster than reading whole file)."""
    if os.path.exists(filename):
        # attempt to load just the first few lines of the file
        try:
            with open(filename, "r", encoding="utf-8") as file:
                first_bit = file.readline() + file.readline() + file.readline().replace(",", "") + "}"
                result = json.loads(first_bit)
        except json.JSONDecodeError:
            # sometimes generated is not at the top of the file, fall back to loading the entire thing
            result = read_json_file(filename)
        return datetime.fromisoformat(result["generated"])
