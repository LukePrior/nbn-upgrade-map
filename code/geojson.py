import json
import logging
import os
from datetime import datetime

from data import AddressList


def write_json_file(filename, data, indent=4):
    with open(filename, "w", encoding="utf-8") as outfile:
        json.dump(data, outfile, indent=indent)


def read_json_file(filename):
    with open(filename, "r", encoding="utf-8") as file:
        return json.load(file)


def format_addresses(addresses: AddressList, suburb: str) -> dict:
    """Convert the list of addresses (with upgrade+tech fields) into a GeoJSON FeatureCollection."""
    features = []
    for address in addresses:
        if address.upgrade and address.tech:
            formatted_address = {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": address.location},
                "properties": {
                    "name": address.name,
                    "locID": address.loc_id,
                    "tech": address.tech,
                    "upgrade": address.upgrade,
                    "gnaf_pid": address.gnaf_pid,
                },
            }
            features.append(formatted_address)

    return {
        "type": "FeatureCollection",
        "generated": datetime.now().isoformat(),
        "suburb": suburb,
        "features": sorted(features, key=lambda x: x["properties"]["gnaf_pid"]),
    }


def get_geojson_filename(suburb: str, state: str) -> str:
    return f"results/{state}/{suburb.lower().replace(' ', '-')}.geojson"


def write_geojson_file(suburb: str, state: str, addresses: AddressList):
    """Write the GeoJSON FeatureCollection to a file."""
    formatted_addresses = format_addresses(addresses, suburb)
    if formatted_addresses["features"]:
        filename = get_geojson_filename(suburb, state)
        os.makedirs(os.path.dirname(filename), exist_ok=True)
        logging.info("Writing results to %s", filename)
        write_json_file(filename, formatted_addresses, indent=1)  # indent=1 is to minimise size increase
    else:
        logging.warning("No addresses found for %s, %s", suburb.title(), state)


def get_geojson_file_generated(suburb: str, state: str) -> datetime:
    """Get the generated date from the GeoJSON file (faster than reading whole file)."""
    filename = get_geojson_filename(suburb, state)
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
