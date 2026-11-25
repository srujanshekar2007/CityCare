"""Lazy optional Sentence Transformers adapter with bounded embedding cache."""

from functools import lru_cache
from typing import Optional, Tuple

import numpy as np

from app.config import settings

_model = None
_load_error: Optional[str] = None


def _load_model():
    global _model, _load_error
    if _model is not None or _load_error is not None or not settings.semantic_enabled:
        return _model
    try:
        from sentence_transformers import SentenceTransformer  # optional dependency

        _model = SentenceTransformer(settings.semantic_model)
    except Exception as exc:  # offline installs and missing optional package are expected
        _load_error = type(exc).__name__
    return _model


@lru_cache(maxsize=2048)
def _embedding(text: str) -> Tuple[float, ...]:
    model = _load_model()
    if model is None or not text:
        return tuple()
    vector = model.encode([text], normalize_embeddings=True, show_progress_bar=False)[0]
    return tuple(float(value) for value in vector)


def semantic_similarity(left: str, right: str) -> Optional[float]:
    if not settings.semantic_enabled or not left or not right:
        return None
    left_vector, right_vector = _embedding(left), _embedding(right)
    if not left_vector or not right_vector:
        return None
    # Embeddings are unit-normalized, so their dot product is cosine similarity.
    return max(0.0, min(1.0, float(np.dot(left_vector, right_vector))))


def semantic_status(load: bool = False) -> dict:
    model = _load_model() if load and settings.semantic_enabled else _model
    return {
        "enabled": settings.semantic_enabled,
        "available": model is not None,
        "load_state": "ready" if model is not None else "disabled" if not settings.semantic_enabled else "not_loaded",
        "model": settings.semantic_model if settings.semantic_enabled else None,
        "error_type": _load_error,
        "cached_embeddings": _embedding.cache_info().currsize,
    }
