import datetime
import os

import geojson
import utils
from data import Address


def test_read_geojson(monkeypatch):
    dir_path = os.path.dirname(os.path.realpath(__file__))
    monkeypatch.setattr("geojson.os.path.exists", lambda path: True)
    monkeypatch.setattr(
        "geojson.read_json_file", lambda filename: utils.read_json_file(f"{dir_path}/data/sample2.geojson")
    )

    stuff = geojson.read_geojson_file("MyTown", "ABC")
    assert stuff is not None
    assert stuff["type"] == "FeatureCollection"
    assert stuff["suburb"] == "ACTON"


def test_write_geojson(monkeypatch):
    SAVED_JSON = {}

    def dummy_write_json_file(filename: str, data: dict, indent=4):
        SAVED_JSON[filename] = data

    monkeypatch.setattr("geojson.write_json_file", dummy_write_json_file)
    monkeypatch.setattr("geojson.os.makedirs", lambda name, mode=0o777, exist_ok=False: None)
    addresses = [
        Address(name="1 Fake St", gnaf_pid="GNAF123", longitude=123.456, latitude=-12.345, upgrade="XYZ", tech="FTTP"),
        Address(name="2 Fake St", gnaf_pid="GNAF456", longitude=123.456, latitude=-12.345, upgrade="ABC", tech="FTTN"),
        Address(name="3 Fake St", gnaf_pid="GNAF789", longitude=123.456, latitude=-12.345, upgrade="ABC"),
        Address(name="4 Fake St", gnaf_pid="GNAF007", longitude=123.456, latitude=-12.345, tech="ABC"),
    ]
    geojson.write_geojson_file("MyTown", "ABC", addresses)

    info = SAVED_JSON["results/ABC/mytown.geojson"]
    assert info["type"] == "FeatureCollection"
    assert info["suburb"] == "MyTown"
    assert len(info["features"]) == 2, "addresses with no tech or upgrade should not be included"
    assert info["features"][0]["type"] == "Feature"
    assert info["features"][0]["properties"]["upgrade"] == "XYZ"
    assert info["features"][0]["properties"]["tech"] == "FTTP"


def test_geojson_generated(monkeypatch):
    dir_path = os.path.dirname(os.path.realpath(__file__))

    # check date at top (partial read)
    generated = geojson.get_geojson_file_generated(f"{dir_path}/data/sample1.geojson")
    assert generated is not None
    assert generated.date() == datetime.date(2023, 7, 7)

    # check date at bottom (full read)
    generated = geojson.get_geojson_file_generated(f"{dir_path}/data/sample2.geojson")
    assert generated is not None
    assert generated.date() == datetime.date(2023, 7, 7)

    # check date at bottom with incomplete top-few JSON (full read)
    generated = geojson.get_geojson_file_generated(f"{dir_path}/data/sample3.geojson")
    assert generated is not None
    assert generated.date() == datetime.date(2023, 7, 7)

    # check generated name path
    dir_path = os.path.dirname(os.path.realpath(__file__))
    monkeypatch.setattr("geojson.get_geojson_filename", lambda suburb, state: f"{dir_path}/data/sample2.geojson")
    generated = geojson.get_geojson_file_generated_from_name("MyTown", "ABC")
    assert generated is not None
