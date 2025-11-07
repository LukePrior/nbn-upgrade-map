import copy
import datetime

import main
import test_nbn
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


def test_nbn_to_data(monkeypatch):
    monkeypatch.setattr("nbn.requests.Session.get", test_nbn.requests_session_get)

    nbn = NBNApi()

    # test uncached
    CACHE.clear()

    address = Address(
        name="1 BLUEGUM RISE ANSTEAD 4070",
        gnaf_pid="GAQLD425035994",
        longitude=-27.56300033,
        latitude=152.85904758,
    )
    out_address = main.get_address(nbn, copy.copy(address), get_status=True)
    assert out_address.loc_id == "LOC000126303452"
    assert out_address.tech == "FTTN"
    assert out_address.tech_change_status == "Committed"
    assert out_address.program_type == "On-Demand N2P SDU/MDU Simple"
    assert out_address.target_eligibility_quarter == "Jun 2024"


def test_fttp_address_caching(monkeypatch):
    """Test that FTTP addresses from cache are not re-fetched from API"""
    monkeypatch.setattr("nbn.NBNApi.get_nbn_data_json", get_nbn_data_json)

    # Clear caches
    CACHE.clear()
    main.GNAF_PID_TO_FTTP_ADDRESS = {}

    nbn = NBNApi()

    # Create an FTTP address to cache
    fttp_address = Address(
        name="1 TEST STREET TEST SUBURB 4000",
        gnaf_pid="GAQLD999999999",
        longitude=152.85905364,
        latitude=-27.56298776,
        loc_id="LOC000999999999",
        tech="FTTP",
        upgrade="NULL_NA",
    )

    # Cache the FTTP address
    main.GNAF_PID_TO_FTTP_ADDRESS["GAQLD999999999"] = fttp_address

    # Create a new address with same gnaf_pid but without tech info
    test_address = Address(
        name="1 TEST STREET TEST SUBURB 4000",
        gnaf_pid="GAQLD999999999",
        longitude=152.85905364,
        latitude=-27.56298776,
    )

    # Track if API was called
    api_calls = []
    original_get_details = nbn.get_nbn_loc_details

    def track_api_calls(loc_id):
        api_calls.append(loc_id)
        return original_get_details(loc_id)

    monkeypatch.setattr(nbn, "get_nbn_loc_details", track_api_calls)

    # Process the address
    result = main.get_address(nbn, copy.copy(test_address), get_status=True)

    # Verify cached data was used
    assert result.tech == "FTTP"
    assert result.upgrade == "NULL_NA"
    assert result.loc_id == "LOC000999999999"

    # Verify API was NOT called (FTTP addresses should skip API calls)
    assert len(api_calls) == 0, "API should not be called for cached FTTP addresses"


def test_non_fttp_address_still_fetched(monkeypatch):
    """Test that non-FTTP addresses are still fetched from API even if cache exists"""
    monkeypatch.setattr("nbn.NBNApi.get_nbn_data_json", get_nbn_data_json)

    # Clear caches
    CACHE.clear()
    main.GNAF_PID_TO_FTTP_ADDRESS = {}

    nbn = NBNApi()

    # Create an FTTN address (non-FTTP) - should NOT be cached
    address = Address(
        name="1 BLUEGUM RISE ANSTEAD 4070",
        gnaf_pid="GAQLD425035994",
        longitude=-27.56300033,
        latitude=152.85904758,
    )

    # Track if API was called
    api_calls = []
    original_get_details = nbn.get_nbn_loc_details

    def track_api_calls(loc_id):
        api_calls.append(loc_id)
        return original_get_details(loc_id)

    monkeypatch.setattr(nbn, "get_nbn_loc_details", track_api_calls)

    # Process the address
    result = main.get_address(nbn, copy.copy(address), get_status=True)

    # Verify API WAS called (non-FTTP addresses should still fetch from API)
    assert len(api_calls) == 1, "API should be called for non-FTTP addresses"
    assert result.tech == "FTTN"
    assert result.upgrade == "FTTP_SA"
