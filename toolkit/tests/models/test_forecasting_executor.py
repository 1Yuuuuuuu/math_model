from __future__ import annotations

import copy
import importlib
import json
import math
import warnings

import numpy as np
import pytest

from cumcm_toolkit.models import execute
from cumcm_toolkit.models.specifications import get_spec, list_capabilities


GM_SERIES = [2.874, 3.278, 3.795, 4.435, 5.199]


def _nonlinear_payload(family: str) -> dict[str, object]:
    if family == "polynomial":
        x = [-2.0, -1.0, 0.0, 1.0, 2.0]
        return {
            "family": family,
            "x": x,
            "y": [1.0 + 2.0 * value + 3.0 * value**2 for value in x],
            "degree": 2,
            "predict_x": [-0.5, 2.5],
        }
    if family == "exponential":
        x = [0.0, 0.5, 1.0, 1.5, 2.0]
        return {
            "family": family,
            "x": x,
            "y": [2.0 * math.exp(0.3 * value) + 1.0 for value in x],
            "initial_parameters": [2.0, 0.3, 1.0],
            "predict_x": [2.5, 3.0],
        }
    if family == "power":
        x = [0.5, 1.0, 2.0, 3.0, 4.0]
        return {
            "family": family,
            "x": x,
            "y": [2.0 * value**1.5 + 1.0 for value in x],
            "initial_parameters": [2.0, 1.5, 1.0],
            "predict_x": [1.5, 5.0],
        }
    x = [-2.0, -1.0, 0.0, 1.0, 2.0, 3.0]
    return {
        "family": family,
        "x": x,
        "y": [10.0 / (1.0 + math.exp(-1.2 * (value - 0.5))) for value in x],
        "initial_parameters": [10.0, 1.2, 0.5],
        "predict_x": [-3.0, 4.0],
    }


def test_gm11_returns_fitted_forecast_and_accuracy_diagnostics() -> None:
    """Dropping restored values or either posterior statistic hides forecast accuracy."""
    result = execute(
        "grey-prediction-gm11", {"series": GM_SERIES, "forecast_steps": 2}
    )

    assert set(result["result"]) == {
        "fitted",
        "forecast",
        "residuals",
        "relative_errors",
    }
    assert len(result["result"]["fitted"]) == 5
    assert len(result["result"]["forecast"]) == 2
    assert len(result["result"]["residuals"]) == 5
    assert len(result["result"]["relative_errors"]) == 5
    assert {"posterior_ratio_c", "small_error_probability_p"} <= set(
        result["diagnostics"]
    )
    assert 0.0 <= result["diagnostics"]["small_error_probability_p"] <= 1.0


def test_gm11_first_fitted_value_and_residual_definition_are_preserved() -> None:
    """Shifting restored AGO values by one period changes every reported residual."""
    result = execute(
        "grey-prediction-gm11", {"series": GM_SERIES, "forecast_steps": 1}
    )["result"]

    assert result["fitted"][0] == GM_SERIES[0]
    assert result["residuals"] == pytest.approx(
        [actual - fitted for actual, fitted in zip(GM_SERIES, result["fitted"])],
        abs=1e-12,
    )
    assert result["relative_errors"] == pytest.approx(
        [abs(residual) / actual for residual, actual in zip(result["residuals"], GM_SERIES)],
        abs=1e-12,
    )


@pytest.mark.parametrize(
    "series",
    [[1.0, 2.0, 3.0], [1.0, 2.0, 0.0, 4.0], [1.0, -2.0, 3.0, 4.0]],
)
def test_gm11_rejects_too_few_or_nonpositive_samples(series: list[float]) -> None:
    """GM(1,1) is not defined here for under-sized or nonpositive source series."""
    with pytest.raises(
        ValueError,
        match=r"grey-prediction-gm11: execution stage failed: series",
    ):
        execute("grey-prediction-gm11", {"series": series, "forecast_steps": 1})


def test_gm11_constant_original_variance_omits_undefined_posterior_statistics() -> None:
    """Dividing by zero original variance must not emit NaN or infinite C/P values."""
    result = execute(
        "grey-prediction-gm11", {"series": [5.0, 5.0, 5.0, 5.0], "forecast_steps": 1}
    )

    assert "posterior_ratio_c" not in result["diagnostics"]
    assert "small_error_probability_p" not in result["diagnostics"]
    assert "variance" in result["diagnostics"]["posterior_accuracy_reason"]
    json.dumps(result, allow_nan=False)


def test_gm11_constant_residual_variance_reports_zero_posterior_ratio(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Treating a zero residual spread as undefined would discard a valid perfect-fit C=0."""
    forecasting = importlib.import_module("cumcm_toolkit.models.executors.forecasting")
    monkeypatch.setattr(
        forecasting.np.linalg,
        "lstsq",
        lambda *_args, **_kwargs: (np.array([0.0, 2.0]), None, None, None),
    )

    result = execute(
        "grey-prediction-gm11", {"series": [1.0, 2.0, 2.0, 2.0], "forecast_steps": 1}
    )

    assert result["result"]["residuals"] == pytest.approx([0.0] * 4)
    assert result["diagnostics"]["posterior_ratio_c"] == pytest.approx(0.0)
    assert result["diagnostics"]["small_error_probability_p"] == pytest.approx(1.0)


def test_gm11_warns_when_level_ratios_are_outside_the_applicability_interval() -> None:
    """Silently fitting an inapplicable oscillating series overstates GM(1,1) reliability."""
    result = execute(
        "grey-prediction-gm11", {"series": [1.0, 100.0, 1.0, 100.0], "forecast_steps": 1}
    )

    assert result["diagnostics"]["level_ratio_applicable"] is False
    assert "level ratio" in " ".join(result["warnings"])


def test_gm11_uses_the_stable_near_zero_development_coefficient_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Dividing by a near-zero development coefficient causes cancellation or overflow."""
    forecasting = importlib.import_module("cumcm_toolkit.models.executors.forecasting")
    monkeypatch.setattr(
        forecasting.np.linalg,
        "lstsq",
        lambda *_args, **_kwargs: (np.array([1e-20, 2.0]), None, None, None),
    )

    result = execute(
        "grey-prediction-gm11", {"series": [1.0, 2.0, 2.0, 2.0], "forecast_steps": 2}
    )

    assert result["diagnostics"]["time_response_method"] == "a-zero-limit"
    assert result["result"]["fitted"] == pytest.approx([1.0, 2.0, 2.0, 2.0])
    assert result["result"]["forecast"] == pytest.approx([2.0, 2.0])


def test_gm11_extreme_finite_input_fails_without_leaking_numerical_warnings() -> None:
    """AGO overflow from finite source values must become a fielded ValueError, not a warning."""
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        with pytest.raises(ValueError, match=r"grey-prediction-gm11: execution stage failed"):
            execute(
                "grey-prediction-gm11",
                {"series": [1e308, 1e308, 1e308, 1e308], "forecast_steps": 1},
            )
    assert caught == []


@pytest.mark.parametrize("family", ["polynomial", "exponential", "power", "logistic"])
def test_nonlinear_regression_fixed_families_are_json_safe(family: str) -> None:
    """Each promised fixed family must return finite fitted, predicted, and metric values."""
    result = execute("nonlinear-regression", _nonlinear_payload(family))

    assert result["result"]["family"] == family
    assert len(result["result"]["fitted"]) == len(_nonlinear_payload(family)["x"])
    assert len(result["result"]["predicted"]) == 2
    assert all(
        math.isfinite(result["result"][metric])
        for metric in ("rmse", "mae", "r_squared")
    )
    assert json.loads(json.dumps(result, allow_nan=False)) == result


@pytest.mark.parametrize(
    ("family", "parameter_names"),
    [
        ("polynomial", {"coefficient_2", "coefficient_1", "coefficient_0"}),
        ("exponential", {"a", "b", "c"}),
        ("power", {"a", "b", "c"}),
        ("logistic", {"L", "k", "x0"}),
    ],
)
def test_nonlinear_regression_has_exact_result_and_stable_parameter_fields(
    family: str, parameter_names: set[str]
) -> None:
    """Positional or family-dependent output shapes make fitted parameters ambiguous."""
    result = execute("nonlinear-regression", _nonlinear_payload(family))

    assert set(result["result"]) == {
        "family",
        "parameters",
        "fitted",
        "predicted",
        "rmse",
        "mae",
        "r_squared",
    }
    assert set(result["result"]["parameters"]) == parameter_names
    assert set(result["parameters"]) == (
        {"family", "degree"}
        if family == "polynomial"
        else {"family", "initial_parameters"}
    )


def test_polynomial_coefficients_use_descending_stable_degree_names() -> None:
    """Reversing polyfit coefficients assigns the intercept to the quadratic term."""
    parameters = execute("nonlinear-regression", _nonlinear_payload("polynomial"))[
        "result"
    ]["parameters"]

    assert parameters == pytest.approx(
        {"coefficient_2": 3.0, "coefficient_1": 2.0, "coefficient_0": 1.0}
    )


@pytest.mark.parametrize(
    ("payload", "field"),
    [
        ({"family": "custom", "formula": "__import__('os')", "x": [1, 2], "y": [1, 2]}, "family"),
        ({"family": "polynomial", "formula": "x", "x": [1, 2], "y": [1, 2], "degree": 1}, "formula"),
        ({"family": "polynomial", "callback": lambda value: value, "x": [1, 2], "y": [1, 2], "degree": 1}, "callback"),
        ({"family": "polynomial", "x": [1, 2], "y": [1, 2], "degree": 1, "extra": 0}, "extra"),
    ],
)
def test_nonlinear_regression_rejects_custom_formula_callback_and_unknown_fields(
    payload: dict[str, object], field: str
) -> None:
    """Allowing executable or undeclared payload fields would expand the safe fixed API."""
    with pytest.raises(ValueError, match=field):
        execute("nonlinear-regression", payload)


@pytest.mark.parametrize(
    ("payload", "field"),
    [
        ({"family": "polynomial", "x": [1, 2], "y": [1], "degree": 1}, "x and y"),
        ({"family": "polynomial", "x": [1, 2], "y": [1, 2], "degree": 2}, "samples"),
        ({"family": "polynomial", "x": [1, 1], "y": [1, 2], "degree": 1}, "x"),
        ({"family": "exponential", "x": [1, 2], "y": [1, 2]}, "samples"),
        ({"family": "logistic", "x": [1, 2, 3], "y": [1, 2, 3], "initial_parameters": [1, 2]}, "initial_parameters"),
        ({"family": "polynomial", "x": [1, 2], "y": [1, 2], "degree": 0}, "degree"),
        ({"family": "polynomial", "x": [1, 2, 3, 4, 5, 6, 7], "y": [1, 2, 3, 4, 5, 6, 7], "degree": 6}, "degree"),
    ],
)
def test_nonlinear_regression_validates_lengths_sufficiency_and_parameter_counts(
    payload: dict[str, object], field: str
) -> None:
    """Under-determined fits and malformed parameter vectors must fail before a library call."""
    with pytest.raises(ValueError, match=field):
        execute("nonlinear-regression", payload)


@pytest.mark.parametrize(
    ("field", "values"),
    [
        ("x", [0.0, 1.0, 2.0]),
        ("x", [-1.0, 1.0, 2.0]),
        ("predict_x", [0.0, 2.0]),
        ("predict_x", [-1.0, 2.0]),
    ],
)
def test_power_regression_rejects_nonpositive_fit_and_prediction_domains(
    field: str, values: list[float]
) -> None:
    """Power curves with free real exponents are not real-valued at nonpositive x."""
    payload = {
        "family": "power",
        "x": [1.0, 2.0, 3.0],
        "y": [2.0, 3.0, 4.0],
        "initial_parameters": [1.0, 1.0, 1.0],
        "predict_x": [1.0],
    }
    payload[field] = values

    with pytest.raises(ValueError, match=field):
        execute("nonlinear-regression", payload)


def test_nonlinear_regression_translates_curve_fit_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A SciPy RuntimeError must become a stable fielded public ValueError."""
    forecasting = importlib.import_module("cumcm_toolkit.models.executors.forecasting")

    def fail_fit(*_args: object, **_kwargs: object) -> object:
        raise RuntimeError("optimizer did not converge")

    monkeypatch.setattr(forecasting, "curve_fit", fail_fit)

    with pytest.raises(
        ValueError,
        match=r"nonlinear-regression: execution stage failed: fit: optimizer did not converge",
    ):
        execute("nonlinear-regression", _nonlinear_payload("exponential"))


def test_nonlinear_regression_rejects_fitted_or_predicted_overflow_without_warning(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Infinite curve evaluation must not escape as a successful result or RuntimeWarning."""
    forecasting = importlib.import_module("cumcm_toolkit.models.executors.forecasting")
    monkeypatch.setattr(
        forecasting,
        "curve_fit",
        lambda *_args, **_kwargs: (np.array([1e308, 1e308, 0.0]), np.eye(3)),
    )

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        with pytest.raises(ValueError, match=r"nonlinear-regression: execution stage failed: fit"):
            execute("nonlinear-regression", _nonlinear_payload("exponential"))
    assert caught == []


def test_nonlinear_regression_extreme_finite_polynomial_input_fails_cleanly() -> None:
    """Ill-scaled but finite polynomial data must not leak LAPACK warnings or nonfinite values."""
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        with pytest.raises(ValueError, match=r"nonlinear-regression: execution stage failed: fit"):
            execute(
                "nonlinear-regression",
                {
                    "family": "polynomial",
                    "x": [1.0, 2.0],
                    "y": [1e308, -1e308],
                    "degree": 1,
                },
            )
    assert caught == []


def test_nonlinear_regression_constant_target_has_finite_defined_r_squared() -> None:
    """A zero target sum of squares must use the documented perfect-fit convention."""
    result = execute(
        "nonlinear-regression",
        {
            "family": "polynomial",
            "x": [0.0, 1.0, 2.0],
            "y": [4.0, 4.0, 4.0],
            "degree": 1,
        },
    )

    assert result["result"]["r_squared"] == 1.0
    assert result["diagnostics"]["r_squared_definition"] == (
        "1 for a numerically perfect constant-target fit; otherwise 0"
    )


@pytest.mark.parametrize(
    ("model_id", "payload"),
    [
        ("grey-prediction-gm11", {"series": [True, 2, 3, 4], "forecast_steps": 1}),
        ("grey-prediction-gm11", {"series": [1, 2, 3, 4], "forecast_steps": True}),
        ("grey-prediction-gm11", {"series": [1, 2, complex(3, 1), 4], "forecast_steps": 1}),
        ("grey-prediction-gm11", {"series": [1, 2, float("nan"), 4], "forecast_steps": 1}),
        ("grey-prediction-gm11", {"series": [1, 2, 10**10000, 4], "forecast_steps": 1}),
        ("nonlinear-regression", {"family": "polynomial", "x": [1, np.float64(2)], "y": [1, 2], "degree": 1}),
        ("nonlinear-regression", {"family": "polynomial", "x": [1, 2], "y": [1, float("inf")], "degree": 1}),
    ],
)
def test_forecasting_payloads_reject_non_plain_or_nonfinite_numbers(
    model_id: str, payload: dict[str, object]
) -> None:
    """Coercing booleans, subclasses, complex, nonfinite, or oversized numbers violates JSON safety."""
    with pytest.raises(ValueError):
        execute(model_id, payload)


def test_forecasting_payloads_reject_container_subclasses() -> None:
    """Container subclass hooks must never execute inside the trusted model boundary."""

    class DictSubclass(dict[str, object]):
        pass

    class ListSubclass(list[object]):
        pass

    with pytest.raises(ValueError, match="plain JSON object"):
        execute(
            "grey-prediction-gm11",
            DictSubclass(series=[1, 2, 3, 4], forecast_steps=1),
        )
    with pytest.raises(ValueError, match="plain JSON"):
        execute(
            "nonlinear-regression",
            {
                "family": "polynomial",
                "x": ListSubclass([1, 2]),
                "y": [1, 2],
                "degree": 1,
            },
        )


@pytest.mark.parametrize(
    ("model_id", "payload", "card", "payload_fields"),
    [
        (
            "grey-prediction-gm11",
            {"series": GM_SERIES, "forecast_steps": 2},
            "shared/knowledge/model-cards/prediction/grey-prediction.md",
            ("series", "forecast_steps"),
        ),
        (
            "nonlinear-regression",
            _nonlinear_payload("polynomial"),
            "shared/knowledge/model-cards/prediction/nonlinear-regression.md",
            ("family", "x", "y"),
        ),
    ],
)
def test_forecasting_models_are_registered_reproducible_json_safe_and_immutable(
    model_id: str,
    payload: dict[str, object],
    card: str,
    payload_fields: tuple[str, ...],
) -> None:
    """Unregistered, mutating, or nondeterministic forecasting cannot be safely dispatched."""
    before = copy.deepcopy(payload)
    first = execute(model_id, payload)
    second = execute(model_id, payload)
    capabilities = {item["model_id"]: item for item in list_capabilities()}

    assert payload == before
    assert first == second
    assert first["reproducibility"] == {"seed": None, "deterministic": True}
    assert json.loads(json.dumps(first, allow_nan=False)) == first
    assert get_spec(model_id).function is not None
    assert capabilities[model_id] == {
        "model_id": model_id,
        "executor": "forecasting",
        "knowledge_card": card,
        "deterministic": True,
        "seed_supported": False,
        "payload_fields": payload_fields,
    }
