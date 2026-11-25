"""Manually labeled synthetic demonstration pairs; never CityCare citizen reports."""

import json
from pathlib import Path


DATA_PATH = Path(__file__).resolve().parent / "demo_pairs.json"


def load_demo_pairs():
    payload = json.loads(DATA_PATH.read_text())
    if payload.get("dataset_type") != "manually_labeled_synthetic_demonstration_pairs":
        raise ValueError("Only the clearly labeled demonstration benchmark is supported here")
    return payload["pairs"]
