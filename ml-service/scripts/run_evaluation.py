#!/usr/bin/env python3
"""Evaluate baselines and calibrate thresholds on the labeled demo benchmark."""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import numpy as np

from app.evaluation.metrics import classification_metrics
from app.evaluation.test_cases import load_demo_pairs
from app.schemas import ComplaintRecord
from app.core.duplicate_engine import _score_pair, analyze_duplicates
from app.core.text_similarity import lexical_similarity
from app.models.model_registry import semantic_similarity
from app.core.preprocessing import preprocess_text
from app.config import settings


def _best_f1_threshold(labels, scores):
    candidates = sorted(set([0.0, 1.0] + [float(score) for score in scores]))
    ranked = []
    for threshold in candidates:
        metric = classification_metrics(labels, scores, threshold)
        ranked.append((metric["f1_score"], metric["precision"], threshold, metric))
    # F1 first, then precision, then the more conservative/higher cutoff.
    return max(ranked, key=lambda item: (item[0], item[1], item[2]))[2:]


def _high_threshold(labels, scores, possible_threshold, precision_target=0.85):
    candidates = sorted(set(float(score) for score in scores if score >= possible_threshold))
    valid = []
    for threshold in candidates:
        metrics = classification_metrics(labels, scores, threshold)
        predicted = metrics["confusion_matrix"]["true_positive"] + metrics["confusion_matrix"]["false_positive"]
        if predicted >= 2 and metrics["precision"] >= precision_target:
            valid.append((metrics["recall"], threshold, metrics["precision"], predicted))
    if valid:
        recall, threshold, precision, count = max(valid, key=lambda row: (row[0], row[2], row[1]))
        return threshold, {"target_precision": precision_target, "target_met": True,
                           "observed_precision": precision, "predicted_count": count}
    threshold = max(candidates) if candidates else 1.0
    metrics = classification_metrics(labels, scores, threshold)
    count = metrics["confusion_matrix"]["true_positive"] + metrics["confusion_matrix"]["false_positive"]
    return threshold, {"target_precision": precision_target, "target_met": False,
                       "observed_precision": metrics["precision"], "predicted_count": count}


def run():
    pairs = load_demo_pairs()
    labels = [int(pair["label"]) for pair in pairs]
    scores = {"word_tfidf": [], "character_tfidf": [], "rapidfuzz_wratio": [], "hybrid": []}
    details = []
    for pair in pairs:
        a, b = ComplaintRecord(**pair["a"]), ComplaintRecord(**pair["b"])
        lexical = lexical_similarity(a.description, [b.description])[0]
        semantic = semantic_similarity(preprocess_text(a.description), preprocess_text(b.description))
        hybrid = _score_pair(a, b, lexical, semantic)["similarity_score"] / 100.0
        scores["word_tfidf"].append(lexical["word_similarity"])
        scores["character_tfidf"].append(lexical["character_similarity"])
        scores["rapidfuzz_wratio"].append(lexical["fuzzy_similarity"])
        scores["hybrid"].append(hybrid)
        details.append({"case": pair["case"], "ground_truth_duplicate": bool(pair["label"]),
                        "signals": lexical, "hybrid_score": round(hybrid * 100, 2),
                        "semantic_available": semantic is not None})

    selected, thresholds_by_model, results_by_model = {}, {}, {}
    for algorithm, values in scores.items():
        threshold, metric = _best_f1_threshold(labels, values)
        thresholds_by_model[algorithm] = round(threshold, 4)
        results_by_model[algorithm] = classification_metrics(labels, values, threshold)
    possible_threshold = thresholds_by_model["hybrid"]
    high_threshold, high_calibration = _high_threshold(labels, scores["hybrid"], possible_threshold)
    high_threshold = max(possible_threshold, high_threshold)

    semantic_used = any(item["semantic_available"] for item in details)
    output = {
        "status": "completed",
        "dataset_type": "manually_labeled_synthetic_demonstration_pairs",
        "dataset_description": "Fictional, manually labeled examples with synthetic test coordinates; not CityCare citizen data and not a holdout benchmark.",
        "pair_count": len(pairs),
        "positive_pair_count": sum(labels),
        "negative_pair_count": len(labels) - sum(labels),
        "evaluation_method": "Resubstitution on the manually labeled demonstration set; metrics validate implementation only and do not estimate real-world generalization.",
        "precision_context": "False duplicate recommendations can hide distinct civic issues if acted on without review; keep administrator review and do not auto-merge.",
        "recall_context": "Missed duplicates may cause repeated assignments; recall must be measured on representative labeled operational pairs before production tuning.",
        "semantic_embeddings": {"enabled": settings.semantic_enabled, "used_in_scores": semantic_used,
                                "note": ("Semantic embeddings contributed to these scores." if semantic_used else
                                         "Optional semantic model was unavailable or disabled during evaluation.")},
        "calibration": {"possible_threshold": round(possible_threshold, 4),
                        "high_threshold": round(high_threshold, 4), **high_calibration},
        "algorithms": results_by_model,
        "calibrated_baseline_thresholds": thresholds_by_model,
        "cases": details,
    }
    evaluation_dir = ROOT / "app" / "evaluation"
    (evaluation_dir / "results.json").write_text(json.dumps(output, indent=2, sort_keys=True) + "\n")
    calibration = {"dataset_type": output["dataset_type"],
                   "possible_threshold": round(possible_threshold, 4),
                   "high_threshold": round(high_threshold, 4),
                   "high_precision_calibration": high_calibration,
                   "method": "possible maximizes demonstration-set F1; high targets precision >= 0.85 with at least two predictions when attainable; otherwise uses most conservative candidate score."}
    (evaluation_dir / "calibration.json").write_text(json.dumps(calibration, indent=2) + "\n")
    print(json.dumps({"dataset_type": output["dataset_type"], "pair_count": len(pairs),
                      "calibration": output["calibration"], "algorithms": {
                          name: {key: value for key, value in metrics.items() if key != "precision_recall_curve" and key != "threshold_candidates"}
                          for name, metrics in results_by_model.items()}}, indent=2))


if __name__ == "__main__":
    run()
