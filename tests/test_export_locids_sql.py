import os
import tempfile

import export_locids_sql


def test_iter_feature_data_with_default_fields(monkeypatch):
    """Test iterating features with default fields."""
    mock_geojson = {
        "features": [
            {
                "geometry": {"coordinates": [115.78506081, -31.95270506]},
                "properties": {
                    "name": "100 STEPHENSON AVENUE MOUNT CLAREMONT 6010",
                    "locID": "LOC000190342926",
                    "tech": "FTTN",
                    "upgrade": "FTTP_NA",
                    "gnaf_pid": "GAWA_146611183",
                    "tech_change_status": "In Design",
                    "program_type": "Customer-initiated N2P MDU Complex",
                    "target_eligibility_quarter": "Mar 2028",
                },
            },
            {
                "geometry": {"coordinates": [115.77758570, -31.96588092]},
                "properties": {
                    "name": "27 LISLE STREET MOUNT CLAREMONT 6010",
                    "locID": "LOC000027955790",
                    "tech": "HFC",
                    "upgrade": "NULL_NA",
                    "gnaf_pid": "GAWA_146615762",
                },
            },
        ]
    }

    def mock_get_all_geojson_files(show_progress=True, rewrite_geojson=False):
        yield "test.geojson", mock_geojson

    monkeypatch.setattr("export_locids_sql.get_all_geojson_files", mock_get_all_geojson_files)

    # Test with default fields
    results = list(export_locids_sql.iter_feature_data(show_progress=False))

    assert len(results) == 2
    assert results[0]["loc_id"] == "LOC000190342926"
    assert results[0]["latitude"] == -31.95270506
    assert results[0]["longitude"] == 115.78506081
    assert results[0]["name"] == "100 STEPHENSON AVENUE MOUNT CLAREMONT 6010"
    assert results[0]["tech"] == "FTTN"
    assert results[0]["upgrade"] == "FTTP_NA"
    assert results[0]["gnaf_pid"] == "GAWA_146611183"
    assert results[0]["tech_change_status"] == "In Design"
    assert results[0]["program_type"] == "Customer-initiated N2P MDU Complex"
    assert results[0]["target_eligibility_quarter"] == "Mar 2028"


def test_iter_feature_data_with_specific_fields(monkeypatch):
    """Test iterating features with specific fields."""
    mock_geojson = {
        "features": [
            {
                "geometry": {"coordinates": [115.78506081, -31.95270506]},
                "properties": {
                    "name": "100 STEPHENSON AVENUE MOUNT CLAREMONT 6010",
                    "locID": "LOC000190342926",
                    "tech": "FTTN",
                    "upgrade": "FTTP_NA",
                    "gnaf_pid": "GAWA_146611183",
                },
            },
        ]
    }

    def mock_get_all_geojson_files(show_progress=True, rewrite_geojson=False):
        yield "test.geojson", mock_geojson

    monkeypatch.setattr("export_locids_sql.get_all_geojson_files", mock_get_all_geojson_files)

    # Test with specific fields
    results = list(export_locids_sql.iter_feature_data(show_progress=False, fields=["loc_id", "name", "tech"]))

    assert len(results) == 1
    assert "loc_id" in results[0]
    assert "name" in results[0]
    assert "tech" in results[0]
    assert results[0]["loc_id"] == "LOC000190342926"
    assert results[0]["name"] == "100 STEPHENSON AVENUE MOUNT CLAREMONT 6010"
    assert results[0]["tech"] == "FTTN"


def test_iter_feature_data_skip_missing_locid(monkeypatch):
    """Test that features without locID are skipped."""
    mock_geojson = {
        "features": [
            {
                "geometry": {"coordinates": [115.78506081, -31.95270506]},
                "properties": {
                    "name": "Missing LocID",
                    "tech": "FTTN",
                },
            },
            {
                "geometry": {"coordinates": [115.77758570, -31.96588092]},
                "properties": {
                    "name": "Has LocID",
                    "locID": "LOC000027955790",
                    "tech": "HFC",
                },
            },
        ]
    }

    def mock_get_all_geojson_files(show_progress=True, rewrite_geojson=False):
        yield "test.geojson", mock_geojson

    monkeypatch.setattr("export_locids_sql.get_all_geojson_files", mock_get_all_geojson_files)

    results = list(export_locids_sql.iter_feature_data(show_progress=False, fields=["loc_id", "name"]))

    assert len(results) == 1
    assert results[0]["loc_id"] == "LOC000027955790"


def test_iter_feature_data_skip_missing_coordinates(monkeypatch):
    """Test that features without valid coordinates are skipped."""
    mock_geojson = {
        "features": [
            {
                "geometry": {"coordinates": None},
                "properties": {
                    "locID": "LOC000001",
                    "name": "Missing coords",
                },
            },
            {
                "geometry": {"coordinates": [None, None]},
                "properties": {
                    "locID": "LOC000002",
                    "name": "Null coords",
                },
            },
            {
                "geometry": {"coordinates": [115.77758570, -31.96588092]},
                "properties": {
                    "locID": "LOC000003",
                    "name": "Valid coords",
                },
            },
        ]
    }

    def mock_get_all_geojson_files(show_progress=True, rewrite_geojson=False):
        yield "test.geojson", mock_geojson

    monkeypatch.setattr("export_locids_sql.get_all_geojson_files", mock_get_all_geojson_files)

    results = list(export_locids_sql.iter_feature_data(show_progress=False, fields=["loc_id", "name"]))

    assert len(results) == 1
    assert results[0]["loc_id"] == "LOC000003"


def test_write_sql_basic():
    """Test writing SQL with basic data."""
    rows = [
        {"loc_id": "LOC001", "latitude": -31.95270506, "longitude": 115.78506081, "name": "Test Address 1", "tech": "FTTN", "upgrade": "FTTP_NA", "gnaf_pid": "GAWA_123", "tech_change_status": "In Design", "program_type": "Test Program", "target_eligibility_quarter": "Mar 2028"},
        {"loc_id": "LOC002", "latitude": -31.96588092, "longitude": 115.77758570, "name": "Test Address 2", "tech": "HFC", "upgrade": "NULL_NA", "gnaf_pid": "GAWA_456", "tech_change_status": "", "program_type": "", "target_eligibility_quarter": ""},
    ]

    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = os.path.join(tmpdir, "test.sql")
        count = export_locids_sql.write_sql(output_path, rows, export_locids_sql.AVAILABLE_FIELDS, dedupe=True)

        assert count == 2
        assert os.path.exists(output_path)

        with open(output_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Check that CREATE TABLE statement is present (without secondary index)
        assert "CREATE TABLE IF NOT EXISTS locids" in content
        assert "locid VARCHAR(20) PRIMARY KEY" in content
        assert "latitude DECIMAL(10, 7) NOT NULL" in content
        assert "longitude DECIMAL(10, 7) NOT NULL" in content
        
        # Check that index is created after data load
        assert "CREATE INDEX IF NOT EXISTS idx_lat_lng ON locids (latitude, longitude)" in content
        
        # Check that INSERT statements are present
        assert "INSERT INTO locids" in content
        assert "LOC001" in content
        assert "LOC002" in content
        assert "Test Address 1" in content
        assert "Test Address 2" in content
        
        # Verify the index comes after the INSERT statements
        create_index_pos = content.find("CREATE INDEX IF NOT EXISTS idx_lat_lng")
        insert_pos = content.find("INSERT INTO locids")
        assert create_index_pos > insert_pos, "Index should be created after data insertion"


def test_write_sql_dedupe():
    """Test SQL deduplication by loc_id."""
    rows = [
        {"loc_id": "LOC001", "latitude": -31.95270506, "longitude": 115.78506081, "name": "Address 1", "tech": "FTTN", "upgrade": "FTTP_NA", "gnaf_pid": "GAWA_123", "tech_change_status": "", "program_type": "", "target_eligibility_quarter": ""},
        {"loc_id": "LOC001", "latitude": -31.95270506, "longitude": 115.78506081, "name": "Address 1", "tech": "FTTN", "upgrade": "FTTP_NA", "gnaf_pid": "GAWA_123", "tech_change_status": "", "program_type": "", "target_eligibility_quarter": ""},  # duplicate
        {"loc_id": "LOC002", "latitude": -31.96588092, "longitude": 115.77758570, "name": "Address 2", "tech": "HFC", "upgrade": "NULL_NA", "gnaf_pid": "GAWA_456", "tech_change_status": "", "program_type": "", "target_eligibility_quarter": ""},
    ]

    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = os.path.join(tmpdir, "test.sql")

        # With deduplication
        count = export_locids_sql.write_sql(output_path, rows, export_locids_sql.AVAILABLE_FIELDS, dedupe=True)
        assert count == 2

        # Without deduplication
        count = export_locids_sql.write_sql(output_path, rows, export_locids_sql.AVAILABLE_FIELDS, dedupe=False)
        assert count == 3


def test_write_sql_special_characters():
    """Test writing SQL with special characters that need escaping."""
    rows = [
        {"loc_id": "LOC001", "latitude": -31.95270506, "longitude": 115.78506081, "name": "O'Brien's Address", "tech": "FTTN", "upgrade": "FTTP_NA", "gnaf_pid": "GAWA_123", "tech_change_status": "It's ready", "program_type": "", "target_eligibility_quarter": ""},
    ]

    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = os.path.join(tmpdir, "test.sql")
        count = export_locids_sql.write_sql(output_path, rows, export_locids_sql.AVAILABLE_FIELDS, dedupe=True)

        assert count == 1

        with open(output_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Check that single quotes are escaped
        assert "O''Brien''s Address" in content
        assert "It''s ready" in content


def test_available_fields_constant():
    """Test that AVAILABLE_FIELDS contains expected fields."""
    expected_fields = [
        "loc_id",
        "latitude",
        "longitude",
        "name",
        "tech",
        "upgrade",
        "gnaf_pid",
        "tech_change_status",
        "program_type",
        "target_eligibility_quarter",
    ]
    assert export_locids_sql.AVAILABLE_FIELDS == expected_fields


def test_default_fields_constant():
    """Test that DEFAULT_FIELDS maintains backward compatibility."""
    assert export_locids_sql.DEFAULT_FIELDS == ["loc_id", "latitude", "longitude"]
