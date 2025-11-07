import testutils
from nbn import CACHE, NBNApi


class JSONWrapper:
    def __init__(self, data):
        self.data = data

    def json(self):
        return self.data

    def raise_for_status(self):
        pass


def requests_session_get(self, url, **kwargs):
    """Return canned NBN API data for testing"""
    if url.startswith("https://places.nbnco.net.au/places/v1/autocomplete?query="):
        query = url.split("=")[-1]
        return JSONWrapper(testutils.read_test_data_json(f"nbn/query.{query}.json"))
    elif url.startswith("https://places.nbnco.net.au/places/v2/details/"):
        loc_id = url.split("/")[-1]
        return JSONWrapper(testutils.read_test_data_json(f"nbn/details.{loc_id}.json"))
    raise NotImplementedError


def test_get_address(monkeypatch):
    monkeypatch.setattr("nbn.requests.Session.get", requests_session_get)

    nbn = NBNApi()

    # test uncached
    CACHE.clear()
    details = nbn.get_nbn_loc_details("LOC000126303452")
    assert details["servingArea"]["techType"] == "FTTN"
    assert details["servingArea"]["description"] == "Moggill"
    assert details["addressDetail"]["formattedAddress"] == "LOT 56 1 BLUEGUM RISE ANSTEAD QLD 4070 Australia"
    assert details["addressDetail"]["techChangeStatus"] == "Committed"
    assert details["addressDetail"]["programType"] == "On-Demand N2P SDU/MDU Simple"
    assert details["addressDetail"]["targetEligibilityQuarter"] == "Jun 2024"
    # test cached
    details = nbn.get_nbn_loc_details("LOC000126303452")
    assert details["servingArea"]["techType"] == "FTTN"
    # fetch, and cache-hit
    loc_id = nbn.get_nbn_loc_id("X1", "1 BLUEGUM RISE ANSTEAD 4070")
    assert loc_id == "LOC000126303452"
    loc_id = nbn.get_nbn_loc_id("X1", "XXX")  # cached
    assert loc_id == "LOC000126303452"
    # not found
    loc_id = nbn.get_nbn_loc_id("X2", "1 XYZ ROAD ABCABC 4070")
    assert loc_id is None

    nbn.close()


def test_mixed_google_and_loc_ids(monkeypatch):
    """Test that the API correctly filters Google Place IDs and returns LOC IDs."""
    monkeypatch.setattr("nbn.requests.Session.get", requests_session_get)

    nbn = NBNApi()
    CACHE.clear()

    # Test mixed results where Google Place ID comes first
    # Should return the LOC ID, not the Google Place ID
    loc_id = nbn.get_nbn_loc_id("X3", "TEST MIXED RESULTS")
    assert loc_id == "LOC000999999999", f"Expected LOC ID but got: {loc_id}"

    nbn.close()
