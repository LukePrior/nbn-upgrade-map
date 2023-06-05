from dataclasses import dataclass
from typing import List

STATES = ["ACT", "NSW", "NT", "QLD", "SA", "TAS", "VIC", "WA"]


@dataclass
class Address:
    name: str
    gnaf_pid: str
    location: tuple
    loc_id: str = None
    tech: str = None
    upgrade: str = None

    @staticmethod
    def from_dict(address_info):
        return Address(
            name=address_info["name"],
            gnaf_pid=address_info["gnaf_pid"],
            location=address_info["location"],
        )


AddressList = List[Address]
