import geojson
from data import Address


WRITTEN_JSON = {}


def _dummy_write_json_file(filename: str, data: dict, indent=4):
    global WRITTEN_JSON
    WRITTEN_JSON[filename] = data


def test_write_geojson(monkeypatch):
    monkeypatch.setattr("geojson.write_json_file", _dummy_write_json_file)
    monkeypatch.setattr("geojson.os.makedirs", lambda name, mode=0o777, exist_ok=False: None)
    addresses = [
        Address(name="1 Fake St", gnaf_pid="GNAF123", longitude=123.456, latitude=-12.345, upgrade="XYZ", tech="FTTP"),
        Address(name="2 Fake St", gnaf_pid="GNAF456", longitude=123.456, latitude=-12.345, upgrade="ABC", tech="FTTN"),
        Address(name="3 Fake St", gnaf_pid="GNAF789", longitude=123.456, latitude=-12.345, upgrade="ABC"),
        Address(name="4 Fake St", gnaf_pid="GNAF007", longitude=123.456, latitude=-12.345, tech="ABC"),
    ]
    geojson.write_geojson_file("MyTown", "ABC", addresses)

    info = WRITTEN_JSON["results/ABC/mytown.geojson"]
    assert info["type"] == "FeatureCollection"
    assert info["suburb"] == "MyTown"
    assert len(info["features"]) == 2, "addresses with no tech or upgrade should not be included"
    assert info["features"][0]["type"] == "Feature"
    assert info["features"][0]["properties"]["upgrade"] == "XYZ"
    assert info["features"][0]["properties"]["tech"] == "FTTP"
