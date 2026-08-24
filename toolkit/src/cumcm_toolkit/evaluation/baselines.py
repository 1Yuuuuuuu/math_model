from __future__ import annotations

from typing import Any

import numpy as np

from cumcm_toolkit.evaluation.metrics import regression_metrics


def constant_baseline(y: Any, *, strategy: str = "mean") -> dict[str, object]:
    values = np.asarray(y)
    if strategy == "mean":
        value: object = float(np.mean(values))
    elif strategy == "median":
        value = float(np.median(values))
    elif strategy == "majority":
        unique, counts = np.unique(values, return_counts=True)
        value = unique[int(np.argmax(counts))]
    else:
        raise ValueError(f"unknown baseline strategy: {strategy}")
    return {"strategy": strategy, "value": value, "fitted": value}


def compare_to_baseline(
    y_true: Any, y_pred: Any, baseline_value: float, *, metric: str = "rmse"
) -> dict[str, object]:
    if metric != "rmse":
        raise ValueError(f"unsupported metric: {metric}")
    model_score = regression_metrics(y_true, y_pred)["rmse"]
    baseline_score = float(np.mean((np.asarray(y_true, dtype=float) - baseline_value) ** 2)) ** 0.5
    improvement: float | None
    if baseline_score == 0:
        improvement = None
    else:
        improvement = round((baseline_score - model_score) / baseline_score, 6)
    return {
        "metric": metric,
        "model_score": model_score,
        "baseline_score": round(baseline_score, 6),
        "improvement": improvement,
    }
