import adhoc_tools
import data


def test_get_nbn_suburb_dates():
    """integration test"""
    suburb_dates = adhoc_tools.get_nbn_suburb_dates()
    assert len(suburb_dates) == len(data.STATES) - 1  # no "Other Territories"
    for state, suburb_list in suburb_dates.items():
        assert "A-C" not in suburb_list
        assert len(suburb_list) > 10

def test_check_processing_rate():
    data = adhoc_tools.check_processing_rate()
    assert len(data) > 10
    assert data[-1][0] == "TOTAL"
