import os
from datetime import datetime

import main
import pytest
import suburbs
import testutils


def _dummy_read_json_file_combined_suburbs(filename: str) -> dict:
    """Fake combined-suburbs.json file."""
    if filename == "results/combined-suburbs.json":
        return testutils.read_test_data_json("combined-suburbs.json")
    raise NotImplementedError


def test_select_suburb(monkeypatch):
    """Test main.select_suburb()."""
    monkeypatch.setattr("utils.read_json_file", _dummy_read_json_file_combined_suburbs)

    # test explicit suburb
    selector = main.select_suburb("Acton", "ACT")
    assert next(selector)[0] == "ACTON"  # unprocessed 1
    with pytest.raises(StopIteration):
        next(selector)

    # test select order
    selector = main.select_suburb(None, None)
    assert next(selector)[0] == "ACTON"  # unprocessed 1
    assert next(selector)[0] == "AMAROO"  # unprocessed 2
    assert next(selector)[0] == "ARANDA"  # old announced
    assert next(selector)[0] == "AINSLIE"  # old unannounced
    with pytest.raises(StopIteration):
        next(selector)


def test_write_suburbs(monkeypatch):
    """Test suburbs.write_all_suburbs()."""
    SAVED_JSON = {}

    def dummy_write_json_file(filename: str, data: dict, indent=4):
        SAVED_JSON[filename] = data

    monkeypatch.setattr("utils.read_json_file", _dummy_read_json_file_combined_suburbs)
    monkeypatch.setattr("suburbs.utils.write_json_file", dummy_write_json_file)

    all_suburbs = suburbs.read_all_suburbs()
    suburbs.write_all_suburbs(all_suburbs)
    assert len(SAVED_JSON) == 1, "Should only be one file"
    states = SAVED_JSON["results/combined-suburbs.json"]
    assert len(states) == 1, "Should only be one state"
    assert len(states["ACT"]) == 4, "Should be 4 suburbs in ACT"


def test_suburb_data(monkeypatch):
    monkeypatch.setattr("utils.read_json_file", _dummy_read_json_file_combined_suburbs)
    all_suburbs = suburbs.read_all_suburbs()
    assert all_suburbs["ACT"][0].internal == "ACTON"
    assert all_suburbs["ACT"][0].file == "acton"
    assert all_suburbs["ACT"][0] != all_suburbs["ACT"][1]


def test_get_suburb_progress(monkeypatch):
    """Test suburbs.get_suburb_progress()."""
    monkeypatch.setattr("utils.read_json_file", _dummy_read_json_file_combined_suburbs)
    progress = suburbs.get_suburb_progress()
    assert progress["all"]["ACT"] == {"done": 2, "percent": 50.0, "total": 4}
    assert progress["listed"]["ACT"] == {"done": 1, "percent": 50.0, "total": 2}


def test_get_address_progress(monkeypatch):
    """Test suburbs.get_address_progress()."""
    monkeypatch.setattr("utils.read_json_file", _dummy_read_json_file_combined_suburbs)
    progress = suburbs.get_address_progress()
    assert progress["listed"]["TOTAL"] == {"done": 1074, "percent": 31.2, "total": 3446}
    assert progress["all"]["TOTAL"] == {"done": 3670, "percent": 57.8, "total": 6354}


def test_update_progress(monkeypatch):
    SAVED_JSON = {}

    def dummy_write_json_file(filename: str, data: dict, indent=4):
        SAVED_JSON[filename] = data

    monkeypatch.setattr("utils.read_json_file", _dummy_read_json_file_combined_suburbs)
    monkeypatch.setattr("suburbs.utils.write_json_file", dummy_write_json_file)

    results = suburbs.update_progress()
    assert results is not None
    assert results == SAVED_JSON["results/progress.json"]["suburbs"]

    assert len(SAVED_JSON) == 1, "Should only be one file"
    progress = SAVED_JSON["results/progress.json"]
    assert progress["suburbs"]["all"]["TOTAL"]["done"] == 2
    assert progress["suburbs"]["all"]["TOTAL"]["total"] == 4
    assert progress["suburbs"]["all"]["TOTAL"]["percent"] == 50.0
    assert progress["suburbs"]["listed"]["TOTAL"]["done"] == 1
    assert progress["suburbs"]["listed"]["TOTAL"]["total"] == 2
    assert progress["suburbs"]["listed"]["TOTAL"]["percent"] == 50.0

    assert progress["addresses"]["all"]["TOTAL"]["done"] == 3670
    assert progress["addresses"]["all"]["TOTAL"]["total"] == 6354
    assert progress["addresses"]["all"]["TOTAL"]["percent"] == 57.8
    assert progress["addresses"]["listed"]["TOTAL"]["done"] == 1074
    assert progress["addresses"]["listed"]["TOTAL"]["total"] == 3446
    assert progress["addresses"]["listed"]["TOTAL"]["percent"] == 31.2


def test_update_processed_dates(monkeypatch):
    SAVED_JSON = {}

    def _dummy_glob(pathname, *, root_dir=None, dir_fd=None, recursive=False):
        if pathname == "results/ACT/*.geojson":
            dir_path = os.path.dirname(os.path.realpath(__file__))
            return [f"{dir_path}/data/acton.geojson"]  # acton, 2023-07-07T03:54:25.154530
        return []

    def dummy_write_json_file(filename: str, data: dict, indent=4):
        SAVED_JSON[filename] = data

    monkeypatch.setattr("utils.read_json_file", _dummy_read_json_file_combined_suburbs)
    monkeypatch.setattr("suburbs.glob.glob", _dummy_glob)
    monkeypatch.setattr("suburbs.utils.write_json_file", dummy_write_json_file)

    suburbs.update_processed_dates()
    assert len(SAVED_JSON) == 1, "Should only be one file"
    assert SAVED_JSON["results/combined-suburbs.json"]["ACT"][0]["processed_date"] == "2023-07-07T03:54:25.154530"


def test_update_suburb_in_all_suburbs(monkeypatch):
    SAVED_JSON = {}

    def dummy_write_json_file(filename: str, data: dict, indent=4):
        SAVED_JSON[filename] = data

    def dummy_get_geojson_file_generated(filename) -> datetime:
        assert filename == "results/ACT/acton.geojson"
        return datetime(2023, 7, 7, 3, 54, 25, 154530)

    def dummy_get_geojson_file_generated_none(filename) -> datetime:
        assert filename == "results/ACT/acton.geojson"
        return None  # simulate no file

    monkeypatch.setattr("utils.read_json_file", _dummy_read_json_file_combined_suburbs)
    monkeypatch.setattr("suburbs.utils.write_json_file", dummy_write_json_file)
    monkeypatch.setattr("geojson.get_geojson_file_generated", dummy_get_geojson_file_generated)

    suburbs.update_suburb_in_all_suburbs("ACTON", "ACT")
    assert len(SAVED_JSON) == 2, "progress and combined-suburbs should be written"
    acton_suburb = SAVED_JSON["results/combined-suburbs.json"]["ACT"][0]
    assert acton_suburb["name"] == "Acton"
    assert acton_suburb["processed_date"] == "2023-07-07T03:54:25.154530"

    monkeypatch.setattr("geojson.get_geojson_file_generated", dummy_get_geojson_file_generated_none)
    suburbs.update_suburb_in_all_suburbs("ACTON", "ACT")
    assert len(SAVED_JSON) == 2, "progress and combined-suburbs should be written"
    acton_suburb = SAVED_JSON["results/combined-suburbs.json"]["ACT"][0]
    assert acton_suburb["name"] == "Acton"
    assert datetime.fromisoformat(acton_suburb["processed_date"]).date() == datetime.now().date()


def test_get_technology_breakdown(monkeypatch):
    def _dummy_read_json_file(filename: str) -> dict:
        if filename == "results/combined-suburbs.json":
            return testutils.read_test_data_json("combined-suburbs.json")  # four ACT suburbs
        elif filename.startswith("results/ACT/"):
            return testutils.read_test_data_json("sample2.geojson")  # two FTTP, one FTTN
        raise NotImplementedError

    monkeypatch.setattr("utils.read_json_file", _dummy_read_json_file)
    monkeypatch.setattr("geojson.read_json_file", _dummy_read_json_file)
    monkeypatch.setattr("geojson.os.path.exists", lambda x: True)

    breakdown = suburbs.get_technology_breakdown()
    assert breakdown["ACT"]["FTTP"] == 8
    assert breakdown["ACT"]["FTTN"] == 4
    assert breakdown["ACT"]["total"] == 12
    assert breakdown["TOTAL"]["total"] == 12
