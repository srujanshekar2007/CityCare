from app.core.preprocessing import preprocess_text


def test_normalizes_unicode_punctuation_whitespace_and_repeated_characters():
    assert preprocess_text("  Potholl!!!   BUS stand  ") == "pothole bus stop"
    assert preprocess_text("Roooadddd") == "rooadd"


def test_preserves_negation_and_issue_words():
    value = preprocess_text("No drain is NOT blocked; water is overflowing and dangerous.")
    assert "no" in value and "not" in value and "blocked" in value
    assert "overflowing" in value and "dangerous" in value


def test_supports_documented_romanized_terms_without_claiming_translation():
    assert preprocess_text("Kachra beside the sadak") == "garbage beside the road"


def test_empty_text_is_safe():
    assert preprocess_text("") == ""
