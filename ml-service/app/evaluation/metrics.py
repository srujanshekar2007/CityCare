"""Statistical metrics for reproducible labeled-pair evaluation."""

from typing import List

import numpy as np
import pandas as pd
from sklearn.metrics import (accuracy_score, confusion_matrix, precision_recall_curve,
                             precision_score, recall_score, f1_score)


def classification_metrics(labels: List[int], scores: List[float], threshold: float) -> dict:
    y_true = np.asarray(labels, dtype=int)
    y_score = np.asarray(scores, dtype=float)
    y_pred = (y_score >= threshold).astype(int)
    tn, fp, fn, tp = confusion_matrix(y_true, y_pred, labels=[0, 1]).ravel().tolist()
    precision, recall, curve_thresholds = precision_recall_curve(y_true, y_score)
    return {
        "threshold": round(float(threshold), 4),
        "precision": round(float(precision_score(y_true, y_pred, zero_division=0)), 4),
        "recall": round(float(recall_score(y_true, y_pred, zero_division=0)), 4),
        "f1_score": round(float(f1_score(y_true, y_pred, zero_division=0)), 4),
        "accuracy": round(float(accuracy_score(y_true, y_pred)), 4),
        "false_positive_rate": round(float(fp / (fp + tn)), 4) if fp + tn else None,
        "false_negative_rate": round(float(fn / (fn + tp)), 4) if fn + tp else None,
        "confusion_matrix": {"true_negative": tn, "false_positive": fp,
                             "false_negative": fn, "true_positive": tp},
        "precision_recall_curve": [
            {"recall": round(float(r), 4), "precision": round(float(p), 4)}
            for p, r in zip(precision, recall)
        ],
        "threshold_candidates": [round(float(value), 4) for value in curve_thresholds],
    }


def duration_summary(days: List[float]) -> dict:
    if not days:
        return {"count": 0, "mean": None, "median": None, "minimum": None, "maximum": None,
                "standard_deviation": None, "p25": None, "p75": None, "interquartile_range": None}
    values = np.asarray(pd.Series(days, dtype="float64").dropna(), dtype=float)
    q25, median, q75 = np.percentile(values, [25, 50, 75]).tolist()
    return {"count": int(values.size), "mean": round(float(values.mean()), 3),
            "median": round(float(median), 3), "minimum": round(float(values.min()), 3),
            "maximum": round(float(values.max()), 3),
            "standard_deviation": round(float(values.std(ddof=1)), 3) if values.size > 1 else None,
            "p25": round(float(q25), 3), "p75": round(float(q75), 3),
            "interquartile_range": round(float(q75 - q25), 3)}
