"""Validate offline datasets before an authorized evaluation run."""

from typing import Dict, Iterable, List

from app.schemas import ComplaintRecord


def validate_records(records: Iterable[Dict]) -> List[ComplaintRecord]:
    """Parse records against the same bounded contract used by the API."""
    validated = []
    for index, record in enumerate(records):
        try:
            validated.append(ComplaintRecord.model_validate(record))
        except Exception as exc:
            raise ValueError("Invalid complaint record at row {}: {}".format(index + 1, exc)) from exc
    return validated
