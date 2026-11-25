from app.core.geographic_similarity import distance_if_available, haversine_meters
from app.schemas import ComplaintRecord


def test_haversine_distance_matches_known_equatorial_degree():
    distance = haversine_meters((0, 0), (0.001, 0))
    assert 110 <= distance <= 112


def test_missing_coordinates_are_omitted():
    left = ComplaintRecord(id="a", description="x", latitude=1, longitude=2)
    right = ComplaintRecord(id="b", description="x")
    assert distance_if_available(left, right) is None


def test_one_coordinate_without_its_pair_is_invalid():
    try:
        ComplaintRecord(id="a", description="x", latitude=1)
    except ValueError:
        return
    raise AssertionError("Expected latitude/longitude pair validation")
