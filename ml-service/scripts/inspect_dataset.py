#!/usr/bin/env python3
"""Inspect schema completeness without printing complaint text or coordinates."""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.data.dataset_loader import load_records
from app.data.validation import validate_records


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dataset", help="Local CSV, JSON, or JSONL file")
    args = parser.parse_args()
    records = load_records(args.dataset)
    validated = validate_records(records)
    print("Validated {} records; complaint text and personal fields were not displayed.".format(len(validated)))
    print("With description: {}".format(sum(bool(row.description) for row in validated)))
    print("With coordinates: {}".format(sum(row.latitude is not None for row in validated)))
    print("With category: {}".format(sum(bool(row.category_id or row.category) for row in validated)))
    print("With submission timestamp: {}".format(sum(row.submitted_at is not None for row in validated)))


if __name__ == "__main__":
    main()
