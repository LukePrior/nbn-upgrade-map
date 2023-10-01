import testutils
from nbn import CACHE, NBNApi


class JSONWrapper:
    def __init__(self, data):
        self.data = data

    def json(self):
        return self.data


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
    # test cached
    details = nbn.get_nbn_loc_details("LOC000126303452")
    assert details["servingArea"]["techType"] == "FTTN"
    # fetch, and cache-hit
    loc_id = nbn.extended_get_nbn_loc_id("X1", "1 BLUEGUM RISE ANSTEAD 4070")
    assert loc_id == "LOC000126303452"
    loc_id = nbn.extended_get_nbn_loc_id("X1", "XXX")  # cached
    assert loc_id == "LOC000126303452"
    # not LOC*
    loc_id = nbn.extended_get_nbn_loc_id("X3", "31A PEMBROKE DRIVE SOMERVILLE 3912")
    assert loc_id == "ChIJPWqDsVzg1WoRPqwxzCROnvc"
    # not found
    loc_id = nbn.extended_get_nbn_loc_id("X2", "1 XYZ ROAD ABCABC 4070")
    assert loc_id is None

    nbn.close()
