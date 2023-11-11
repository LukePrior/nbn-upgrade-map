import datetime
from argparse import Namespace

import adhoc_tools
import testutils
from test_db import SAMPLE_ADDRESSES_DB_FILE


def test_check_processing_rate(monkeypatch):
    """Check the reporting function"""
    monkeypatch.setattr(
        "utils.read_json_file",
        lambda filename: testutils.read_test_data_json("combined-suburbs.json"),
    )

    data = adhoc_tools.check_processing_rate()
    assert len(data) == 3
    assert data[0] == (datetime.date(2021, 7, 7), 1)
    assert data[1] == (datetime.date(2022, 8, 2), 1)
    assert data[-1] == ("TOTAL", 2)


def test_get_db_suburb_list():
    args = Namespace(dbhost=SAMPLE_ADDRESSES_DB_FILE)
    suburbs = adhoc_tools.get_db_suburb_list(args)
    assert len(suburbs) == 5
    assert len(suburbs["NSW"]) == 2


def test_add_address_count_to_suburbs(monkeypatch):
    monkeypatch.setattr(
        "utils.read_json_file",
        lambda filename: testutils.read_test_data_json("combined-suburbs-somer.json"),
    )
    SAVED_JSON = {}

    def dummy_write_json_file(filename: str, data: dict, indent=4):
        SAVED_JSON[filename] = data

    monkeypatch.setattr("suburbs.utils.write_json_file", dummy_write_json_file)

    # DB has 8 suburbs (like "SOMER") across 5 states
    # all-suburbs has three of these with different (big) address-counts
    args = Namespace(dbhost=SAMPLE_ADDRESSES_DB_FILE)
    adhoc_tools.add_address_count_to_suburbs(args)
    assert len(SAVED_JSON) == 1
    assert "results/combined-suburbs.json" in SAVED_JSON
    nsw_suburbs = {s["name"]: s for s in SAVED_JSON["results/combined-suburbs.json"]["NSW"]}
    assert nsw_suburbs["Somersby"]["address_count"] == 5
    assert nsw_suburbs["Somerton"]["address_count"] == 1
    sa_suburbs = {s["name"]: s for s in SAVED_JSON["results/combined-suburbs.json"]["SA"]}
    assert sa_suburbs["Somerton Park"]["address_count"] == 20


def test_update_suburb_dates(monkeypatch):
    monkeypatch.setattr("adhoc_tools.get_nbn_suburb_dates", lambda: testutils.read_test_data_json("suburb-dates.json"))
    monkeypatch.setattr("utils.read_json_file", lambda filename: testutils.read_test_data_json("combined-suburbs.json"))

    SAVED_JSON = {}

    def dummy_write_json_file(filename: str, data: dict, indent=4):
        SAVED_JSON[filename] = data

    monkeypatch.setattr("suburbs.utils.write_json_file", dummy_write_json_file)
