"""Deterministic multi-criteria evaluation model executors."""

from __future__ import annotations

from collections.abc import Mapping

import numpy as np

from .base import numeric_array, required_field


_DIRECTIONS = frozenset({"benefit", "cost"})
_WEIGHT_SUM_REL_TOLERANCE = 1e-9
_WEIGHT_SUM_ABS_TOLERANCE = 1e-12


def _matrix_and_criteria(payload: Mapping[str, object]) -> tuple[np.ndarray, list[str]]:
    """Validate and convert the common decision-matrix input."""
    matrix = numeric_array(payload, "matrix", ndim=2).astype(float, copy=False)
    if not np.all(np.isfinite(matrix)):
        raise ValueError("matrix: must contain only finite values")

    criteria_value = required_field(payload, "criteria")
    if not isinstance(criteria_value, (list, tuple)):
        raise ValueError("criteria: must be an array of benefit/cost directions")
    criteria = list(criteria_value)
    if len(criteria) != matrix.shape[1]:
        raise ValueError("criteria: length must match the number of matrix columns")
    if any(not isinstance(direction, str) or direction not in _DIRECTIONS for direction in criteria):
        raise ValueError("criteria: each direction must be benefit or cost")
    return matrix, criteria


def _topsis_weights(payload: Mapping[str, object], columns: int) -> np.ndarray:
    """Return validated TOPSIS weights, defaulting to equal weights."""
    if "weights" not in payload:
        return np.full(columns, 1.0 / columns)

    weights = numeric_array(payload, "weights", ndim=1).astype(float, copy=False)
    if weights.size != columns:
        raise ValueError("weights: length must match the number of matrix columns")
    if np.any(weights < 0):
        raise ValueError("weights: must be non-negative")
    if np.any(weights > 1.0 + _WEIGHT_SUM_ABS_TOLERANCE):
        raise ValueError("weights: must sum to 1")
    total = float(weights.sum())
    if not np.isfinite(total) or not np.isclose(
        total,
        1.0,
        rtol=_WEIGHT_SUM_REL_TOLERANCE,
        atol=_WEIGHT_SUM_ABS_TOLERANCE,
    ):
        raise ValueError("weights: must sum to 1")
    return weights


def _stable_descending_rank(values: np.ndarray) -> list[int]:
    """Return descending values with the original index as a stable tie-breaker."""
    indices = np.arange(values.size)
    return np.lexsort((indices, -values)).tolist()


def _raw_result(
    *,
    parameters: dict[str, object],
    rows: int,
    columns: int,
    result: dict[str, object],
    diagnostics: dict[str, object],
    warnings: list[str] | None = None,
) -> dict[str, object]:
    """Build the executor-level portion of the common execution result contract."""
    return {
        "parameters": parameters,
        "input_summary": {"rows": rows, "columns": columns},
        "result": result,
        "diagnostics": diagnostics,
        "warnings": [] if warnings is None else warnings,
        "seed": None,
    }


def execute_topsis(payload: Mapping[str, object]) -> dict[str, object]:
    """Rank alternatives using weighted vector-normalized TOPSIS."""
    matrix, criteria = _matrix_and_criteria(payload)
    weights = _topsis_weights(payload, matrix.shape[1])

    scales = np.abs(matrix).max(axis=0)
    if np.any(scales == 0) or np.any(matrix.min(axis=0) == matrix.max(axis=0)):
        raise ValueError("matrix: TOPSIS requires non-constant, nonzero-norm criterion columns")
    scaled_matrix = matrix / scales
    scaled_norms = np.linalg.norm(scaled_matrix, axis=0)
    weighted = (scaled_matrix / scaled_norms) * weights

    positive_ideal = np.empty(matrix.shape[1])
    negative_ideal = np.empty(matrix.shape[1])
    for column, direction in enumerate(criteria):
        column_values = weighted[:, column]
        if direction == "benefit":
            positive_ideal[column] = column_values.max()
            negative_ideal[column] = column_values.min()
        else:
            positive_ideal[column] = column_values.min()
            negative_ideal[column] = column_values.max()

    distance_to_positive = np.linalg.norm(weighted - positive_ideal, axis=1)
    distance_to_negative = np.linalg.norm(weighted - negative_ideal, axis=1)
    denominator = distance_to_positive + distance_to_negative
    if np.any(denominator == 0):
        raise ValueError("matrix: TOPSIS closeness is undefined when ideal distances coincide")
    closeness = distance_to_negative / denominator
    if not np.all(np.isfinite(closeness)):
        raise ValueError("matrix: TOPSIS produced non-finite closeness values")

    return _raw_result(
        parameters={"criteria": criteria, "weights": weights.tolist()},
        rows=matrix.shape[0],
        columns=matrix.shape[1],
        result={"closeness": closeness.tolist(), "ranking": _stable_descending_rank(closeness)},
        diagnostics={
            "positive_ideal": positive_ideal.tolist(),
            "negative_ideal": negative_ideal.tolist(),
            "distance_to_positive": distance_to_positive.tolist(),
            "distance_to_negative": distance_to_negative.tolist(),
        },
    )


def execute_entropy_weight(payload: Mapping[str, object]) -> dict[str, object]:
    """Derive objective entropy weights and rank alternatives by weighted scores."""
    matrix, criteria = _matrix_and_criteria(payload)
    rows, columns = matrix.shape
    if rows < 2:
        raise ValueError("matrix: entropy weight requires at least two alternatives")

    minima = matrix.min(axis=0)
    maxima = matrix.max(axis=0)
    with np.errstate(over="ignore"):
        ranges = maxima - minima
    if not np.all(np.isfinite(ranges)):
        raise ValueError("matrix: criterion range is too large to normalize safely")
    constant_columns = ranges == 0
    oriented = np.zeros_like(matrix, dtype=float)
    variable_columns = ~constant_columns
    for column in np.flatnonzero(variable_columns):
        if criteria[column] == "benefit":
            oriented[:, column] = (matrix[:, column] - minima[column]) / ranges[column]
        else:
            oriented[:, column] = (maxima[column] - matrix[:, column]) / ranges[column]

    proportions = np.zeros_like(oriented, dtype=float)
    column_totals = oriented.sum(axis=0)
    proportions[:, variable_columns] = (
        oriented[:, variable_columns] / column_totals[variable_columns]
    )
    entropy_terms = np.zeros_like(proportions, dtype=float)
    positive = proportions > 0
    entropy_terms[positive] = proportions[positive] * np.log(proportions[positive])
    entropies = -entropy_terms.sum(axis=0) / np.log(rows)
    entropies[constant_columns] = 1.0
    divergence = np.maximum(0.0, 1.0 - entropies)
    divergence[constant_columns] = 0.0
    total_divergence = float(divergence.sum())
    if not np.isfinite(total_divergence) or total_divergence == 0:
        raise ValueError("matrix: all criteria have zero information")
    weights = divergence / total_divergence
    scores = oriented @ weights
    if not np.all(np.isfinite(weights)) or not np.all(np.isfinite(scores)):
        raise ValueError("matrix: entropy weight produced non-finite results")

    warnings = []
    if np.any(constant_columns):
        warnings.append("one or more criteria have zero information and weight 0")
    return _raw_result(
        parameters={"criteria": criteria},
        rows=rows,
        columns=columns,
        result={
            "weights": weights.tolist(),
            "scores": scores.tolist(),
            "ranking": _stable_descending_rank(scores),
        },
        diagnostics={
            "entropy": entropies.tolist(),
            "divergence": divergence.tolist(),
            "constant_columns": constant_columns.tolist(),
        },
        warnings=warnings,
    )
