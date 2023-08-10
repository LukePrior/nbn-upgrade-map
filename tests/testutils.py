import json
import os

import pytest

WRITTEN_JSON = {}


@pytest.fixture
def reset_captures():
    """Reset the buckets where load/save is stored"""
    global WRITTEN_JSON
    WRITTEN_JSON = {}


def dummy_write_json_file(filename: str, data: dict, indent=4):
    """Dummy function to replace utils.write_json_file() for testing."""
    WRITTEN_JSON[filename] = data


def read_file_string(filename: str) -> str:
    """Read the contents of a file as a string"""
    with open(filename) as f:
        return f.read()


def get_test_data_path(filename: str) -> str:
    """Get the full path to a test data file."""
    return f"{os.path.dirname(os.path.realpath(__file__))}/data/{filename}"


def read_test_data_file(filename: str) -> str:
    """Read the contents of a test data file."""
    with open(get_test_data_path(filename), encoding="utf-8") as file:
        return file.read()


def read_test_data_json(filename: str) -> dict:
    """Read the contents of a test data file as JSON."""
    with open(get_test_data_path(filename), "r", encoding="utf-8") as file:
        return json.load(file)
