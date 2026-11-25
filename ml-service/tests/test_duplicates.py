from datetime import datetime, timezone

from app.core.duplicate_engine import _score_pair, analyze_duplicates
from app.core.text_similarity import lexical_similarity
from app.schemas import ComplaintRecord


def test_hybrid_explains_high_text_category_and_location_match():
    a = ComplaintRecord(id="a", complaint_number=1, description="Large pothole near bus stop",
                        category="road damage", latitude=0, longitude=0,
                        submitted_at=datetime(2025, 1, 1, tzinfo=timezone.utc))
    b = ComplaintRecord(id="b", complaint_number=2, description="Large potholl near bus stand",
                        category="road damage", latitude=0.0002, longitude=0.0001,
                        submitted_at=datetime(2025, 1, 2, tzinfo=timezone.utc))
    result = analyze_duplicates(a, [a, b])
    assert result["candidate_count"] == 1
    match = result["matches"][0]
    assert match["complaint_id"] == "b"
    assert match["signals"]["category_match"] is True
    assert match["signals"]["distance_meters"] is not None
    assert match["explanation"]
    assert result["model_version"]


def test_nearby_different_issue_cannot_become_duplicate_from_location_alone():
    a = ComplaintRecord(id="a", description="Damaged traffic signal", category="traffic", latitude=0, longitude=0)
    b = ComplaintRecord(id="b", description="Water pipe leakage", category="water", latitude=0.0001, longitude=0.0001)
    lexical = lexical_similarity(a.description, [b.description])[0]
    result = _score_pair(a, b, lexical, None)
    assert result["similarity_score"] < 35


def test_missing_signals_are_renormalized_safely():
    a = ComplaintRecord(id="a", description="pothole by library")
    b = ComplaintRecord(id="b", description="road hole by library")
    result = analyze_duplicates(a, [b])["matches"][0]
    assert result["signals"]["distance_meters"] is None
    assert result["signals"]["temporal_relevance"] is None
    assert any("Coordinates were missing" in value for value in result["warnings"])


def test_duplicate_query_with_no_candidates_is_valid():
    a = ComplaintRecord(id="a", description="pothole")
    result = analyze_duplicates(a, [])
    assert result["matches"] == []
    assert result["analysis_status"] == "completed"
