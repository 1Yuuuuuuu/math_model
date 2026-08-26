"""Validated, reproducible data-processing model executors."""

from __future__ import annotations

from collections.abc import Mapping
from numbers import Integral

import numpy as np
from scipy.interpolate import CubicSpline, PchipInterpolator, interp1d
from sklearn.decomposition import PCA
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler

from .base import bounded_integer, finite_float, required_field, string_enum


_NORMALIZATION_METHODS = frozenset({"minmax", "zscore", "robust"})
_INTERPOLATION_METHODS = frozenset({"linear", "nearest", "cubic", "pchip"})
_ANOMALY_METHODS = frozenset({"iqr", "zscore", "isolation-forest"})
_MISSING_POLICIES = frozenset({"reject", "drop-rows", "column-mean"})


def _numeric_array_allow_nan(
    payload: Mapping[str, object], field: str, *, ndim: int, min_size: int = 1
) -> np.ndarray:
    """Read a real numeric array while reserving NaN for explicit missing-data handling."""
    value = required_field(payload, field)
    if isinstance(value, (str, bytes, bytearray, Mapping)):
        raise ValueError(f"{field}: must be a rectangular real numeric array")
    try:
        array = np.asarray(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field}: must be a rectangular real numeric array") from exc
    if array.ndim != ndim or array.size < min_size:
        raise ValueError(f"{field}: must have exactly {ndim} dimension(s) and at least {min_size} value(s)")
    if (
        not np.issubdtype(array.dtype, np.number)
        or np.issubdtype(array.dtype, np.bool_)
        or np.issubdtype(array.dtype, np.complexfloating)
    ):
        raise ValueError(f"{field}: must use a real numeric dtype")
    array = array.astype(float, copy=False)
    if np.any(np.isinf(array)):
        raise ValueError(f"{field}: infinity is not a missing value and is not allowed")
    return array


def _missing_policy(payload: Mapping[str, object]) -> str:
    if "missing_policy" not in payload:
        return "reject"
    return string_enum(payload, "missing_policy", _MISSING_POLICIES)


def _reject_unknown_fields(payload: Mapping[str, object], allowed: set[str]) -> None:
    """Fail closed when a public executor receives an unrecognized payload key."""
    unknown = sorted(set(payload) - allowed)
    if unknown:
        raise ValueError(f"{unknown[0]}: is not a supported payload field")


def _apply_missing_policy(
    values: np.ndarray, *, policy: str, field: str
) -> tuple[np.ndarray, list[int], list[int], list[int], list[int]]:
    """Apply row-wise missing treatment and retain original row indexes for the envelope."""
    missing_rows = np.flatnonzero(np.isnan(values).any(axis=1)).astype(int).tolist()
    source_rows = list(range(values.shape[0]))
    if not missing_rows:
        return values, source_rows, [], [], []
    if policy == "reject":
        raise ValueError(
            f"{field}: contains missing values; set missing_policy to drop-rows or column-mean"
        )
    if policy == "drop-rows":
        keep = ~np.isnan(values).any(axis=1)
        processed = values[keep]
        if processed.shape[0] == 0:
            raise ValueError(f"{field}: drop-rows would remove every row")
        return processed, np.flatnonzero(keep).astype(int).tolist(), missing_rows, missing_rows, []

    processed = values.copy()
    for column in range(processed.shape[1]):
        column_values = processed[:, column]
        present = column_values[~np.isnan(column_values)]
        if present.size == 0:
            raise ValueError(f"{field}: column {column} has no observed value for column-mean")
        column_values[np.isnan(column_values)] = float(np.mean(present))
    return processed, source_rows, missing_rows, [], missing_rows


def _input_summary(
    *, original_rows: int, columns: int, source_rows: list[int], missing_rows: list[int], dropped_rows: list[int], filled_rows: list[int]
) -> dict[str, object]:
    return {
        "rows": original_rows,
        "columns": columns,
        "rows_used": len(source_rows),
        "source_rows": source_rows,
        "missing_rows": missing_rows,
        "missing_row_count": len(missing_rows),
        "dropped_rows": dropped_rows,
        "dropped_row_count": len(dropped_rows),
        "filled_rows": filled_rows,
        "filled_row_count": len(filled_rows),
    }


def _selected_columns(payload: Mapping[str, object], column_count: int) -> list[int]:
    value = payload.get("columns")
    if value is None:
        return list(range(column_count))
    if not isinstance(value, (list, tuple)):
        raise ValueError("columns: must be an array of unique column indexes")
    selected: list[int] = []
    for index in value:
        if isinstance(index, bool) or not isinstance(index, Integral):
            raise ValueError("columns: each index must be an integer")
        normalized = int(index)
        if normalized < 0 or normalized >= column_count:
            raise ValueError("columns: index is out of range")
        if normalized in selected:
            raise ValueError("columns: indexes must be unique")
        selected.append(normalized)
    if not selected:
        raise ValueError("columns: must select at least one column")
    return selected


def execute_normalization(payload: Mapping[str, object]) -> Mapping[str, object]:
    """Normalize selected columns with finite statistics and explicit missing-data handling."""
    _reject_unknown_fields(payload, {"matrix", "method", "columns", "missing_policy"})
    matrix = _numeric_array_allow_nan(payload, "matrix", ndim=2)
    method = string_enum(payload, "method", _NORMALIZATION_METHODS) if "method" in payload else "minmax"
    policy = _missing_policy(payload)
    processed, source_rows, missing_rows, dropped_rows, filled_rows = _apply_missing_policy(
        matrix, policy=policy, field="matrix"
    )
    selected = _selected_columns(payload, processed.shape[1])
    transformed = processed.copy()
    selected_values = processed[:, selected]
    warnings: list[str] = []
    result: dict[str, object] = {"transformed": transformed.tolist()}

    if method == "minmax":
        minimum = np.min(selected_values, axis=0)
        scale = np.max(selected_values, axis=0) - minimum
        normalized = np.zeros_like(selected_values)
        nonzero = scale != 0
        normalized[:, nonzero] = (selected_values[:, nonzero] - minimum[nonzero]) / scale[nonzero]
        result.update({"min": minimum.tolist(), "range": scale.tolist()})
    elif method == "zscore":
        minimum = np.mean(selected_values, axis=0)
        scale = np.std(selected_values, axis=0, ddof=0)
        normalized = np.zeros_like(selected_values)
        nonzero = scale != 0
        normalized[:, nonzero] = (selected_values[:, nonzero] - minimum[nonzero]) / scale[nonzero]
        result.update({"mean": minimum.tolist(), "scale": scale.tolist()})
    else:
        minimum = np.median(selected_values, axis=0)
        q1, q3 = np.percentile(selected_values, [25, 75], axis=0)
        scale = q3 - q1
        normalized = np.zeros_like(selected_values)
        nonzero = scale != 0
        normalized[:, nonzero] = (selected_values[:, nonzero] - minimum[nonzero]) / scale[nonzero]
        result.update({"median": minimum.tolist(), "iqr": scale.tolist()})

    for selected_offset, column in enumerate(selected):
        if not nonzero[selected_offset]:
            warnings.append(f"constant column {column} was transformed to 0")
    transformed[:, selected] = normalized
    result["transformed"] = transformed.tolist()
    return {
        "parameters": {"method": method, "columns": selected, "missing_policy": policy},
        "input_summary": _input_summary(
            original_rows=matrix.shape[0], columns=matrix.shape[1], source_rows=source_rows,
            missing_rows=missing_rows, dropped_rows=dropped_rows, filled_rows=filled_rows,
        ),
        "result": result,
        "diagnostics": {"method": method, "selected_columns": selected},
        "warnings": warnings,
        "seed": None,
    }


def execute_interpolation(payload: Mapping[str, object]) -> Mapping[str, object]:
    """Interpolate one-dimensional paired data without silently sorting or extrapolating."""
    _reject_unknown_fields(
        payload, {"x", "y", "new_x", "method", "extrapolation", "missing_policy"}
    )
    x = _numeric_array_allow_nan(payload, "x", ndim=1)
    y = _numeric_array_allow_nan(payload, "y", ndim=1)
    new_x = _numeric_array_allow_nan(payload, "new_x", ndim=1)
    if np.isnan(new_x).any():
        raise ValueError("new_x: missing values are not allowed")
    if x.size != y.size:
        raise ValueError("x and y: must have equal lengths")
    method = string_enum(payload, "method", _INTERPOLATION_METHODS) if "method" in payload else "linear"
    policy = _missing_policy(payload)
    paired, source_rows, missing_rows, dropped_rows, filled_rows = _apply_missing_policy(
        np.column_stack((x, y)), policy=policy, field="x/y"
    )
    x_processed, y_processed = paired[:, 0], paired[:, 1]
    required_nodes = 4 if method == "cubic" else 2
    if x_processed.size < required_nodes:
        raise ValueError(f"{method}: requires at least {required_nodes} paired sample(s)")
    if not np.all(np.diff(x_processed) > 0):
        raise ValueError("x: values must be strictly increasing with no duplicates")

    extrapolation = string_enum(payload, "extrapolation", {"reject", "allow"}) if "extrapolation" in payload else "reject"
    extrapolated = ((new_x < x_processed[0]) | (new_x > x_processed[-1]))
    if extrapolation == "reject" and np.any(extrapolated):
        raise ValueError("extrapolation: values outside the x domain require extrapolation='allow'")

    if method in {"linear", "nearest"}:
        function = interp1d(
            x_processed, y_processed, kind=method, bounds_error=False,
            fill_value="extrapolate" if extrapolation == "allow" else np.nan,
        )
    elif method == "cubic":
        function = CubicSpline(x_processed, y_processed, extrapolate=extrapolation == "allow")
    else:
        function = PchipInterpolator(x_processed, y_processed, extrapolate=extrapolation == "allow")
    values = np.asarray(function(new_x), dtype=float)
    if values.shape != new_x.shape or not np.all(np.isfinite(values)):
        raise ValueError("interpolation produced non-finite values")
    return {
        "parameters": {
            "method": method,
            "extrapolation": extrapolation,
            "missing_policy": policy,
        },
        "input_summary": {
            **_input_summary(
                original_rows=x.size, columns=2, source_rows=source_rows,
                missing_rows=missing_rows, dropped_rows=dropped_rows, filled_rows=filled_rows,
            ),
            "new_x_count": int(new_x.size),
        },
        "result": {"values": values.tolist(), "extrapolated": extrapolated.tolist()},
        "diagnostics": {"domain": [float(x_processed[0]), float(x_processed[-1])], "nodes": int(x_processed.size)},
        "warnings": [],
        "seed": None,
    }


def execute_pca(payload: Mapping[str, object]) -> Mapping[str, object]:
    """Fit a deterministic PCA on an explicitly standardized or raw numeric matrix.

    ``components`` and ``loadings`` each contain one principal component per row.
    Each loading equals its axis coefficient times the square root of that component's
    explained variance.
    """
    _reject_unknown_fields(payload, {"matrix", "components", "standardize", "missing_policy"})
    matrix = _numeric_array_allow_nan(payload, "matrix", ndim=2)
    policy = _missing_policy(payload)
    processed, source_rows, missing_rows, dropped_rows, filled_rows = _apply_missing_policy(
        matrix, policy=policy, field="matrix"
    )
    components = bounded_integer(
        payload, "components", minimum=1, maximum=min(processed.shape)
    )
    standardize = required_field(payload, "standardize")
    if type(standardize) is not bool:
        raise ValueError("standardize: must be a boolean")
    if processed.shape[0] < 2:
        raise ValueError("pca: explained variance requires at least 2 samples")

    warnings: list[str] = []
    standardization: dict[str, object]
    if standardize:
        scaler = StandardScaler()
        fitted = np.asarray(scaler.fit_transform(processed), dtype=float)
        standardization = {
            "applied": True,
            "mean": np.asarray(scaler.mean_, dtype=float).tolist(),
            "scale": np.asarray(scaler.scale_, dtype=float).tolist(),
        }
        constant_columns = np.flatnonzero(np.asarray(scaler.var_, dtype=float) == 0)
        for column in constant_columns.astype(int):
            warnings.append(f"constant column {column} was standardized to 0")
    else:
        fitted = processed.copy()
        standardization = {"applied": False}

    if not np.all(np.isfinite(fitted)):
        raise ValueError("pca: preprocessing produced non-finite values")
    total_variance = float(np.sum(np.var(fitted, axis=0, ddof=0)))
    if not np.isfinite(total_variance) or total_variance <= 0:
        raise ValueError("pca: total variance must be finite and positive")

    estimator = PCA(n_components=components, svd_solver="full")
    transformed = np.asarray(estimator.fit_transform(fitted), dtype=float)
    axes = np.asarray(estimator.components_, dtype=float)
    explained_variance = np.asarray(estimator.explained_variance_, dtype=float)
    explained_ratio = np.asarray(estimator.explained_variance_ratio_, dtype=float)
    mean = np.asarray(estimator.mean_, dtype=float)
    loadings = axes * np.sqrt(explained_variance)[:, np.newaxis]
    cumulative_ratio = np.minimum(np.cumsum(explained_ratio), 1.0)
    arrays = (transformed, axes, explained_variance, explained_ratio, cumulative_ratio, mean, loadings)
    if any(not np.all(np.isfinite(values)) for values in arrays):
        raise ValueError("pca: fit produced non-finite statistics")

    return {
        "parameters": {
            "components": components,
            "standardize": standardize,
            "missing_policy": policy,
        },
        "input_summary": _input_summary(
            original_rows=matrix.shape[0], columns=matrix.shape[1], source_rows=source_rows,
            missing_rows=missing_rows, dropped_rows=dropped_rows, filled_rows=filled_rows,
        ),
        "result": {
            "transformed": transformed.tolist(),
            "components": axes.tolist(),
            "loadings": loadings.tolist(),
            "explained_variance": explained_variance.tolist(),
            "explained_variance_ratio": explained_ratio.tolist(),
            "cumulative_explained_variance_ratio": cumulative_ratio.tolist(),
            "mean": mean.tolist(),
            "standardization": standardization,
        },
        "diagnostics": {
            "components_definition": "rows are unit principal axes in fitted feature space",
            "loadings_definition": "rows are components in fitted feature space; axis coefficient times sqrt(explained_variance)",
        },
        "warnings": warnings,
        "seed": None,
    }


def _reject_irrelevant_anomaly_parameters(payload: Mapping[str, object], method: str) -> None:
    allowed = {
        "iqr": {"matrix", "method", "multiplier", "missing_policy"},
        "zscore": {"matrix", "method", "threshold", "missing_policy"},
        "isolation-forest": {"matrix", "method", "contamination", "seed", "missing_policy"},
    }[method]
    if "random_state" in payload:
        raise ValueError("random_state: use seed instead; random_state is not accepted")
    _reject_unknown_fields(payload, allowed)


def execute_anomaly_detection(payload: Mapping[str, object]) -> Mapping[str, object]:
    """Detect row anomalies using robust rules or a fixed-seed isolation forest."""
    matrix = _numeric_array_allow_nan(payload, "matrix", ndim=2)
    method = string_enum(payload, "method", _ANOMALY_METHODS) if "method" in payload else "iqr"
    _reject_irrelevant_anomaly_parameters(payload, method)
    policy = _missing_policy(payload)
    processed, source_rows, missing_rows, dropped_rows, filled_rows = _apply_missing_policy(
        matrix, policy=policy, field="matrix"
    )
    warnings: list[str] = []
    parameters: dict[str, object] = {"method": method, "missing_policy": policy}
    diagnostics: dict[str, object]
    seed: int | None = None

    if method == "iqr":
        multiplier = finite_float(payload, "multiplier", minimum=np.nextafter(0.0, 1.0)) if "multiplier" in payload else 1.5
        q1, q3 = np.percentile(processed, [25, 75], axis=0)
        iqr = q3 - q1
        lower, upper = q1 - multiplier * iqr, q3 + multiplier * iqr
        mask = (processed < lower) | (processed > upper)
        for column in np.flatnonzero(iqr == 0):
            warnings.append(f"zero IQR column {int(column)} was evaluated without division")
        parameters["multiplier"] = multiplier
        diagnostics = {"q1": q1.tolist(), "q3": q3.tolist(), "iqr": iqr.tolist(), "lower": lower.tolist(), "upper": upper.tolist()}
    elif method == "zscore":
        threshold = finite_float(payload, "threshold", minimum=np.nextafter(0.0, 1.0)) if "threshold" in payload else 3.0
        mean = np.mean(processed, axis=0)
        scale = np.std(processed, axis=0, ddof=0)
        zscores = np.zeros_like(processed)
        nonzero = scale != 0
        zscores[:, nonzero] = (processed[:, nonzero] - mean[nonzero]) / scale[nonzero]
        mask = np.abs(zscores) > threshold
        for column in np.flatnonzero(~nonzero):
            warnings.append(f"zero scale column {int(column)} was evaluated as non-anomalous")
        parameters["threshold"] = threshold
        diagnostics = {"mean": mean.tolist(), "scale": scale.tolist(), "threshold": threshold, "zscores": zscores.tolist()}
    else:
        contamination = finite_float(payload, "contamination", minimum=np.nextafter(0.0, 1.0), maximum=0.5) if "contamination" in payload else 0.1
        if "seed" in payload:
            seed = bounded_integer(payload, "seed", minimum=0, maximum=2**32 - 1)
        else:
            seed = 0
        forest = IsolationForest(contamination=contamination, random_state=seed)
        labels = forest.fit_predict(processed) == -1
        scores = np.asarray(forest.score_samples(processed), dtype=float)
        if not np.all(np.isfinite(scores)):
            raise ValueError("isolation-forest produced non-finite scores")
        mask = np.repeat(labels[:, np.newaxis], processed.shape[1], axis=1)
        parameters.update({"contamination": contamination, "seed": seed})
        diagnostics = {"contamination": contamination, "scores": scores.tolist(), "score_orientation": "higher is more normal"}

    row_mask = np.any(mask, axis=1)
    anomaly_indices = [source_rows[index] for index in np.flatnonzero(row_mask).astype(int)]
    result: dict[str, object] = {
        "mask": row_mask.tolist(),
        "anomaly_indices": anomaly_indices,
        "count": len(anomaly_indices),
    }
    if method != "isolation-forest":
        result["cell_mask"] = mask.tolist()
    return {
        "parameters": parameters,
        "input_summary": _input_summary(
            original_rows=matrix.shape[0], columns=matrix.shape[1], source_rows=source_rows,
            missing_rows=missing_rows, dropped_rows=dropped_rows, filled_rows=filled_rows,
        ),
        "result": result,
        "diagnostics": diagnostics,
        "warnings": warnings,
        "seed": seed,
    }
