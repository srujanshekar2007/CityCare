"""Internal intelligence endpoints; operational access is mediated by Express."""

import json
from pathlib import Path
from fastapi import APIRouter, Depends, Header, HTTPException, status

from app.config import settings
from app.core.duplicate_engine import MODEL_NAME, MODEL_VERSION, WEIGHTS, analyze_duplicates, thresholds
from app.core.hotspot_detection import detect_hotspots
from app.models.model_registry import semantic_status
from app.schemas import BatchDuplicateRequest, DuplicateAnalyzeRequest, HotspotRequest

router = APIRouter(prefix="/api/v1")
_RESULTS = Path(__file__).resolve().parents[1] / "evaluation" / "results.json"


def require_service_token(authorization: str = Header(default="")) -> None:
    if not settings.service_token:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                            detail="Internal service authentication is not configured")
    scheme, _, token = authorization.partition(" ")
    import hmac

    if scheme.lower() != "bearer" or not hmac.compare_digest(token, settings.service_token):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="Internal service authentication required")


@router.get("/model/info", dependencies=[Depends(require_service_token)])
def model_info():
    high, possible, source = thresholds()
    return {
        "model_name": MODEL_NAME,
        "model_version": MODEL_VERSION,
        "available_similarity_methods": ["word_tfidf_unigram_bigram", "character_tfidf_char_wb_3_5",
                                          "rapidfuzz_wratio", "category", "haversine_geography",
                                          "exponential_temporal_decay"],
        "weights": WEIGHTS,
        "thresholds": {"high": high, "possible": possible, "source": source},
        "semantic_model": semantic_status(load=False),
        "configuration": {"max_candidates": settings.max_candidates,
                           "temporal_half_life_days": settings.temporal_half_life_days,
                           "geo_proximity_scale_meters": settings.geo_scale_meters},
    }


@router.post("/duplicates/analyze", dependencies=[Depends(require_service_token)])
def duplicates_analyze(payload: DuplicateAnalyzeRequest):
    if len(payload.candidates) > settings.max_candidates:
        raise HTTPException(status_code=413, detail="Candidate limit exceeded")
    return analyze_duplicates(payload.complaint, payload.candidates, payload.top_k)


@router.post("/duplicates/batch", dependencies=[Depends(require_service_token)])
def duplicates_batch(payload: BatchDuplicateRequest):
    if len(payload.candidates) > settings.max_candidates:
        raise HTTPException(status_code=413, detail="Candidate limit exceeded")
    # Bounded at 10 queries × configured candidate cap; no unbounded pairwise work.
    return {"analysis_status": "completed", "query_count": len(payload.queries),
            "candidate_count": len(payload.candidates), "results": [
                analyze_duplicates(query, payload.candidates, payload.top_k)
                for query in payload.queries
            ]}


@router.post("/hotspots/analyze", dependencies=[Depends(require_service_token)])
def hotspots_analyze(payload: HotspotRequest):
    return detect_hotspots(payload.complaints, payload.epsilon_meters, payload.min_samples,
                           payload.start_date, payload.end_date, payload.category_id,
                           payload.density_medium_per_km2, payload.density_high_per_km2)


@router.get("/evaluation/summary", dependencies=[Depends(require_service_token)])
def evaluation_summary():
    if not _RESULTS.exists():
        return {"status": "not_run", "dataset_type": "manually_labeled_synthetic_demonstration_pairs",
                "message": "Run scripts/run_evaluation.py to produce the local benchmark summary."}
    try:
        return json.loads(_RESULTS.read_text())
    except (OSError, json.JSONDecodeError):
        raise HTTPException(status_code=500, detail="Evaluation summary is unavailable")
