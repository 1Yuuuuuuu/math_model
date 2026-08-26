"""Validated statistical model executors with finite JSON results."""

from __future__ import annotations

import math
import warnings
from collections.abc import Mapping

import numpy as np
from scipy import stats

from .base import required_field, string_enum


_CORRELATION_METHODS = frozenset({"pearson", "spearman", "kendall"})
_CORRELATION_MISSING_POLICIES = frozenset({"reject", "pairwise"})
_CONFIDENCE_METHODS = frozenset({"mean-t", "proportion-wilson"})


def _reject_unknown_fields(payload: Mapping[str, object], allowed: set[str]) -> None:
    """Fail closed when a public statistical executor receives an unknown key."""
    unknown = sorted(set(payload) - allowed)
    if unknown:
        raise ValueError(f"{unknown[0]}: is not a supported payload field")


def _numeric_array_allow_nan(
    payload: Mapping[str, object], field: str, *, ndim: int
) -> np.ndarray:
    """Read a real numeric array, allowing NaN only for explicit pairwise filtering."""
    value = required_field(payload, field)
    if isinstance(value, (str, bytes, bytearray, Mapping)):
        raise ValueError(f"{field}: must be a rectangular real numeric array")
    try:
        array = np.asarray(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f"{field}: must be a rectangular real numeric array") from exc
    if array.ndim != ndim or array.size == 0:
        raise ValueError(f"{field}: must have exactly {ndim} dimension(s) and contain values")
    if (
        not np.issubdtype(array.dtype, np.number)
        or np.issubdtype(array.dtype, np.bool_)
        or np.issubdtype(array.dtype, np.complexfloating)
    ):
        raise ValueError(f"{field}: must use a real numeric dtype")
    try:
        values = array.astype(float, copy=False)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f"{field}: must contain finite real numbers or NaN") from exc
    if np.any(np.isinf(values)):
        raise ValueError(f"{field}: infinity is not a missing value and is not allowed")
    return values


def _correlation_function(method: str):
    return {
        "pearson": stats.pearsonr,
        "spearman": stats.spearmanr,
        "kendall": stats.kendalltau,
    }[method]


def _pair_correlation(x: np.ndarray, y: np.ndarray, method: str) -> tuple[float | None, float | None, str | None]:
    """Return one finite correlation pair or a JSON-safe reason for it being undefined."""
    if x.size < 2:
        return None, None, "insufficient_samples"
    if np.all(x == x[0]) or np.all(y == y[0]):
        return None, None, "constant_input"
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        calculated = _correlation_function(method)(x, y)
    try:
        coefficient = float(calculated.statistic)
        p_value = float(calculated.pvalue)
    except (AttributeError, TypeError, ValueError, OverflowError):
        return None, None, "non_finite_output"
    if not math.isfinite(coefficient) or not math.isfinite(p_value):
        return None, None, "non_finite_output"
    if coefficient < -1.0 or coefficient > 1.0:
        return None, None, "invalid_coefficient"
    return coefficient, min(1.0, max(0.0, p_value)), None


def _correlation_policy(payload: Mapping[str, object]) -> str:
    if "missing_policy" not in payload:
        return "reject"
    return string_enum(payload, "missing_policy", _CORRELATION_MISSING_POLICIES)


def execute_correlation(payload: Mapping[str, object]) -> Mapping[str, object]:
    """Calculate pair or variable-matrix correlations without leaking undefined floats."""
    _reject_unknown_fields(payload, {"x", "y", "matrix", "method", "missing_policy"})
    method = string_enum(payload, "method", _CORRELATION_METHODS)
    policy = _correlation_policy(payload)
    has_x, has_y, has_matrix = "x" in payload, "y" in payload, "matrix" in payload
    if has_matrix and (has_x or has_y):
        raise ValueError("matrix: cannot be combined with x or y")
    if has_x != has_y:
        raise ValueError("x and y: must be provided together")
    if not has_matrix and not has_x:
        raise ValueError("x and y: or matrix is required")

    if has_x:
        x = _numeric_array_allow_nan(payload, "x", ndim=1)
        y = _numeric_array_allow_nan(payload, "y", ndim=1)
        if x.size != y.size:
            raise ValueError("x and y: must have equal lengths")
        paired = np.column_stack((x, y))
        missing = np.isnan(paired)
        missing_rows = np.flatnonzero(np.any(missing, axis=1)).astype(int).tolist()
        if missing_rows and policy == "reject":
            raise ValueError("x/y: contains missing values; set missing_policy to pairwise")
        usable = ~np.any(missing, axis=1)
        filtered = paired[usable]
        coefficient, p_value, reason = _pair_correlation(filtered[:, 0], filtered[:, 1], method)
        if reason is not None:
            if reason == "constant_input":
                raise ValueError("x/y: constant input has undefined correlation")
            if reason == "insufficient_samples":
                raise ValueError("x/y: correlation requires at least 2 paired samples")
            raise ValueError("x/y: correlation did not produce finite statistics")
        return {
            "parameters": {"method": method, "missing_policy": policy},
            "input_summary": {
                "mode": "pair",
                "observations": int(x.size),
                "missing_count": int(np.count_nonzero(missing)),
                "missing_rows": missing_rows,
                "pairwise_missing_count": int(x.size - filtered.shape[0]),
                "effective_sample_size": int(filtered.shape[0]),
            },
            "result": {
                "coefficient": coefficient,
                "p_value": p_value,
                "sample_size": int(filtered.shape[0]),
            },
            "diagnostics": {"mode": "pair", "pair_reason": None},
            "warnings": [],
            "seed": None,
        }

    matrix = _numeric_array_allow_nan(payload, "matrix", ndim=2)
    missing = np.isnan(matrix)
    if np.any(missing) and policy == "reject":
        raise ValueError("matrix: contains missing values; set missing_policy to pairwise")
    rows, variables = matrix.shape
    coefficients: list[list[float | None]] = [[None] * variables for _ in range(variables)]
    p_values: list[list[float | None]] = [[None] * variables for _ in range(variables)]
    sample_sizes: list[list[int]] = [[0] * variables for _ in range(variables)]
    missing_counts: list[list[int]] = [[0] * variables for _ in range(variables)]
    pair_diagnostics: dict[str, dict[str, object]] = {}

    for left in range(variables):
        for right in range(left, variables):
            usable = ~(missing[:, left] | missing[:, right])
            count = int(np.count_nonzero(usable))
            removed = rows - count
            if left == right:
                values = matrix[usable, left]
                if count < 2:
                    coefficient, p_value, reason = None, None, "insufficient_samples"
                elif np.all(values == values[0]):
                    coefficient, p_value, reason = None, None, "constant_input"
                else:
                    # This is a definitional self-correlation, not a tested null hypothesis.
                    coefficient, p_value, reason = 1.0, None, None
            else:
                coefficient, p_value, reason = _pair_correlation(
                    matrix[usable, left], matrix[usable, right], method
                )
            coefficients[left][right] = coefficients[right][left] = coefficient
            p_values[left][right] = p_values[right][left] = p_value
            sample_sizes[left][right] = sample_sizes[right][left] = count
            missing_counts[left][right] = missing_counts[right][left] = removed
            if reason is not None:
                detail = {"reason": reason, "sample_size": count}
                pair_diagnostics[f"{left},{right}"] = detail
                if left != right:
                    pair_diagnostics[f"{right},{left}"] = detail.copy()

    return {
        "parameters": {"method": method, "missing_policy": policy},
        "input_summary": {
            "mode": "matrix",
            "observations": int(rows),
            "variables": int(variables),
            "missing_count": int(np.count_nonzero(missing)),
            "missing_rows": np.flatnonzero(np.any(missing, axis=1)).astype(int).tolist(),
            "pairwise_missing_count": missing_counts,
            "effective_sample_size": sample_sizes,
        },
        "result": {"coefficient": coefficients, "p_value": p_values, "sample_size": sample_sizes},
        "diagnostics": {
            "mode": "matrix",
            "diagonal": "nonconstant variables with at least two observed values have coefficient 1.0; p_value is null because a self-correlation hypothesis test is not applicable; undefined diagonals are null",
            "pairs": pair_diagnostics,
        },
        "warnings": [],
        "seed": None,
    }


def _confidence(payload: Mapping[str, object]) -> float:
    value = required_field(payload, "confidence")
    if type(value) not in (int, float):
        raise ValueError("confidence: must be an int or float strictly between 0 and 1")
    try:
        confidence = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("confidence: must be an int or float strictly between 0 and 1") from exc
    if not math.isfinite(confidence) or not 0.0 < confidence < 1.0:
        raise ValueError("confidence: must be strictly between 0 and 1")
    return confidence


def _exact_integer(payload: Mapping[str, object], field: str) -> int:
    value = required_field(payload, field)
    if type(value) is not int:
        raise ValueError(f"{field}: must be an integer")
    return value


def _finite_float(value: object, field: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f"{field}: must be representable as a finite number") from exc
    if not math.isfinite(number):
        raise ValueError(f"{field}: must be representable as a finite number")
    return number


def execute_confidence_interval(payload: Mapping[str, object]) -> Mapping[str, object]:
    """Calculate a t mean or Wilson proportion confidence interval safely."""
    _reject_unknown_fields(payload, {"method", "sample", "successes", "total", "confidence"})
    method = string_enum(payload, "method", _CONFIDENCE_METHODS)
    confidence = _confidence(payload)
    if method == "mean-t":
        if "successes" in payload or "total" in payload:
            raise ValueError("successes/total: are not valid for method mean-t")
        sample = _numeric_array_allow_nan(payload, "sample", ndim=1)
        if np.any(np.isnan(sample)):
            raise ValueError("sample: must contain only finite values")
        if sample.size < 2:
            raise ValueError("sample: mean-t requires at least 2 observations")
        sample_size = int(sample.size)
        estimate = math.fsum(float(value) / sample_size for value in sample)
        if not math.isfinite(estimate):
            raise ValueError("sample: mean is not finite")
        # Scaling identifies mathematical zero variance before any subnormal output
        # underflow, and keeps the t margin in the scale-normalized domain.
        scale = float(np.max(np.abs(sample)))
        if scale == 0.0:
            scaled_standard_deviation = 0.0
        else:
            with np.errstate(over="ignore", invalid="ignore"):
                scaled_standard_deviation = float(np.std(sample / scale, ddof=1))
        zero_variance = scaled_standard_deviation == 0.0
        standard_deviation = scaled_standard_deviation * scale
        if not math.isfinite(standard_deviation):
            raise ValueError("sample: variance must be finite")
        standard_error = standard_deviation / math.sqrt(sample_size)
        if zero_variance:
            lower = upper = estimate
            critical_value: float | None = None
            margin = 0.0
        else:
            critical_value = float(stats.t.isf((1.0 - confidence) / 2.0, df=sample_size - 1))
            if not math.isfinite(critical_value):
                raise ValueError("confidence: produced a non-finite t critical value")
            margin = critical_value * (scaled_standard_deviation / math.sqrt(sample_size)) * scale
            lower, upper = estimate - margin, estimate + margin
            if not math.isfinite(lower) or not math.isfinite(upper):
                raise ValueError("sample/confidence: produced a non-finite interval")
        return {
            "parameters": {"method": method, "confidence": confidence},
            "input_summary": {"sample_size": sample_size},
            "result": {
                "estimate": estimate,
                "lower": lower,
                "upper": upper,
                "confidence": confidence,
                "sample_size": sample_size,
                "method": method,
            },
            "diagnostics": {
                "degrees_freedom": sample_size - 1,
                "standard_deviation": standard_deviation,
                "standard_error": standard_error,
                "critical_value": critical_value,
                "margin": margin,
                "zero_variance": zero_variance,
            },
            "warnings": [],
            "seed": None,
        }

    if "sample" in payload:
        raise ValueError("sample: is not valid for method proportion-wilson")
    successes = _exact_integer(payload, "successes")
    total = _exact_integer(payload, "total")
    if total <= 0:
        raise ValueError("total: must be greater than 0")
    if successes < 0 or successes > total:
        raise ValueError("successes: must satisfy 0 <= successes <= total")
    successes_float = _finite_float(successes, "successes")
    total_float = _finite_float(total, "total")
    estimate = successes_float / total_float
    if not math.isfinite(estimate) or not 0.0 <= estimate <= 1.0:
        raise ValueError("successes/total: must produce a finite proportion")
    critical_value = float(stats.norm.isf((1.0 - confidence) / 2.0))
    if not math.isfinite(critical_value):
        raise ValueError("confidence: produced a non-finite normal critical value")
    z_squared = critical_value * critical_value
    inverse_total = 1.0 / total_float
    denominator = 1.0 + z_squared * inverse_total
    # Express both numerator terms in 1/n units before scaling.  This avoids
    # forming 4*n or p/n, which respectively overflow and underflow for huge n.
    center = (successes_float + z_squared / 2.0) * inverse_total / denominator
    half_width = (
        critical_value
        * math.sqrt(successes_float * (1.0 - estimate) + z_squared / 4.0)
        * inverse_total
        / denominator
    )
    lower = max(0.0, min(estimate, center - half_width))
    upper = min(1.0, max(estimate, center + half_width))
    if not all(math.isfinite(value) for value in (lower, upper)):
        raise ValueError("successes/total: produced a non-finite Wilson interval")
    return {
        "parameters": {"method": method, "confidence": confidence},
        "input_summary": {"sample_size": total, "successes": successes},
        "result": {
            "estimate": estimate,
            "lower": lower,
            "upper": upper,
            "confidence": confidence,
            "sample_size": total,
            "method": method,
        },
        "diagnostics": {"critical_value": critical_value, "formula": "wilson_score"},
        "warnings": [],
        "seed": None,
    }
