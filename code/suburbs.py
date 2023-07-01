# api for managing the list of suburbs, which ones have been completed, dates announced, etc.

import json


def get_all_suburbs():
    """Return a list of all suburbs by state."""
    with open("results/all_suburbs.json", "r", encoding="utf-8") as file:
        return json.load(file)["states"]


def get_listed_suburbs():
    """Return a list of all suburbs by state that have been listed for upgrade."""
    with open("results/suburbs.json", "r", encoding="utf-8") as file:
        return json.load(file)["states"]
