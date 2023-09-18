import datetime

import adhoc_tools
import data
import testutils


def test_get_nbn_suburb_dates():
    """integration test"""
    suburb_dates = adhoc_tools.get_nbn_suburb_dates()
    assert len(suburb_dates) == len(data.STATES) - 1  # no "Other Territories"
    for state, suburb_list in suburb_dates.items():
        assert "A-C" not in suburb_list
        assert len(suburb_list) > 10


def test_check_processing_rate(monkeypatch):
    """Check the reporting function"""
    monkeypatch.setattr(
        "utils.read_json_file",
        lambda filename: testutils.read_test_data_json("combined-suburbs.json"),
    )

    data = adhoc_tools.check_processing_rate()
    assert len(data) == 3
    assert data[0] == (datetime.date(2021, 7, 7), 1, None)
    assert data[1] == (datetime.date(2022, 8, 2), None, 1)
    assert data[-1] == ("TOTAL", 1, 1)
