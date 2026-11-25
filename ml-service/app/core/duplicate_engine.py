"""Explainable, missing-signal-aware hybrid duplicate recommendation model."""

import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional, Tuple

from app.config import settings
from app.core.explanations import explain_match
from app.core.geographic_similarity import distance_if_available, proximity_score
from app.core.preprocessing import preprocess_text
from app.core.text_similarity import lexical_similarity
from app.models.model_registry import semantic_similarity, semantic_status

MODEL_NAME = "citycare-hybrid-nlp"
MODEL_VERSION = "1.0.0"
WEIGHTS = {
    "word_similarity": 0.24,
    "character_similarity": 0.18,
    "fuzzy_similarity": 0.14,
    "semantic_similarity": 0.18,
    "category_signal": 0.10,
    "geographic_proximity": 0.11,
    "temporal_relevance": 0.05,
}
_CALIBRATION_PATH = Path(__file__).resolve().parents[1] / "evaluation" / "calibration.json"


def thresholds() -> Tuple[float, float, str]:
    high, possible = settings.high_threshold, settings.possible_threshold
    if high is not None and possible is not None:
        return high, possible, "environment"
    try:
        calibration = json.loads(_CALIBRATION_PATH.read_text())
        if high is None:
            high = float(calibration["high_threshold"])
        if possible is None:
            possible = float(calibration["possible_threshold"])
        return high, possible, "manually_labeled_demonstration_benchmark"
    except (OSError, ValueError, KeyError, TypeError):
        return high or 0.82, possible or 0.60, "conservative_fallback_uncalibrated"


def _utc(value: Optional[datetime]) -> Optional[datetime]:
    if value is None:
        return None
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def _category_value(record) -> Optional[str]:
    value = record.category_id or record.category
    return value.strip().casefold() if value else None


def _temporal_relevance(left, right) -> Optional[float]:
    a, b = _utc(left.submitted_at), _utc(right.submitted_at)
    if a is None or b is None:
        return None
    delta_days = abs((a - b).total_seconds()) / 86400.0
    return math.exp(-math.log(2) * delta_days / max(settings.temporal_half_life_days, 1.0))


def _confidence(score: float, high: float, possible: float) -> str:
    if score >= high:
        return "high"
    if score >= possible:
        return "possible"
    return "unlikely"


def _score_pair(query, candidate, lexical: Dict[str, float], semantic: Optional[float]) -> dict:
    distance = distance_if_available(query, candidate)
    proximity = proximity_score(distance, max(settings.geo_scale_meters, 1.0))
    time_relevance = _temporal_relevance(query, candidate)
    left_category, right_category = _category_value(query), _category_value(candidate)
    category_match = (left_category == right_category) if left_category and right_category else None
    category_signal = (1.0 if category_match else 0.12) if category_match is not None else None

    signals = {
        **lexical,
        "semantic_similarity": round(semantic, 6) if semantic is not None else None,
        "category_match": category_match,
        "category_signal": category_signal,
        "distance_meters": round(distance, 1) if distance is not None else None,
        "geographic_proximity": round(proximity, 6) if proximity is not None else None,
        "temporal_relevance": round(time_relevance, 6) if time_relevance is not None else None,
    }
    values = {
        "word_similarity": lexical["word_similarity"],
        "character_similarity": lexical["character_similarity"],
        "fuzzy_similarity": lexical["fuzzy_similarity"],
        "semantic_similarity": semantic,
        "category_signal": category_signal,
        "geographic_proximity": proximity,
        "temporal_relevance": time_relevance,
    }
    available = [(WEIGHTS[key], value) for key, value in values.items() if value is not None]
    denominator = sum(weight for weight, _ in available)
    score = 100.0 * sum(weight * value for weight, value in available) / denominator if denominator else 0.0
    lexical_strength = (lexical["word_similarity"] + lexical["character_similarity"] + lexical["fuzzy_similarity"]) / 3
    # Location and time can adjust text evidence, but cannot by themselves create a match.
    if lexical_strength < 0.18:
        score *= lexical_strength / 0.18
    if category_match is False and lexical_strength < 0.78:
        score *= 0.78
    return {
        "similarity_score": round(max(0.0, min(100.0, score)), 2),
        "signals": signals,
        "_lexical_strength": lexical_strength,
    }


def analyze_duplicates(query, candidates, top_k: int = 20) -> dict:
    unique_candidates = [candidate for candidate in candidates if candidate.id != query.id]
    lexical = lexical_similarity(query.description, [candidate.description for candidate in unique_candidates])
    semantic_values = [semantic_similarity(preprocess_text(query.description), preprocess_text(candidate.description))
                       for candidate in unique_candidates]
    high_threshold, possible_threshold, threshold_source = thresholds()
    matches = []
    for candidate, lexical_signals, semantic in zip(unique_candidates, lexical, semantic_values):
        result = _score_pair(query, candidate, lexical_signals, semantic)
        score = result["similarity_score"]
        band = _confidence(score, high_threshold, possible_threshold)
        warnings = []
        if semantic is None:
            warnings.append("Semantic embeddings are unavailable; lexical, category, location and time signals were used.")
        if result["signals"]["distance_meters"] is None:
            warnings.append("Coordinates were missing; geographical similarity was omitted and the other weights were renormalized.")
        if result["signals"]["temporal_relevance"] is None:
            warnings.append("Submission timestamp was missing; temporal relevance was omitted and the other weights were renormalized.")
        matches.append({
            "complaint_id": candidate.id,
            "complaint_number": candidate.complaint_number,
            "description": candidate.description,
            "category": candidate.category or candidate.category_id,
            "location": candidate.location_description,
            "similarity_score": score,
            "confidence_band": band,
            "signals": result["signals"],
            "explanation": explain_match(result["signals"], score),
            "warnings": sorted(set(warnings)),
        })
    matches.sort(key=lambda item: (-item["similarity_score"], str(item["complaint_id"])))
    visible = matches[:top_k]
    semantic = semantic_status()
    warnings = []
    if not semantic["available"]:
        warnings.append("Optional semantic embeddings are disabled or unavailable; no semantic score was used.")
    if not unique_candidates:
        warnings.append("No candidate complaints were available in the caller's permitted comparison scope.")
    return {
        "query_complaint_id": query.id,
        "analysis_status": "completed",
        "model_name": MODEL_NAME,
        "model_version": MODEL_VERSION,
        "thresholds": {"high": high_threshold, "possible": possible_threshold, "source": threshold_source},
        "semantic_model": semantic,
        "weights": WEIGHTS,
        "candidate_count": len(unique_candidates),
        "matches": visible,
        "recommendations": [match for match in visible if match["confidence_band"] != "unlikely"],
        "warnings": warnings,
    }
