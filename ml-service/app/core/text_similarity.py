"""Word, character and fuzzy lexical similarity features."""

from typing import Dict, List, Tuple

from rapidfuzz import fuzz
from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS, TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from app.core.preprocessing import preprocess_text

_PRESERVED_NEGATIONS = {"no", "not", "nor", "never", "without"}
_STOP_WORDS = sorted(set(ENGLISH_STOP_WORDS) - _PRESERVED_NEGATIONS)


def lexical_similarity(query: str, candidates: List[str]) -> List[Dict[str, float]]:
    texts = [preprocess_text(query)] + [preprocess_text(value) for value in candidates]
    word = [0.0] * len(candidates)
    char = [0.0] * len(candidates)
    non_empty_indices = [index for index, value in enumerate(texts) if value]

    if len(non_empty_indices) >= 2:
        compact_texts = [texts[index] for index in non_empty_indices]
        try:
            matrix = TfidfVectorizer(
                ngram_range=(1, 2), min_df=1, sublinear_tf=True, stop_words=_STOP_WORDS,
                max_features=50000,
            ).fit_transform(compact_texts)
            query_row = non_empty_indices.index(0) if 0 in non_empty_indices else None
            if query_row is not None:
                for candidate_index in range(len(candidates)):
                    if candidate_index + 1 in non_empty_indices:
                        row = non_empty_indices.index(candidate_index + 1)
                        word[candidate_index] = float(cosine_similarity(matrix[query_row], matrix[row])[0, 0])
        except ValueError:
            pass
        try:
            matrix = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), min_df=1,
                                     sublinear_tf=True, max_features=80000).fit_transform(compact_texts)
            query_row = non_empty_indices.index(0) if 0 in non_empty_indices else None
            if query_row is not None:
                for candidate_index in range(len(candidates)):
                    if candidate_index + 1 in non_empty_indices:
                        row = non_empty_indices.index(candidate_index + 1)
                        char[candidate_index] = float(cosine_similarity(matrix[query_row], matrix[row])[0, 0])
        except ValueError:
            pass

    output = []
    for index, candidate in enumerate(candidates):
        left, right = texts[0], texts[index + 1]
        fuzzy_score = fuzz.WRatio(left, right) / 100.0 if left and right else 0.0
        output.append({
            "word_similarity": round(word[index], 6),
            "character_similarity": round(char[index], 6),
            "fuzzy_similarity": round(fuzzy_score, 6),
        })
    return output
