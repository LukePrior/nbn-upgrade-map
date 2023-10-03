import pytest
import testutils
import utils


def test_read_write_json_file():
    test_data = {"a": 1, "b": 2, "c": {"d": 3, "e": 4}}
    utils.write_json_file("test.json", test_data)
    read_data = utils.read_json_file("test.json")
    assert test_data == read_data
    missing_file = utils.read_json_file("xtest.json", empty_if_missing=True)
    assert missing_file == {}


@pytest.mark.skip(reason="waiting for https://github.com/LukePrior/nbn-upgrade-map/pull/177")
def test_minimised_json():
    test_data = {"a": 1, "b": 2, "c": {"d": 3, "e": 4}}
    utils.write_json_file("test.json", test_data, indent=0)
    s = testutils.read_file_string("test.json")
    assert s == '{"a":1,"b":2,"c":{"d":3,"e":4}}'


def test_progress_bar(capsys):
    utils.print_progress_bar(0, 100, prefix="Progress:", suffix="Complete", length=50)
    utils.print_progress_bar(25, 100, prefix="Progress:", suffix="Complete", length=50)
    utils.print_progress_bar(100, 100, prefix="Progress:", suffix="Complete", length=50)

    captured = capsys.readouterr()
    assert captured.out.count("Progress:") == 3
    assert "0.0%" in captured.out
    assert "100.0%" in captured.out
