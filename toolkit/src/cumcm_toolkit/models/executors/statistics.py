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
_PARAMETRIC_TESTS = frozenset({"one-sample-t", "independent-t", "paired-t"})
_NONPARAMETRIC_TESTS = frozenset(
    {"mann-whitney-u", "wilcoxon", "kruskal-wallis", "chi-square"}
)
_ALTERNATIVES = frozenset({"two-sided", "less", "greater"})


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
    active: set[int] = set()

    def validate_plain_numbers(node: object) -> None:
        if type(node) in (int, float):
            try:
                number = float(node)
            except (TypeError, ValueError, OverflowError) as exc:
                raise ValueError(
                    f"{field}: must contain numbers representable as finite floats"
                ) from exc
            if math.isinf(number):
                raise ValueError(f"{field}: infinity is not a missing value and is not allowed")
            return
        if type(node) not in (list, tuple):
            raise ValueError(f"{field}: must contain only plain JSON numbers")
        marker = id(node)
        if marker in active:
            raise ValueError(f"{field}: must not contain a cyclic array")
        active.add(marker)
        try:
            for item in node:
                validate_plain_numbers(item)
        finally:
            active.remove(marker)

    validate_plain_numbers(value)
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
    if type(value) not in (int, float):
        raise ValueError(f"{field}: must be representable as a finite number")
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


def _finite_vector(
    payload: Mapping[str, object], field: str, *, minimum_size: int
) -> np.ndarray:
    values = _numeric_array_allow_nan(payload, field, ndim=1)
    if np.any(np.isnan(values)):
        raise ValueError(f"{field}: must contain only finite values")
    if values.size < minimum_size:
        raise ValueError(f"{field}: must contain at least {minimum_size} samples")
    return values


def _alternative(payload: Mapping[str, object]) -> str:
    if "alternative" not in payload:
        return "two-sided"
    return string_enum(payload, "alternative", _ALTERNATIVES)


def _stable_mean(values: np.ndarray, field: str) -> float:
    scale = float(np.max(np.abs(values)))
    if scale == 0.0:
        return 0.0
    with np.errstate(over="ignore", invalid="ignore", under="ignore"):
        scaled_sum = math.fsum(float(value / scale) for value in values)
    mean = (scaled_sum / values.size) * scale
    if not math.isfinite(mean):
        raise ValueError(f"{field}: mean must be finite")
    return mean


def _scaled_sample_deviation(values: np.ndarray, field: str) -> tuple[float, float]:
    scale = float(np.max(np.abs(values)))
    if scale == 0.0:
        return 0.0, 0.0
    with np.errstate(over="ignore", invalid="ignore", under="ignore"):
        scaled = float(np.std(values / scale, ddof=1))
    if not math.isfinite(scaled):
        raise ValueError(f"{field}: variance must be finite")
    deviation = scaled * scale
    if not math.isfinite(deviation):
        raise ValueError(f"{field}: variance must be finite")
    return scale, scaled


def _finite_test_result(calculated: object, test_name: str) -> tuple[float, float, float | None]:
    try:
        statistic = float(calculated.statistic)  # type: ignore[attr-defined]
        p_value = float(calculated.pvalue)  # type: ignore[attr-defined]
        raw_df = getattr(calculated, "df", None)
        degrees_freedom = None if raw_df is None else float(raw_df)
    except (AttributeError, TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f"{test_name}: statistic is not defined as a finite value") from exc
    values = (
        (statistic, p_value)
        if degrees_freedom is None
        else (statistic, p_value, degrees_freedom)
    )
    if not all(math.isfinite(value) for value in values):
        raise ValueError(f"{test_name}: statistic is not defined as a finite value")
    if not 0.0 <= p_value <= 1.0:
        raise ValueError(f"{test_name}: p_value is not defined as a probability")
    return statistic, p_value, degrees_freedom


def _finite_difference(left: float, right: float, field: str) -> float:
    difference = left - right
    if not math.isfinite(difference):
        raise ValueError(f"{field}: mean difference must be finite")
    return difference


def execute_parametric_test(payload: Mapping[str, object]) -> Mapping[str, object]:
    """Execute one approved t-test with a finite Cohen effect size."""
    test_name = string_enum(payload, "test", _PARAMETRIC_TESTS)
    allowed = {
        "one-sample-t": {"test", "sample", "population_mean", "alternative"},
        "independent-t": {
            "test",
            "sample_a",
            "sample_b",
            "equal_variance",
            "alternative",
        },
        "paired-t": {"test", "sample_a", "sample_b", "alternative"},
    }[test_name]
    _reject_unknown_fields(payload, allowed)
    alternative = _alternative(payload)

    if test_name == "one-sample-t":
        sample = _finite_vector(payload, "sample", minimum_size=2)
        population_mean = _finite_float(
            required_field(payload, "population_mean"), "population_mean"
        )
        mean = _stable_mean(sample, "sample")
        mean_difference = _finite_difference(mean, population_mean, "sample/population_mean")
        scale, scaled_deviation = _scaled_sample_deviation(sample, "sample")
        if scaled_deviation == 0.0:
            raise ValueError("sample: effect size is not defined for zero variance")
        with np.errstate(over="ignore", invalid="ignore", under="ignore"):
            scaled_sample = sample / scale
            scaled_population_mean = population_mean / scale
        if not math.isfinite(scaled_population_mean):
            raise ValueError("sample/population_mean: scaled difference must be finite")
        effect_size = (
            _stable_mean(scaled_sample, "sample") - scaled_population_mean
        ) / scaled_deviation
        with warnings.catch_warnings(), np.errstate(all="ignore"):
            warnings.simplefilter("ignore")
            calculated = stats.ttest_1samp(
                scaled_sample, scaled_population_mean, alternative=alternative
            )
        input_summary = {"sample_size": int(sample.size)}
        parameters: dict[str, object] = {
            "test": test_name,
            "alternative": alternative,
            "population_mean": population_mean,
        }
    elif test_name == "independent-t":
        sample_a = _finite_vector(payload, "sample_a", minimum_size=2)
        sample_b = _finite_vector(payload, "sample_b", minimum_size=2)
        equal_variance_value = payload.get("equal_variance", False)
        if type(equal_variance_value) is not bool:
            raise ValueError("equal_variance: must be a boolean")
        equal_variance = equal_variance_value
        mean_a = _stable_mean(sample_a, "sample_a")
        mean_b = _stable_mean(sample_b, "sample_b")
        mean_difference = _finite_difference(mean_a, mean_b, "sample_a/sample_b")
        scale = max(float(np.max(np.abs(sample_a))), float(np.max(np.abs(sample_b))))
        if scale == 0.0:
            raise ValueError("sample_a/sample_b: effect size is not defined for zero variance")
        with np.errstate(over="ignore", invalid="ignore", under="ignore"):
            scaled_a = sample_a / scale
            scaled_b = sample_b / scale
            variance_a = float(np.var(scaled_a, ddof=1))
            variance_b = float(np.var(scaled_b, ddof=1))
        pooled_variance = (
            (sample_a.size - 1) * variance_a + (sample_b.size - 1) * variance_b
        ) / (sample_a.size + sample_b.size - 2)
        if not math.isfinite(pooled_variance) or pooled_variance <= 0.0:
            raise ValueError("sample_a/sample_b: effect size is not defined for zero variance")
        effect_size = (
            _stable_mean(scaled_a, "sample_a") - _stable_mean(scaled_b, "sample_b")
        ) / math.sqrt(pooled_variance)
        with warnings.catch_warnings(), np.errstate(all="ignore"):
            warnings.simplefilter("ignore")
            calculated = stats.ttest_ind(
                scaled_a,
                scaled_b,
                equal_var=equal_variance,
                alternative=alternative,
            )
        input_summary = {
            "sample_size_a": int(sample_a.size),
            "sample_size_b": int(sample_b.size),
        }
        parameters = {
            "test": test_name,
            "alternative": alternative,
            "equal_variance": equal_variance,
        }
    else:
        sample_a = _finite_vector(payload, "sample_a", minimum_size=1)
        sample_b = _finite_vector(payload, "sample_b", minimum_size=1)
        if sample_a.size != sample_b.size:
            raise ValueError("sample_a/sample_b: must have equal lengths for paired-t")
        if sample_a.size < 2:
            raise ValueError("sample_a/sample_b: paired-t requires at least 2 samples")
        with np.errstate(over="ignore", invalid="ignore", under="ignore"):
            differences = sample_a - sample_b
        if not np.all(np.isfinite(differences)):
            raise ValueError("sample_a/sample_b: paired differences must be finite")
        scale = float(np.max(np.abs(differences)))
        if scale == 0.0:
            raise ValueError("paired differences: effect size is not defined for zero variance")
        with np.errstate(over="ignore", invalid="ignore", under="ignore"):
            scaled_differences = differences / scale
        scaled_difference_mean = _stable_mean(scaled_differences, "paired differences")
        mean_difference = _stable_mean(differences, "paired differences")
        _, scaled_deviation = _scaled_sample_deviation(
            scaled_differences, "paired differences"
        )
        if scaled_deviation == 0.0:
            raise ValueError("paired differences: effect size is not defined for zero variance")
        effect_size = scaled_difference_mean / scaled_deviation
        with warnings.catch_warnings(), np.errstate(all="ignore"):
            warnings.simplefilter("ignore")
            calculated = stats.ttest_rel(
                scaled_differences,
                np.zeros_like(scaled_differences),
                alternative=alternative,
            )
        input_summary = {"pairs": int(sample_a.size)}
        parameters = {"test": test_name, "alternative": alternative}

    statistic, p_value, degrees_freedom = _finite_test_result(calculated, test_name)
    if degrees_freedom is None or not math.isfinite(effect_size):
        raise ValueError(f"{test_name}: effect size or degrees of freedom is not defined")
    return {
        "parameters": parameters,
        "input_summary": input_summary,
        "result": {
            "statistic": statistic,
            "p_value": p_value,
            "degrees_freedom": degrees_freedom,
            "mean_difference": mean_difference,
            "effect_size": effect_size,
        },
        "diagnostics": {"effect_size_method": "cohen_d"},
        "warnings": [],
        "seed": None,
    }


def _rank_groups(payload: Mapping[str, object]) -> list[np.ndarray]:
    raw_groups = required_field(payload, "groups")
    if not isinstance(raw_groups, (list, tuple)):
        raise ValueError("groups: must be an array of at least two numeric arrays")
    try:
        groups = list(raw_groups)  # type: ignore[arg-type]
    except TypeError as exc:
        raise ValueError("groups: must be an array of at least two numeric arrays") from exc
    if len(groups) < 2:
        raise ValueError("groups: must contain at least two groups")
    try:
        parsed = [
            _finite_vector({"groups": group}, "groups", minimum_size=1)
            for group in groups
        ]
    except ValueError as exc:
        raise ValueError(
            f"groups: every group must be a non-empty finite numeric array ({exc})"
        ) from exc
    if sum(group.size for group in parsed) <= len(parsed):
        raise ValueError("groups: require more total samples than groups for a defined effect")
    return parsed


def _anova_groups(payload: Mapping[str, object]) -> list[np.ndarray]:
    """Read strict JSON group arrays suitable for a one-way ANOVA."""
    raw_groups = required_field(payload, "groups")
    if type(raw_groups) is not list or len(raw_groups) < 2:
        raise ValueError("groups: must be an array of at least two numeric arrays")

    parsed: list[np.ndarray] = []
    for raw_group in raw_groups:
        if type(raw_group) is not list:
            raise ValueError("groups: every group must be a plain JSON numeric array")
        try:
            parsed.append(_finite_vector({"groups": raw_group}, "groups", minimum_size=1))
        except ValueError as exc:
            raise ValueError(
                f"groups: every group must be a non-empty finite numeric array ({exc})"
            ) from exc

    if sum(group.size for group in parsed) <= len(parsed):
        raise ValueError("groups: insufficient within degrees of freedom")
    return parsed


def _scaled_sum_squares(values: np.ndarray, center: float) -> float:
    """Sum squared deviations in a bounded scale without overflow."""
    value = math.fsum((float(item) - center) ** 2 for item in values)
    if not math.isfinite(value):
        raise ValueError("anova: sums of squares must be finite")
    return value


def _restore_anova_sum_of_squares(scaled_value: float, scale: float, field: str) -> float:
    """Return a finite original-scale sum of squares or fail closed."""
    with np.errstate(over="ignore", invalid="ignore", under="ignore"):
        restored = (scaled_value * scale) * scale
    if not math.isfinite(restored) or (scaled_value > 0.0 and restored == 0.0):
        raise ValueError(f"anova: {field} must be a finite representable value")
    return restored


def execute_anova(payload: Mapping[str, object]) -> Mapping[str, object]:
    """Execute a finite one-way omnibus ANOVA without post-hoc comparisons."""
    _reject_unknown_fields(payload, {"groups"})
    groups = _anova_groups(payload)
    group_count = len(groups)
    total_samples = sum(group.size for group in groups)
    df_between = group_count - 1
    df_within = total_samples - group_count
    if df_between <= 0 or df_within <= 0:
        raise ValueError("anova: degrees of freedom must be positive")

    all_values = np.concatenate(groups)
    scale = float(np.max(np.abs(all_values)))
    if not math.isfinite(scale) or scale == 0.0:
        raise ValueError("anova: total variance must be positive and finite")
    with np.errstate(over="ignore", invalid="ignore", under="ignore"):
        scaled_groups = [group / scale for group in groups]
    if not all(np.all(np.isfinite(group)) for group in scaled_groups):
        raise ValueError("anova: scaled observations must be finite")

    scaled_all = np.concatenate(scaled_groups)
    grand_mean = _stable_mean(scaled_all, "groups")
    group_means = [_stable_mean(group, "groups") for group in scaled_groups]
    ss_between_scaled = math.fsum(
        group.size * (mean - grand_mean) ** 2
        for group, mean in zip(scaled_groups, group_means, strict=True)
    )
    ss_within_scaled = math.fsum(
        _scaled_sum_squares(group, mean)
        for group, mean in zip(scaled_groups, group_means, strict=True)
    )
    ss_total_scaled = _scaled_sum_squares(scaled_all, grand_mean)
    if not all(math.isfinite(value) for value in (ss_between_scaled, ss_within_scaled, ss_total_scaled)):
        raise ValueError("anova: sums of squares must be finite")
    if ss_total_scaled <= 0.0:
        raise ValueError("anova: total variance must be positive")
    if ss_within_scaled <= 0.0:
        raise ValueError("anova: within-group variance must be positive for a finite statistic")

    ms_between_scaled = ss_between_scaled / df_between
    ms_within_scaled = ss_within_scaled / df_within
    statistic = ms_between_scaled / ms_within_scaled
    p_value = float(stats.f.sf(statistic, df_between, df_within))
    eta_squared = ss_between_scaled / ss_total_scaled
    if not all(math.isfinite(value) for value in (statistic, p_value, eta_squared)):
        raise ValueError("anova: statistic, p_value, and eta_squared must be finite")
    if not 0.0 <= p_value <= 1.0 or not 0.0 <= eta_squared <= 1.0:
        raise ValueError("anova: p_value or eta_squared is outside its defined range")

    ss_between = _restore_anova_sum_of_squares(ss_between_scaled, scale, "ss_between")
    ss_within = _restore_anova_sum_of_squares(ss_within_scaled, scale, "ss_within")
    ss_total = _restore_anova_sum_of_squares(ss_total_scaled, scale, "ss_total")
    ms_between = ss_between / df_between
    ms_within = ss_within / df_within
    if (
        not math.isfinite(ms_between)
        or ms_between < 0.0
        or not math.isfinite(ms_within)
        or ms_within <= 0.0
    ):
        raise ValueError("anova: mean squares must be finite with positive within variance")

    return {
        "parameters": {"method": "one-way-omnibus"},
        "input_summary": {
            "groups": group_count,
            "group_sizes": [int(group.size) for group in groups],
            "sample_size": int(total_samples),
        },
        "result": {
            "statistic": statistic,
            "p_value": p_value,
            "df_between": int(df_between),
            "df_within": int(df_within),
            "ss_between": ss_between,
            "ss_within": ss_within,
            "ss_total": ss_total,
            "ms_between": ms_between,
            "ms_within": ms_within,
            "eta_squared": eta_squared,
        },
        "diagnostics": {
            "post_hoc": "not_performed",
            "post_hoc_note": "A significant omnibus result does not identify differing group pairs.",
        },
        "warnings": [],
        "seed": None,
    }


def execute_nonparametric_test(payload: Mapping[str, object]) -> Mapping[str, object]:
    """Execute an approved rank or contingency-table test without undefined floats."""
    test_name = string_enum(payload, "test", _NONPARAMETRIC_TESTS)
    allowed = {
        "mann-whitney-u": {"test", "sample_a", "sample_b", "alternative"},
        "wilcoxon": {"test", "sample_a", "sample_b", "alternative"},
        "kruskal-wallis": {"test", "groups"},
        "chi-square": {"test", "table"},
    }[test_name]
    _reject_unknown_fields(payload, allowed)
    output_warnings: list[str] = []

    if test_name == "mann-whitney-u":
        alternative = _alternative(payload)
        sample_a = _finite_vector(payload, "sample_a", minimum_size=1)
        sample_b = _finite_vector(payload, "sample_b", minimum_size=1)
        with warnings.catch_warnings(), np.errstate(all="ignore"):
            warnings.simplefilter("ignore")
            calculated = stats.mannwhitneyu(sample_a, sample_b, alternative=alternative)
        statistic, p_value, _ = _finite_test_result(calculated, test_name)
        denominator = float(sample_a.size * sample_b.size)
        effect_size = 2.0 * statistic / denominator - 1.0
        parameters = {"test": test_name, "alternative": alternative}
        input_summary = {
            "sample_size_a": int(sample_a.size),
            "sample_size_b": int(sample_b.size),
        }
        diagnostics = {"effect_size_method": "rank_biserial"}
    elif test_name == "wilcoxon":
        alternative = _alternative(payload)
        sample_a = _finite_vector(payload, "sample_a", minimum_size=1)
        sample_b = _finite_vector(payload, "sample_b", minimum_size=1)
        if sample_a.size != sample_b.size:
            raise ValueError("sample_a/sample_b: must have equal lengths for wilcoxon")
        with np.errstate(over="ignore", invalid="ignore"):
            differences = sample_a - sample_b
        if not np.all(np.isfinite(differences)):
            raise ValueError("sample_a/sample_b: paired differences must be finite")
        nonzero = differences != 0.0
        if not np.any(nonzero):
            raise ValueError(
                "paired differences: wilcoxon is not defined when all differences are zero"
            )
        ranks = stats.rankdata(np.abs(differences[nonzero]), method="average")
        positive = float(np.sum(ranks[differences[nonzero] > 0.0]))
        negative = float(np.sum(ranks[differences[nonzero] < 0.0]))
        rank_total = positive + negative
        effect_size = (positive - negative) / rank_total
        with warnings.catch_warnings(), np.errstate(all="ignore"):
            warnings.simplefilter("ignore")
            calculated = stats.wilcoxon(sample_a, sample_b, alternative=alternative)
        statistic, p_value, _ = _finite_test_result(calculated, test_name)
        parameters = {"test": test_name, "alternative": alternative}
        input_summary = {
            "pairs": int(sample_a.size),
            "nonzero_differences": int(np.count_nonzero(nonzero)),
        }
        diagnostics = {
            "effect_size_method": "matched_pairs_rank_biserial",
            "positive_rank_sum": positive,
            "negative_rank_sum": negative,
        }
    elif test_name == "kruskal-wallis":
        groups = _rank_groups(payload)
        with warnings.catch_warnings(), np.errstate(all="ignore"):
            warnings.simplefilter("ignore")
            try:
                calculated = stats.kruskal(*groups)
            except ValueError as exc:
                raise ValueError("groups: kruskal-wallis statistic is not defined") from exc
        statistic, p_value, _ = _finite_test_result(calculated, test_name)
        total = sum(group.size for group in groups)
        denominator = total - len(groups)
        effect_size = max(0.0, (statistic - len(groups) + 1.0) / denominator)
        parameters = {"test": test_name}
        input_summary = {
            "groups": len(groups),
            "group_sizes": [int(group.size) for group in groups],
            "sample_size": int(total),
        }
        diagnostics = {"effect_size_method": "epsilon_squared"}
    else:
        table = _numeric_array_allow_nan(payload, "table", ndim=2)
        if np.any(np.isnan(table)):
            raise ValueError("table: must contain only finite values")
        if table.shape[0] < 2 or table.shape[1] < 2:
            raise ValueError("table: must have at least two rows and two columns")
        if np.any(table < 0.0):
            raise ValueError("table: counts must be non-negative")
        if np.any(np.sum(table, axis=0) <= 0.0) or np.any(np.sum(table, axis=1) <= 0.0):
            raise ValueError("table: every row and column must have a positive total")
        with warnings.catch_warnings(), np.errstate(all="ignore"):
            warnings.simplefilter("ignore")
            try:
                calculated = stats.chi2_contingency(table)
            except (ValueError, OverflowError) as exc:
                raise ValueError("table: chi-square statistic is not defined") from exc
        statistic, p_value, _ = _finite_test_result(calculated, test_name)
        expected = np.asarray(calculated.expected_freq, dtype=float)
        if not np.all(np.isfinite(expected)):
            raise ValueError("table: expected counts must be finite")
        if np.any(expected < 5.0):
            output_warnings.append("one or more expected counts are below 5")
        total = float(np.sum(table))
        effect_denominator = total * min(table.shape[0] - 1, table.shape[1] - 1)
        effect_size = math.sqrt(statistic / effect_denominator)
        parameters = {"test": test_name}
        input_summary = {
            "rows": int(table.shape[0]),
            "columns": int(table.shape[1]),
            "sample_size": total,
        }
        diagnostics = {
            "effect_size_method": "cramers_v",
            "degrees_freedom": int(calculated.dof),
            "low_expected_count": bool(np.any(expected < 5.0)),
        }

    if not math.isfinite(effect_size):
        raise ValueError(f"{test_name}: effect size is not defined as a finite value")
    result: dict[str, object] = {
        "statistic": statistic,
        "p_value": p_value,
        "effect_size": effect_size,
    }
    if test_name == "chi-square":
        result["expected_counts"] = expected.tolist()
    return {
        "parameters": parameters,
        "input_summary": input_summary,
        "result": result,
        "diagnostics": diagnostics,
        "warnings": sorted(set(output_warnings)),
        "seed": None,
    }
