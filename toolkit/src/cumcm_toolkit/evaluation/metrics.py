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
    if y_true.size == 0:
        raise ValueError("regression metrics require non-empty arrays")
    if not (np.isfinite(y_true).all() and np.isfinite(y_pred).all()):
        raise ValueError("regression metrics require finite values")
    errors = y_true - y_pred
    mse = float(np.mean(errors**2))
    return {
        "mse": round(mse, 6),
        "rmse": round(float(np.sqrt(mse)), 6),
        "mae": round(float(np.mean(np.abs(errors))), 6),
        "r2": round(float(r2_score(y_true, y_pred)), 6),
    }


def _infer_positive_label(y_true: Any, y_pred: Any) -> object:
    candidates = set(np.unique(y_true)) | set(np.unique(y_pred))
    preferred = [p for p in (1, "1", True, "true") if p in candidates]
    distinct = list(dict.fromkeys(preferred))  # 1 == True, so dedupe before counting
    if len(distinct) > 1:
        raise ValueError(f"ambiguous positive label: multiple candidates {distinct}")
    if distinct:
        return distinct[0]
    raise ValueError(f"cannot infer positive label from labels: {sorted(map(str, candidates))}")


def classification_metrics(
    y_true: Any, y_pred: Any, *, positive_label: object | None = None
) -> dict[str, float]:
    _check_lengths(y_true, y_pred)
    pos = positive_label if positive_label is not None else _infer_positive_label(y_true, y_pred)
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
    overlapping = [
        {key: row[key] for key in key_columns}
        for _, row in merged.sort_values(key_columns).iterrows()
    ]
    return {
        "overlap_rows": len(overlapping),
        "overlapping_keys": overlapping,
        "warning": f"train/test overlap on key columns: {len(overlapping)} rows" if overlapping else "",
    }


def detect_target_leakage(
    features: pd.DataFrame, target: pd.Series, *, tolerance: float = 1e-9
) -> list[str]:
    if len(features) != len(target):
        raise ValueError(f"length mismatch: features {len(features)} vs target {len(target)}")
    if not features.index.equals(target.index):
        raise ValueError("features and target must share the same index (no silent alignment)")
    leaked = []
    target_values = target.to_numpy(dtype=float)
    for column in features.columns:
        series = features[column]
        if not pd.api.types.is_numeric_dtype(series.dtype):
            continue
        values = series.to_numpy(dtype=float)
        if np.isnan(values).any() or np.isnan(target_values).any():
            continue
        corr = float(np.corrcoef(values, target_values)[0, 1])
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
