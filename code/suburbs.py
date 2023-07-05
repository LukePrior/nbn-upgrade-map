# api for managing the list of suburbs, which ones have been completed, dates announced, etc.

import data
import geojson


def get_all_suburbs() -> dict[str, list[str]]:
    """Return a list of all suburbs by state"""
    return geojson.read_json_file("results/all_suburbs.json")["states"]


def get_listed_suburbs() -> dict[str, list[str]]:
    """Return a list of all suburbs by state that have been listed for upgrade."""
    return geojson.read_json_file("results/suburbs.json")["states"]


def get_completed_suburbs() -> list[dict]:
    """Return a flat of all suburbs by state that have been completed."""
    return geojson.read_json_file("results/results.json")["suburbs"]


def get_completed_suburbs_by_state() -> dict[str, set[str]]:
    """Return a dict->set(internal-name) of all suburbs by state that have been completed."""
    completed_suburbs = {state: set() for state in data.STATES}
    for suburb in get_completed_suburbs():
        completed_suburbs[suburb["state"]].add(suburb["internal"])
    return completed_suburbs


def write_results_json(suburbs: list[dict]):
    """Write the list of completed suburbs to a JSON file."""
    geojson.write_json_file("results/results.json", {"suburbs": sorted(suburbs, key=lambda k: (k["state"], k["name"]))})
