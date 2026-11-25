"""DBSCAN hotspot identification using geodesic (Haversine) distance."""

import math
from collections import Counter
from datetime import timezone
from typing import Optional

import numpy as np
from sklearn.cluster import DBSCAN

from app.core.geographic_similarity import EARTH_RADIUS_METERS, haversine_meters


def _as_utc(value):
    if value is None:
        return None
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def _category(record):
    return record.category or record.category_id or "Uncategorized"


def _center(points):
    radians = np.radians(np.asarray(points, dtype=float))
    lat, lon = radians[:, 0], radians[:, 1]
    x = np.cos(lat) * np.cos(lon)
    y = np.cos(lat) * np.sin(lon)
    z = np.sin(lat)
    return [
        round(math.degrees(math.atan2(z.mean(), math.sqrt(x.mean() ** 2 + y.mean() ** 2))), 6),
        round(math.degrees(math.atan2(y.mean(), x.mean())), 6),
    ]


def detect_hotspots(records, epsilon_meters: float = 500, min_samples: int = 3,
                    start_date=None, end_date=None, category_id: Optional[str] = None,
                    density_medium_per_km2: float = 10, density_high_per_km2: float = 30) -> dict:
    eligible, excluded_coordinates, excluded_filters = [], 0, 0
    start, end = _as_utc(start_date), _as_utc(end_date)
    for record in records:
        if category_id and (record.category_id or "") != category_id:
            excluded_filters += 1
            continue
        submitted = _as_utc(record.submitted_at)
        if (start and (submitted is None or submitted < start)) or (end and (submitted is None or submitted > end)):
            excluded_filters += 1
            continue
        if record.latitude is None or record.longitude is None:
            excluded_coordinates += 1
            continue
        eligible.append(record)

    if len(eligible) < min_samples:
        return {
            "analysis_status": "insufficient_data",
            "clusters": [],
            "input_count": len(records),
            "geocoded_count": len(eligible),
            "excluded_missing_coordinates": excluded_coordinates,
            "excluded_by_filters": excluded_filters,
            "noise_count": len(eligible),
            "warnings": ["At least min_samples geocoded complaints are needed to form a hotspot."],
        }

    coordinates = np.radians([[row.latitude, row.longitude] for row in eligible])
    labels = DBSCAN(eps=epsilon_meters / EARTH_RADIUS_METERS, min_samples=min_samples,
                    metric="haversine", algorithm="ball_tree").fit_predict(coordinates)
    clusters = []
    for cluster_label in sorted(set(int(value) for value in labels if value >= 0)):
        indices = np.flatnonzero(labels == cluster_label).tolist()
        members = [eligible[index] for index in indices]
        points = [(member.latitude, member.longitude) for member in members]
        center = _center(points)
        radius = max(haversine_meters(tuple(center), point) for point in points)
        effective_radius_km = max(radius, epsilon_meters / 2) / 1000
        density = len(members) / (math.pi * effective_radius_km ** 2)
        density_class = "high" if density >= density_high_per_km2 else "medium" if density >= density_medium_per_km2 else "low"
        category_counts = Counter(_category(member) for member in members)
        date_values = [value for value in (_as_utc(member.submitted_at) for member in members) if value]
        clusters.append({
            "cluster_id": "hotspot-{}".format(cluster_label + 1),
            "center": {"latitude": center[0], "longitude": center[1]},
            "complaint_count": len(members),
            "dominant_category": category_counts.most_common(1)[0][0],
            "category_counts": dict(category_counts),
            "radius_meters": round(radius, 1),
            "estimated_density_per_km2": round(density, 2),
            "density_classification": density_class,
            "start_date": min(date_values).isoformat() if date_values else None,
            "end_date": max(date_values).isoformat() if date_values else None,
            "complaint_ids": [member.id for member in members],
        })

    return {
        "analysis_status": "completed",
        "clusters": clusters,
        "input_count": len(records),
        "geocoded_count": len(eligible),
        "excluded_missing_coordinates": excluded_coordinates,
        "excluded_by_filters": excluded_filters,
        "noise_count": int((labels == -1).sum()),
        "parameters": {"epsilon_meters": epsilon_meters, "min_samples": min_samples,
                       "density_medium_per_km2": density_medium_per_km2,
                       "density_high_per_km2": density_high_per_km2},
        "warnings": [],
    }
