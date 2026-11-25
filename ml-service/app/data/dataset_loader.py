"""Load local JSON, JSONL, or CSV records for offline evaluation only."""

import csv
import json
from pathlib import Path
from typing import Dict, List


def load_records(path) -> List[Dict]:
    source = Path(path)
    if not source.is_file():
        raise FileNotFoundError("Dataset file does not exist: {}".format(source))
    if source.stat().st_size > 25_000_000:
        raise ValueError("Dataset exceeds the 25 MB offline safety limit")
    suffix = source.suffix.lower()
    if suffix == ".jsonl":
        with source.open(encoding="utf-8") as handle:
            values = [json.loads(line) for line in handle if line.strip()]
    elif suffix == ".json":
        with source.open(encoding="utf-8") as handle:
            values = json.load(handle)
    elif suffix == ".csv":
        with source.open(newline="", encoding="utf-8-sig") as handle:
            values = list(csv.DictReader(handle))
    else:
        raise ValueError("Supported dataset formats are .json, .jsonl, and .csv")
    if isinstance(values, dict):
        values = values.get("records")
    if not isinstance(values, list) or len(values) > 100_000:
        raise ValueError("Dataset must be a list or contain a records list of at most 100000 entries")
    if not all(isinstance(item, dict) for item in values):
        raise ValueError("Every dataset row must be an object")
    return values
