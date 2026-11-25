import json

import pytest

from app.data.dataset_loader import load_records
from app.data.validation import validate_records


def test_load_and_validate_json_records(tmp_path):
    path = tmp_path / "records.json"
    path.write_text(json.dumps({"records": [{"id": "one", "description": "Pothole"}]}))
    records = validate_records(load_records(path))
    assert len(records) == 1
    assert records[0].description == "Pothole"


def test_loader_rejects_unknown_format(tmp_path):
    path = tmp_path / "records.txt"
    path.write_text("private complaint data")
    with pytest.raises(ValueError, match="Supported dataset formats"):
        load_records(path)


def test_validator_rejects_invalid_coordinate_pair():
    with pytest.raises(ValueError, match="Invalid complaint record"):
        validate_records([{"id": "one", "latitude": 12.0}])
