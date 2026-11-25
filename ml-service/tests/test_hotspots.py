from datetime import datetime, timezone

from app.core.hotspot_detection import detect_hotspots
from app.schemas import ComplaintRecord


def test_dbscan_groups_close_records_and_keeps_noise_and_missing_coordinates():
    records = [
        ComplaintRecord(id="a", description="x", category="waste", latitude=0, longitude=0,
                        submitted_at=datetime(2025, 1, 1, tzinfo=timezone.utc)),
        ComplaintRecord(id="b", description="x", category="waste", latitude=0.0001, longitude=0.0001,
                        submitted_at=datetime(2025, 1, 2, tzinfo=timezone.utc)),
        ComplaintRecord(id="c", description="x", category="water", latitude=0.0002, longitude=0.0001),
        ComplaintRecord(id="noise", description="x", latitude=20, longitude=20),
        ComplaintRecord(id="missing", description="x"),
    ]
    result = detect_hotspots(records, epsilon_meters=500, min_samples=3)
    assert len(result["clusters"]) == 1
    cluster = result["clusters"][0]
    assert cluster["complaint_count"] == 3
    assert cluster["dominant_category"] == "waste"
    assert set(cluster["complaint_ids"]) == {"a", "b", "c"}
    assert result["noise_count"] == 1
    assert result["excluded_missing_coordinates"] == 1


def test_insufficient_records_has_explicit_empty_result():
    result = detect_hotspots([ComplaintRecord(id="x", description="y", latitude=0, longitude=0)],
                             min_samples=3)
    assert result["analysis_status"] == "insufficient_data"
    assert result["clusters"] == []
