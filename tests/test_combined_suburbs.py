import main
import pytest
import suburbs
import testutils
from testutils import reset_captures

def _dummy_read_json_file_combined_suburbs(filename: str) -> dict:
    """Fake combined-suburbs.json file."""
    assert filename == "results/combined-suburbs.json"
    return testutils.read_test_data_json("combined-suburbs.json")


def test_select_suburb(monkeypatch):
    """Test main.select_suburb()."""
    monkeypatch.setattr("utils.read_json_file", _dummy_read_json_file_combined_suburbs)

    # test explicit suburb
    selector = main.select_suburb("Acton", "ACT")
    assert next(selector)[0] == "ACTON"  # unprocessed 1

    # test select order
    selector = main.select_suburb(None, None)
    assert next(selector)[0] == "ACTON"  # unprocessed 1
    assert next(selector)[0] == "AMAROO"  # unprocessed 2
    assert next(selector)[0] == "ARANDA"  # old announced
    assert next(selector)[0] == "AINSLIE"  # old unannounced
    with pytest.raises(StopIteration):
        next(selector)

def test_write_suburbs(monkeypatch, reset_captures):
    monkeypatch.setattr("utils.read_json_file", _dummy_read_json_file_combined_suburbs)
    monkeypatch.setattr("suburbs.utils.write_json_file", testutils.dummy_write_json_file)

    all_suburbs = suburbs.read_all_suburbs()
    suburbs.write_all_suburbs(all_suburbs)
    assert len(testutils.WRITTEN_JSON) == 1, "Should only be one file"
    states = testutils.WRITTEN_JSON["results/combined-suburbs.json"]
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

def test_update_progress(monkeypatch, reset_captures):
    monkeypatch.setattr("utils.read_json_file", _dummy_read_json_file_combined_suburbs)
    monkeypatch.setattr("suburbs.utils.write_json_file", testutils.dummy_write_json_file)

    results = suburbs.update_progress()

    assert len(testutils.WRITTEN_JSON) == 1, "Should only be one file"
    progress = testutils.WRITTEN_JSON["results/progress.json"]
    assert progress['suburbs']['all']['TOTAL']['done'] == 2
    assert progress['suburbs']['all']['TOTAL']['total'] == 4
    assert progress['suburbs']['all']['TOTAL']['percent'] == 50.0
    assert progress['suburbs']['listed']['TOTAL']['done'] == 1
    assert progress['suburbs']['listed']['TOTAL']['total'] == 2
    assert progress['suburbs']['listed']['TOTAL']['percent'] == 50.0

    assert progress['addresses']['all']['TOTAL']['done'] == 3670
    assert progress['addresses']['all']['TOTAL']['total'] == 6354
    assert progress['addresses']['all']['TOTAL']['percent'] == 57.8
    assert progress['addresses']['listed']['TOTAL']['done'] == 1074
    assert progress['addresses']['listed']['TOTAL']['total'] == 3446
    assert progress['addresses']['listed']['TOTAL']['percent'] == 31.2

# TODO: test_update_processed_dates() - need to patch glob.glob, get-generated, and read_all_suburbs + write_all_suburbs