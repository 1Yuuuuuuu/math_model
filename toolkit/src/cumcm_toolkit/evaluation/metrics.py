from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score, f1_score, precision_score, r2_score, recall_score


def _check_lengths(y_true: Any, y_pred: Any) -> None:
    if len(y_true) != len(y_pred):
        raise ValueError(f"length mismatch: y_true {len(y_true)} vs y_pred {len(y_pred)}")


def regression_metrics(y_true: Any, y_pred: Any) -> dict[str, float]:
    _check_lengths(y_true, y_pred)
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)
    errors = y_true - y_pred
    mse = float(np.mean(errors**2))
    return {
        "mse": round(mse, 6),
        "rmse": round(float(np.sqrt(mse)), 6),
        "mae": round(float(np.mean(np.abs(errors))), 6),
        "r2": round(float(r2_score(y_true, y_pred)), 6),
    }


def classification_metrics(
    y_true: Any, y_pred: Any, *, positive_label: str | None = None
) -> dict[str, float]:
    _check_lengths(y_true, y_pred)
    pos = positive_label or "1"
    return {
        "accuracy": round(float(accuracy_score(y_true, y_pred)), 6),
        "precision": round(float(precision_score(y_true, y_pred, pos_label=pos, zero_division=0)), 6),
        "recall": round(float(recall_score(y_true, y_pred, pos_label=pos, zero_division=0)), 6),
        "f1": round(float(f1_score(y_true, y_pred, pos_label=pos, zero_division=0)), 6),
    }


def detect_improper_split(
    train: pd.DataFrame, test: pd.DataFrame, key_columns: list[str]
) -> dict[str, object]:
    missing = [c for c in key_columns if c not in train.columns or c not in test.columns]
    if missing:
        raise ValueError(f"key columns missing from split: {missing}")
    train_keys = train[key_columns].drop_duplicates()
    test_keys = test[key_columns].drop_duplicates()
    merged = train_keys.merge(test_keys, on=key_columns)
    overlapping = merged.sort_values(key_columns[0])[key_columns[0]].tolist()
    return {
        "overlap_rows": len(overlapping),
        "overlapping_keys": overlapping,
        "warning": f"train/test overlap on key columns: {len(overlapping)} rows" if overlapping else "",
    }


def detect_target_leakage(
    features: pd.DataFrame, target: pd.Series, *, tolerance: float = 1e-9
) -> list[str]:
    leaked = []
    for column in features.columns:
        series = features[column]
        if not pd.api.types.is_numeric_dtype(series.dtype):
            continue
        corr = float(pd.Series(series).corr(pd.Series(target)))
        if np.isnan(corr):
            continue
        if abs(corr) >= 1.0 - tolerance:
            leaked.append(str(column))
    return sorted(leaked)


def check_data_leakage(
    train: pd.DataFrame,
    test: pd.DataFrame,
    target: pd.Series,
    *,
    key_columns: list[str],
    tolerance: float = 1e-9,
) -> dict[str, object]:
    split = detect_improper_split(train, test, key_columns)
    features = train.drop(columns=[c for c in key_columns if c in train.columns], errors="ignore")
    leak = detect_target_leakage(features, target, tolerance=tolerance)
    warnings: list[str] = []
    if split["overlap_rows"]:
        warnings.append(split["warning"])
    if leak:
        warnings.append(f"target leakage in features: {leak}")
    return {"improper_split": split, "target_leakage": leak, "warnings": warnings}
