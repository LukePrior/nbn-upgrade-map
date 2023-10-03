import copy
import datetime

import main
import testutils
import update_breakdown
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


def test_update_breakdown(monkeypatch):
    SAVED_JSON = {}

    def _dummy_read_json_file(filename: str, empty_if_missing=False) -> dict:
        if filename == "results/breakdown.json" and empty_if_missing:
            return {}
        elif filename == "results/breakdown-suburbs.json" and empty_if_missing:
            return {}
        elif filename == "results/combined-suburbs.json":
            return testutils.read_test_data_json("combined-suburbs.json")  # four ACT suburbs
        elif filename.startswith("results/ACT/"):
            return testutils.read_test_data_json("sample2.geojson")  # two FTTP, one FTTN
        raise NotImplementedError(f"Unexpected filename: {filename}")

    def _dummy_write_json_file(filename: str, data: dict, indent=4):
        SAVED_JSON[filename] = data

    def _dummy_glob(pathname, *, root_dir=None, dir_fd=None, recursive=False):
        return ["results/ACT/acton.geojson", "results/ACT/braddon.geojson"]

    monkeypatch.setattr("utils.read_json_file", _dummy_read_json_file)
    monkeypatch.setattr("utils.write_json_file", _dummy_write_json_file)
    monkeypatch.setattr("adhoc_tools.glob.glob", _dummy_glob)

    bd = update_breakdown.update_breakdown()

    date_key = datetime.datetime.now().date().isoformat()
    assert len(bd) == 1
    assert date_key in bd
    assert len(bd[date_key]) == 2
    assert bd[date_key]["tech"]["FTTP"] == 4
    assert bd[date_key]["tech"]["FTTN"] == 2
    assert bd[date_key]["upgrade"]["NULL_NA"] == 2
    update_breakdown.print_breakdowns(bd)
    # TODO: check output?


def test_update_breakdown_rerun(monkeypatch):
    date_key = datetime.datetime.now().date().isoformat()
    dummy_value = "DUMMY_VALUE"

    def _dummy_read_json_file(filename: str, empty_if_missing=False) -> dict:
        if filename == "results/breakdown.json" and empty_if_missing:
            return {date_key: dummy_value}
        elif filename == "results/breakdown-suburbs.json" and empty_if_missing:
            return {date_key: dummy_value}
        raise NotImplementedError(f"Unexpected filename: {filename}")

    monkeypatch.setattr("utils.read_json_file", _dummy_read_json_file)
    bd = update_breakdown.update_breakdown()
    assert len(bd) == 1
    assert bd[date_key] == dummy_value
