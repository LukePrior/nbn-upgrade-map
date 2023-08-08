import pytest

import utils

def _read_file_string(filename: str) -> str:
    with open(filename) as f:
        return f.read()

def test_write_json_file():
    test_data = {"a": 1, "b": 2, "c": {"d": 3, "e": 4}}
    utils.write_json_file("test.json", test_data)
    read_data = utils.read_json_file("test.json")
    assert test_data == read_data

@pytest.mark.skip(reason="waiting for https://github.com/LukePrior/nbn-upgrade-map/pull/177")
def test_minimised_json():
    test_data = {"a": 1, "b": 2, "c": {"d": 3, "e": 4}}
    utils.write_json_file("test.json", test_data, indent=0)
    s = _read_file_string("test.json")
    assert s == '{"a":1,"b":2,"c":{"d":3,"e":4}}'

