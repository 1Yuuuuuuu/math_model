"""Deterministic GM(1,1) and fixed-family nonlinear forecast executors."""

from __future__ import annotations

import math
import warnings
from collections.abc import Mapping

import numpy as np
from scipy.optimize import curve_fit

from .base import bounded_integer, json_finite_number, required_field, string_enum


_NONLINEAR_FAMILIES = frozenset({"polynomial", "exponential", "power", "logistic"})
_CURVE_PARAMETER_NAMES = {
    "exponential": ("a", "b", "c"),
    "power": ("a", "b", "c"),
    "logistic": ("L", "k", "x0"),
}
_A_ZERO_TOLERANCE = 1e-12


def _reject_unknown_fields(payload: Mapping[str, object], allowed: set[str]) -> None:
    unknown = sorted(set(payload) - allowed)
    if unknown:
        raise ValueError(f"{unknown[0]}: is not a supported payload field")


def _finite_vector(
    payload: Mapping[str, object], field: str, *, minimum_size: int
) -> np.ndarray:
    value = required_field(payload, field)
    if type(value) is not list:
        raise ValueError(f"{field}: must be a plain JSON array of finite numbers")
    if len(value) < minimum_size:
        raise ValueError(f"{field}: must contain at least {minimum_size} sample(s)")
    normalized = [
        json_finite_number(item, f"{field}[{index}]")
        for index, item in enumerate(value)
    ]
    array = np.asarray(normalized, dtype=float)
    if array.ndim != 1 or not np.all(np.isfinite(array)):
        raise ValueError(f"{field}: must contain only finite numbers")
    return array


def _finite_result(*arrays: np.ndarray, field: str) -> None:
    if any(not np.all(np.isfinite(array)) for array in arrays):
        raise ValueError(f"{field}: produced non-finite values")


def _scaled_mean_and_population_std(values: np.ndarray) -> tuple[float, float]:
    """Compute finite population moments without squaring values at source scale."""
    scale = float(np.max(np.abs(values)))
    if scale == 0.0:
        return 0.0, 0.0
    normalized = values / scale
    normalized_mean = float(np.mean(normalized))
    centered = normalized - normalized_mean
    mean = scale * normalized_mean
    standard_deviation = scale * math.sqrt(float(np.mean(centered**2)))
    return mean, standard_deviation


def execute_gm11(payload: Mapping[str, object]) -> Mapping[str, object]:
    """Fit a positive GM(1,1) series and restore fitted and future observations."""
    _reject_unknown_fields(payload, {"series", "forecast_steps"})
    series = _finite_vector(payload, "series", minimum_size=4)
    if np.any(series <= 0):
        raise ValueError("series: every sample must be positive")
    forecast_steps = bounded_integer(
        payload, "forecast_steps", minimum=1, maximum=10_000
    )

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        with np.errstate(over="ignore", under="ignore", invalid="ignore", divide="ignore"):
            accumulated = np.cumsum(series, dtype=float)
            background = 0.5 * (accumulated[:-1] + accumulated[1:])
            design = np.column_stack((-background, np.ones(series.size - 1)))
    _finite_result(accumulated, background, design, field="series accumulation")

    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            coefficients = np.asarray(
                np.linalg.lstsq(design, series[1:], rcond=None)[0], dtype=float
            )
    except (
        ValueError,
        TypeError,
        RuntimeError,
        OverflowError,
        np.linalg.LinAlgError,
    ) as exc:
        raise ValueError(f"fit: {exc}") from exc
    if coefficients.shape != (2,) or not np.all(np.isfinite(coefficients)):
        raise ValueError("fit: produced non-finite GM(1,1) coefficients")
    development_coefficient, grey_input = map(float, coefficients)

    periods = np.arange(series.size + forecast_steps, dtype=float)
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            with np.errstate(
                over="ignore", under="ignore", invalid="ignore", divide="ignore"
            ):
                response_method = "exponential"
                if abs(development_coefficient) <= _A_ZERO_TOLERANCE:
                    accumulated_response = series[0] + grey_input * periods
                    response_method = "a-zero-limit"
                else:
                    decay = np.exp(-development_coefficient * periods)
                    input_response = (
                        -np.expm1(-development_coefficient * periods)
                        / development_coefficient
                    )
                    accumulated_response = (
                        series[0] * decay + grey_input * input_response
                    )
                restored = np.empty_like(accumulated_response)
                restored[0] = series[0]
                restored[1:] = np.diff(accumulated_response)
    except (
        ValueError,
        TypeError,
        RuntimeError,
        OverflowError,
        FloatingPointError,
    ) as exc:
        raise ValueError(f"fit: {exc}") from exc
    _finite_result(accumulated_response, restored, field="fit")

    fitted = restored[: series.size]
    forecast = restored[series.size :]
    with np.errstate(over="ignore", under="ignore", invalid="ignore", divide="ignore"):
        residuals = series - fitted
        relative_errors = np.abs(residuals) / series
    _finite_result(fitted, forecast, residuals, relative_errors, field="fit")

    count = int(series.size)
    lower_bound = math.exp(-2.0 / (count + 1))
    upper_bound = math.exp(2.0 / (count + 1))
    with np.errstate(over="ignore", under="ignore", invalid="ignore", divide="ignore"):
        level_ratios = series[:-1] / series[1:]
    _finite_result(level_ratios, field="level ratio")
    level_ratio_applicable = bool(
        np.all((level_ratios > lower_bound) & (level_ratios < upper_bound))
    )
    output_warnings: list[str] = []
    if not level_ratio_applicable:
        output_warnings.append(
            "one or more level ratios are outside the GM(1,1) applicability interval"
        )

    diagnostics: dict[str, object] = {
        "development_coefficient_a": development_coefficient,
        "grey_input_b": grey_input,
        "time_response_method": response_method,
        "level_ratios": level_ratios.tolist(),
        "level_ratio_bounds": [lower_bound, upper_bound],
        "level_ratio_applicable": level_ratio_applicable,
    }
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        with np.errstate(
            over="ignore", under="ignore", invalid="ignore", divide="ignore"
        ):
            _, original_std = _scaled_mean_and_population_std(series)
    if not math.isfinite(original_std):
        raise ValueError("posterior accuracy: original variance is not finitely representable")
    if original_std > 0.0:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            with np.errstate(
                over="ignore", under="ignore", invalid="ignore", divide="ignore"
            ):
                residual_mean, residual_std = _scaled_mean_and_population_std(
                    residuals
                )
        if not math.isfinite(residual_std) or not math.isfinite(residual_mean):
            raise ValueError(
                "posterior accuracy: residual variance is not finitely representable"
            )
        posterior_ratio = residual_std / original_std
        with np.errstate(
            over="ignore", under="ignore", invalid="ignore", divide="ignore"
        ):
            small_error_probability = float(
                np.mean(np.abs(residuals - residual_mean) < 0.6745 * original_std)
            )
        if not math.isfinite(posterior_ratio) or not math.isfinite(
            small_error_probability
        ):
            raise ValueError("posterior accuracy: produced non-finite diagnostics")
        diagnostics.update(
            {
                "posterior_ratio_c": posterior_ratio,
                "small_error_probability_p": small_error_probability,
            }
        )
    else:
        diagnostics["posterior_accuracy_reason"] = (
            "posterior ratio C and small-error probability P are undefined because "
            "the original series variance is zero"
        )

    return {
        "parameters": {"forecast_steps": forecast_steps},
        "input_summary": {"samples": count},
        "result": {
            "fitted": fitted.tolist(),
            "forecast": forecast.tolist(),
            "residuals": residuals.tolist(),
            "relative_errors": relative_errors.tolist(),
        },
        "diagnostics": diagnostics,
        "warnings": output_warnings,
        "seed": None,
    }


def _exponential(x: np.ndarray, a: float, b: float, c: float) -> np.ndarray:
    return a * np.exp(b * x) + c


def _power(x: np.ndarray, a: float, b: float, c: float) -> np.ndarray:
    return a * np.power(x, b) + c


def _logistic(x: np.ndarray, L: float, k: float, x0: float) -> np.ndarray:
    return L / (1.0 + np.exp(-k * (x - x0)))


def _initial_parameters(
    payload: Mapping[str, object], family: str, x: np.ndarray, y: np.ndarray
) -> list[float]:
    if "initial_parameters" in payload:
        values = _finite_vector(payload, "initial_parameters", minimum_size=1)
        if values.size != 3:
            raise ValueError("initial_parameters: must contain exactly 3 values")
        return values.tolist()
    if family == "logistic":
        return [float(np.max(y)), 1.0, float(np.median(x))]
    amplitude = float(np.max(y) - np.min(y))
    return [amplitude if amplitude != 0.0 else 1.0, 1.0, float(np.min(y))]


def _fit_metrics(
    y: np.ndarray, fitted: np.ndarray
) -> tuple[float, float, float, str]:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        with np.errstate(
            over="ignore", under="ignore", invalid="ignore", divide="ignore"
        ):
            residuals = y - fitted
            _finite_result(residuals, field="fit")
            scale = float(np.max(np.abs(residuals)))
            if scale == 0.0:
                rmse = 0.0
                mae = 0.0
            else:
                normalized_residuals = residuals / scale
                rmse = scale * math.sqrt(float(np.mean(normalized_residuals**2)))
                mae = scale * float(np.mean(np.abs(normalized_residuals)))

            if np.all(y == y[0]):
                tolerance = 1e-12 * max(1.0, abs(float(y[0])))
                r_squared = (
                    1.0
                    if np.allclose(fitted, y, rtol=1e-12, atol=tolerance)
                    else 0.0
                )
                definition = (
                    "1 for a numerically perfect constant-target fit; otherwise 0"
                )
            else:
                y_scale = float(np.max(np.abs(y)))
                normalized_y = y / y_scale if y_scale else y
                centered = normalized_y - float(np.mean(normalized_y))
                normalized_residuals = residuals / y_scale if y_scale else residuals
                target_ss = float(np.sum(centered**2))
                residual_ss = float(np.sum(normalized_residuals**2))
                r_squared = 1.0 - residual_ss / target_ss
                definition = (
                    "1 - residual sum of squares / target total sum of squares"
                )
    metrics = (rmse, mae, r_squared)
    if not all(math.isfinite(value) for value in metrics):
        raise ValueError("fit: produced non-finite metrics")
    return rmse, mae, r_squared, definition


def execute_nonlinear_regression(payload: Mapping[str, object]) -> Mapping[str, object]:
    """Fit one of four non-executable, fixed regression curve families."""
    family = string_enum(payload, "family", _NONLINEAR_FAMILIES)
    allowed = {"family", "x", "y", "predict_x"}
    allowed.add("degree" if family == "polynomial" else "initial_parameters")
    _reject_unknown_fields(payload, allowed)
    x = _finite_vector(payload, "x", minimum_size=1)
    y = _finite_vector(payload, "y", minimum_size=1)
    if x.size != y.size:
        raise ValueError("x and y: must have equal lengths")
    predict_x = (
        _finite_vector(payload, "predict_x", minimum_size=1)
        if "predict_x" in payload
        else np.empty(0, dtype=float)
    )

    input_parameters: dict[str, object] = {"family": family}
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            with np.errstate(
                over="ignore", under="ignore", invalid="ignore", divide="ignore"
            ):
                if family == "polynomial":
                    degree = bounded_integer(payload, "degree", minimum=1, maximum=5)
                    if x.size < degree + 1:
                        required_samples = degree + 1
                        raise ValueError(
                            f"samples: polynomial degree {degree} requires at least "
                            f"{required_samples} samples"
                        )
                    if np.unique(x).size < degree + 1:
                        required_distinct = degree + 1
                        raise ValueError(
                            f"x: polynomial degree {degree} requires at least "
                            f"{required_distinct} distinct values"
                        )
                    coefficients = np.asarray(np.polyfit(x, y, degree), dtype=float)
                    fitted = np.asarray(np.polyval(coefficients, x), dtype=float)
                    predicted = np.asarray(np.polyval(coefficients, predict_x), dtype=float)
                    fitted_parameters = {
                        f"coefficient_{power}": float(value)
                        for power, value in zip(range(degree, -1, -1), coefficients)
                    }
                    input_parameters["degree"] = degree
                else:
                    if x.size < 3 or np.unique(x).size < 3:
                        raise ValueError(
                            "samples: nonlinear curve fitting requires at least 3 distinct samples"
                        )
                    if family == "power":
                        if np.any(x <= 0):
                            raise ValueError("x: power family requires strictly positive values")
                        if np.any(predict_x <= 0):
                            raise ValueError(
                                "predict_x: power family requires strictly positive values"
                            )
                    initial = _initial_parameters(payload, family, x, y)
                    function = {
                        "exponential": _exponential,
                        "power": _power,
                        "logistic": _logistic,
                    }[family]
                    fitted_values = curve_fit(
                        function, x, y, p0=initial, maxfev=10_000
                    )[0]
                    coefficients = np.asarray(fitted_values, dtype=float)
                    fitted = np.asarray(function(x, *coefficients), dtype=float)
                    predicted = np.asarray(function(predict_x, *coefficients), dtype=float)
                    fitted_parameters = {
                        name: float(value)
                        for name, value in zip(_CURVE_PARAMETER_NAMES[family], coefficients)
                    }
                    input_parameters["initial_parameters"] = initial
    except ValueError as exc:
        if str(exc).startswith(
            ("samples:", "x:", "predict_x:", "initial_parameters:", "degree:")
        ):
            raise
        raise ValueError(f"fit: {exc}") from exc
    except (
        TypeError,
        RuntimeError,
        OverflowError,
        FloatingPointError,
        np.linalg.LinAlgError,
    ) as exc:
        raise ValueError(f"fit: {exc}") from exc

    if coefficients.ndim != 1 or not np.all(np.isfinite(coefficients)):
        raise ValueError("fit: produced non-finite parameters")
    _finite_result(fitted, predicted, field="fit")
    rmse, mae, r_squared, r_squared_definition = _fit_metrics(y, fitted)
    return {
        "parameters": input_parameters,
        "input_summary": {
            "samples": int(x.size),
            "prediction_points": int(predict_x.size),
        },
        "result": {
            "family": family,
            "parameters": fitted_parameters,
            "fitted": fitted.tolist(),
            "predicted": predicted.tolist(),
            "rmse": rmse,
            "mae": mae,
            "r_squared": r_squared,
        },
        "diagnostics": {"r_squared_definition": r_squared_definition},
        "warnings": [],
        "seed": None,
    }
