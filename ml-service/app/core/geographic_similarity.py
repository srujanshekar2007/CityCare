"""Haversine distance and interpretable distance relevance."""

import math
from typing import Optional, Tuple

EARTH_RADIUS_METERS = 6_371_008.8


def haversine_meters(a: Tuple[float, float], b: Tuple[float, float]) -> float:
    lat1, lon1 = map(math.radians, a)
    lat2, lon2 = map(math.radians, b)
    dlat, dlon = lat2 - lat1, lon2 - lon1
    value = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 2 * EARTH_RADIUS_METERS * math.asin(min(1.0, math.sqrt(value)))


def distance_if_available(a, b) -> Optional[float]:
    if a.latitude is None or a.longitude is None or b.latitude is None or b.longitude is None:
        return None
    return haversine_meters((a.latitude, a.longitude), (b.latitude, b.longitude))


def proximity_score(distance_meters: Optional[float], scale_meters: float) -> Optional[float]:
    if distance_meters is None:
        return None
    return math.exp(-max(0.0, distance_meters) / scale_meters)
