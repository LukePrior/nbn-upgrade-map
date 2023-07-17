import json
from dataclasses import dataclass
from datetime import datetime

STATES_MAP = {
    "New South Wales": "NSW",
    "ACT": "ACT",
    "Victoria": "VIC",
    "Queensland": "QLD",
    "South Australia": "SA",
    "Western Australia": "WA",
    "Tasmania": "TAS",
    "Northern Territory": "NT",
    "Other Territories": "OT",
}

STATES = sorted(STATES_MAP.values())


@dataclass(slots=True)
class Address:
    """A single address in a suburb."""

    name: str
    gnaf_pid: str
    longitude: float
    latitude: float
    loc_id: str = None
    tech: str = None
    upgrade: str = None


AddressList = list[Address]


@dataclass(slots=True)
class Suburb:
    """Details about a Suburb."""

    name: str
    processed_date: datetime = None
    announced: bool = False  # should be redundant vs announced_date, but isn't
    announced_date: str = None  # TODO: datetime?
    address_count: int = 0

    @property
    def internal(self):
        """Return the "internal" representation of the suburb name, e.g. "Brisbane City" -> "BRISBANE-CITY"."""
        return self.name.upper().replace(" ", "-")

    @property
    def file(self):
        """Return the "file" representation of the suburb name, e.g. "Brisbane City" -> "brisbane-city"."""
        return self.name.lower().replace(" ", "-")

    def __eq__(self, other):
        return self.name == other.name

    def __lt__(self, other):
        return self.name < other.name


SuburbsByState = dict[str, list[Suburb]]


def write_json_file(filename: str, data: dict, indent=4):
    """Write a dict to a JSON file."""
    with open(filename, "w", encoding="utf-8") as outfile:
        json.dump(data, outfile, indent=indent)


def read_json_file(filename: str) -> dict:
    """Read a dict from a JSON file."""
    with open(filename, "r", encoding="utf-8") as file:
        return json.load(file)
