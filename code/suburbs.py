# api for managing the list of suburbs, which ones have been completed, dates announced, etc.

import json
from typing import Dict, List

import data


def get_all_suburbs():
    """Return a list of all suburbs by state. dict[string]->list[string]"""
    with open("results/all_suburbs.json", "r", encoding="utf-8") as file:
        return json.load(file)["states"]


def get_listed_suburbs():
    """Return a list of all suburbs by state that have been listed for upgrade."""
    with open("results/suburbs.json", "r", encoding="utf-8") as file:
        return json.load(file)["states"]


def get_completed_suburbs() -> list:
    """Return a flat of all suburbs by state that have been completed."""
    with open("results/results.json", "r", encoding="utf-8") as file:
        return json.load(file)["suburbs"]


def get_completed_suburbs_by_state() -> dict:
    """Return a dict->set(internal-name) of all suburbs by state that have been completed."""
    completed_suburbs = {state: set() for state in data.STATES}
    for suburb in get_completed_suburbs():
        completed_suburbs[suburb["state"]].add(suburb["internal"])
    return completed_suburbs


def write_results_json(suburbs: List[Dict]):
    """Write the list of completed suburbs to a JSON file."""
    suburb_record = {"suburbs": sorted(suburbs, key=lambda k: (k["state"], k["name"]))}
    with open("results/results.json", "w") as outfile:
        json.dump(suburb_record, outfile, indent=4)
