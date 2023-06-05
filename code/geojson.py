import json
import logging
import os
from datetime import datetime

from data import AddressList


def format_addresses(addresses: AddressList, suburb: str) -> dict:
    """Convert the list of addresses (with upgrade+tech fields) into a GeoJSON FeatureCollection."""
    formatted_addresses = {
        "type": "FeatureCollection",
        "generated": datetime.now().isoformat(),
        "suburb": suburb,
        "features": [],
    }
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
            formatted_addresses["features"].append(formatted_address)

    return formatted_addresses


def write_geojson_file(suburb: str, state: str, addresses: AddressList):
    """Write the GeoJSON FeatureCollection to a file."""
    formatted_addresses = format_addresses(addresses, suburb)
    if formatted_addresses["features"]:
        if not os.path.exists(f"results/{state}"):
            os.makedirs(f"results/{state}")
        target_suburb_file = suburb.lower().replace(" ", "-")
        with open(f"results/{state}/{target_suburb_file}.geojson", "w", encoding="utf-8") as outfile:
            logging.info("Writing results to %s", outfile.name)
            json.dump(formatted_addresses, outfile, indent=1)  # indent=1 is to minimise size increase
    else:
        logging.warning("No addresses found for %s, %s", suburb.title(), state)
