"""Conservative text cleanup that preserves negation and issue details."""

import re
import unicodedata
from typing import List


_TOKEN_RE = re.compile(r"[a-z0-9]+(?:'[a-z]+)?")
_ALIASES = {
    "busstand": "bus stop",
    "busstande": "bus stop",
    "potholes": "pothole",
    "potholl": "pothole",
    "potholee": "pothole",
    "kachra": "garbage",
    "kooda": "garbage",
    "sadak": "road",
    "gaddha": "pothole",
    "gadda": "pothole",
    "nali": "drain",
}
_PHRASE_ALIASES = (("bus stand", "bus stop"), ("busstop", "bus stop"))


def normalize_unicode(text: str) -> str:
    return unicodedata.normalize("NFKC", text or "")


def tokenize(text: str) -> List[str]:
    normalized = normalize_unicode(text).lower()
    normalized = re.sub(r"(.)\1{2,}", r"\1\1", normalized)
    normalized = normalized.replace("&", " and ")
    normalized = re.sub(r"[^\w\s']", " ", normalized, flags=re.UNICODE)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    for source, target in _PHRASE_ALIASES:
        normalized = normalized.replace(source, target)
    tokens = _TOKEN_RE.findall(normalized)
    return [_ALIASES.get(token, token) for token in tokens]


def preprocess_text(text: str) -> str:
    """Return a normalized lexical form; no stopword or negation deletion."""
    return " ".join(tokenize(text))
