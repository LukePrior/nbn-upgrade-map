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
    name: str
    gnaf_pid: str
    location: tuple[float, float]
    loc_id: str = None
    tech: str = None
    upgrade: str = None

    # @staticmethod
    # def from_dict(address_info):
    #     return Address(
    #         name=address_info["name"],
    #         gnaf_pid=address_info["gnaf_pid"],
    #         location=address_info["location"],
    #     )


AddressList = list[Address]


# A combination of results.json and suburbs.json/all_suburbs.json plus suburb-dates
#             "internal": "AINSLIE",
#             "state": "ACT",  # removed from file/structure; add manually to dict if required
#             "name": "Ainslie",
#             "file": "ainslie",
#             "date": "05-06-2023"


@dataclass(slots=True)
class Suburb:
    name: str
    processed_date: datetime = None
    announced: bool = False  # should be redundant vs announced_date, but isn't
    announced_date: str = None  # TODO: datetime?

    @property
    def internal(self):
        return self.name.upper().replace(" ", "-")

    @property
    def file(self):
        return self.name.lower().replace(" ", "-")

    def __eq__(self, other):
        return self.name == other.name

    def __lt__(self, other):
        return self.name < other.name


def write_json_file(filename: str, data: dict, indent=4):
    with open(filename, "w", encoding="utf-8") as outfile:
        json.dump(data, outfile, indent=indent)


def read_json_file(filename: str) -> dict:
    with open(filename, "r", encoding="utf-8") as file:
        return json.load(file)
