"""Human-readable explanations for model recommendations."""


def explain_match(signals: dict, score: float) -> list:
    explanations = []
    lexical = [signals.get("word_similarity", 0), signals.get("character_similarity", 0),
               signals.get("fuzzy_similarity", 0), signals.get("semantic_similarity")]
    lexical = [value for value in lexical if value is not None]
    if lexical and sum(lexical) / len(lexical) >= 0.55:
        explanations.append("Descriptions share meaningful wording or issue context.")
    if signals.get("category_match") is True:
        explanations.append("Both reports use the same complaint category.")
    elif signals.get("category_match") is False:
        explanations.append("The categories differ, which lowers the combined score.")
    distance = signals.get("distance_meters")
    if distance is not None:
        if distance <= 300:
            explanations.append("Reported coordinates are within 300 metres.")
        elif distance <= 1500:
            explanations.append("Reported coordinates are nearby.")
        else:
            explanations.append("The reports are geographically separated.")
    relevance = signals.get("temporal_relevance")
    if relevance is not None and relevance >= 0.7:
        explanations.append("The reports were submitted within a relatively recent time window.")
    if not explanations:
        explanations.append("The available description signals are weak; review before taking action.")
    if score < 35:
        explanations.append("The overall evidence is weak and this is not a duplicate recommendation.")
    return explanations
