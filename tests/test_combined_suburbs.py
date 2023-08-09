import main
import pytest
import suburbs


def _dummy_read_json_file_combined_suburbs(filename: str) -> dict:
    """Fake combined-suburbs.json file."""
    assert filename == "results/combined-suburbs.json"
    return {
        "ACT": [
            {
                "address_count": 2596,
                "announced": False,
                "announced_date": "November 2024",
                "name": "Ainslie",
                "processed_date": "2022-08-02T17:44:18.007411",
            },
            {
                "address_count": 312,
                "announced": False,
                "announced_date": None,
                "name": "Acton",
                "processed_date": None,
            },
            {
                "address_count": 2372,
                "announced": True,
                "announced_date": None,
                "name": "Amaroo",
                "processed_date": None,
            },
            {
                "address_count": 1074,
                "announced": False,
                "announced_date": None,
                "name": "Aranda",
                "processed_date": "2021-07-07T04:13:03.074294",
            },
        ]
    }


def test_select_unprocessed(monkeypatch):
    """Test main.select_suburb()."""
    monkeypatch.setattr("utils.read_json_file", _dummy_read_json_file_combined_suburbs)

    selector = main.select_suburb(None, None)
    assert next(selector)[0] == "ACTON"  # unprocessed 1
    assert next(selector)[0] == "AMAROO"  # unprocessed 2
    assert next(selector)[0] == "ARANDA"  # old announced
    assert next(selector)[0] == "AINSLIE"  # old unannounced
    with pytest.raises(StopIteration):
        next(selector)


def test_get_suburb_progress(monkeypatch):
    """Test suburbs.get_suburb_progress()."""
    monkeypatch.setattr("utils.read_json_file", _dummy_read_json_file_combined_suburbs)
    progress = suburbs.get_suburb_progress()
    assert progress["all"]["ACT"] == {"done": 2, "percent": 50.0, "total": 4}
    assert progress["listed"]["ACT"] == {"done": 0, "percent": 0.0, "total": 1}


def test_get_address_progress(monkeypatch):
    """Test suburbs.get_address_progress()."""
    monkeypatch.setattr("utils.read_json_file", _dummy_read_json_file_combined_suburbs)
    progress = suburbs.get_address_progress()
    assert progress["listed"]["TOTAL"] == {"done": 0, "percent": 0.0, "total": 2372}
    assert progress["all"]["TOTAL"] == {"done": 3670, "percent": 57.8, "total": 6354}
