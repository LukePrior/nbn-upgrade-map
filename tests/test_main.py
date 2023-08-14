import copy

import main
import testutils
from data import Address
from nbn import CACHE, NBNApi


def get_nbn_data_json(self, url) -> dict:
    """Return canned NBN API data for testing"""
    if url.startswith("https://places.nbnco.net.au/places/v1/autocomplete?query="):
        query = url.split("=")[-1]
        return testutils.read_test_data_json(f"nbn/query.{query}.json")
    elif url.startswith("https://places.nbnco.net.au/places/v2/details/"):
        loc_id = url.split("/")[-1]
        return testutils.read_test_data_json(f"nbn/details.{loc_id}.json")

    raise NotImplementedError


def test_get_address(monkeypatch):
    monkeypatch.setattr("nbn.NBNApi.get_nbn_data_json", get_nbn_data_json)

    CACHE.clear()

    nbn = NBNApi()
    address = Address(
        name="1 BLUEGUM RISE ANSTEAD 4070",
        gnaf_pid="GAQLD425035994",
        longitude=-27.56300033,
        latitude=152.85904758,
    )
    out_address = main.get_address(nbn, copy.copy(address), get_status=False)
    assert out_address.name == address.name
    assert out_address.loc_id == "LOC000126303452"
    assert out_address.tech is None
    assert out_address.upgrade is None

    out_address = main.get_address(nbn, copy.copy(address), get_status=True)
    assert out_address.loc_id == "LOC000126303452"
    assert out_address.tech == "FTTN"
    assert out_address.upgrade == "FTTP_SA"


def test_remove_duplicate_addresses():
    addresses = [
        Address(name=f"{n} Fake St", gnaf_pid=f"GNAF00{n}", longitude=123.456, latitude=-12.345, loc_id=str(n))
        for n in range(5)
    ]
    addresses.append(copy.copy(addresses[0]))
    new_addresses = main.remove_duplicate_addresses(addresses)
    assert len(addresses) == 6
    assert len(new_addresses) == 5
    assert [a.loc_id for a in new_addresses] == [str(n) for n in range(5)]
