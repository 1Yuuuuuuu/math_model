from __future__ import annotations

from typing import Any

import numpy as np

from cumcm_toolkit.evaluation.metrics import regression_metrics
from cumcm_toolkit.utils.numbers import ensure_finite, to_python_scalar


def constant_baseline(y: Any, *, strategy: str = "mean") -> dict[str, object]:
    values = np.asarray(y)
    if values.size == 0:
        raise ValueError("constant baseline requires non-empty input")
    if strategy == "mean":
        value: object = ensure_finite(float(np.mean(values)), "constant_baseline mean")
    elif strategy == "median":
        value = ensure_finite(float(np.median(values)), "constant_baseline median")
    elif strategy == "majority":
        unique, counts = np.unique(values, return_counts=True)
        value = to_python_scalar(unique[int(np.argmax(counts))])
    else:
        raise ValueError(f"unknown baseline strategy: {strategy}")
    return {"strategy": strategy, "value": value, "fitted": value}


def compare_to_baseline(
    y_true: Any, y_pred: Any, baseline_value: float, *, metric: str = "rmse"
) -> dict[str, object]:
    if metric != "rmse":
        raise ValueError(f"unsupported metric: {metric}")
    baseline_value = ensure_finite(baseline_value, "compare_to_baseline baseline_value")
    model_score = regression_metrics(y_true, y_pred)["rmse"]
    errors = np.asarray(y_true, dtype=float) - baseline_value
    if errors.size == 0:
        raise ValueError("compare_to_baseline requires non-empty input")
    if not np.isfinite(errors).all():
        raise ValueError("compare_to_baseline requires finite values")
    baseline_score = float(np.mean(errors**2)) ** 0.5
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
