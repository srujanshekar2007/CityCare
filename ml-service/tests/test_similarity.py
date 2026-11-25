from app.core.text_similarity import lexical_similarity


def test_word_character_and_fuzzy_signals_are_computed():
    result = lexical_similarity("Large pothole near bus stop", ["Large potholl near the bus stand"])[0]
    assert 0 <= result["word_similarity"] <= 1
    assert result["character_similarity"] > 0
    assert result["fuzzy_similarity"] > 0.5


def test_empty_text_does_not_create_false_similarity():
    result = lexical_similarity("", [""])[0]
    assert result["word_similarity"] == 0
    assert result["character_similarity"] == 0
    assert result["fuzzy_similarity"] == 0


def test_negation_is_not_removed_from_word_features():
    results = lexical_similarity("drain is not blocked", ["drain is blocked", "drain is not blocked"])
    assert results[1]["word_similarity"] > results[0]["word_similarity"]
