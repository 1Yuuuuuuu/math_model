from __future__ import annotations

import copy
import importlib
import json
import math
import re
import warnings

import numpy as np
import pytest

from cumcm_toolkit.models import execute
from cumcm_toolkit.models.specifications import get_spec, list_capabilities


GM_SERIES = [2.874, 3.278, 3.795, 4.435, 5.199]
ARIMA_SERIES = [
    10.0,
    10.66829419696158,
    11.181859485365136,
    11.528224001611973,
    11.848639500938415,
    12.308215145067372,
    12.944116900360214,
    13.631397319743758,
    14.197871649324677,
    14.582423697048352,
    14.891195777822126,
    15.30000195868986,
    15.892685416399913,
    16.584033407365327,
    17.198121471138976,
    17.630057568031424,
    17.942419336666985,
    18.30772050162409,
    18.849802550645665,
    19.52997544193259,
    20.182589050145527,
    20.66733112770721,
    20.99822973814192,
    21.33075599940439,
    21.818884327598677,
    22.473529483498054,
    23.15251169009592,
    23.6912751856809,
    24.054181157661575,
    24.367273439088265,
]


def _arima_payload() -> dict[str, object]:
    return {"series": ARIMA_SERIES.copy(), "order": [1, 1, 0], "forecast_steps": 3}


def _smoothing_payload() -> dict[str, object]:
    return {
        "series": [10.0 + 0.3 * index for index in range(16)],
        "forecast_steps": 3,
        "trend": "add",
        "seasonal": None,
        "damped_trend": False,
    }


def _assert_finite_json_tree(value: object) -> None:
    if isinstance(value, dict):
        assert type(value) is dict
        for key, item in value.items():
            assert type(key) is str
            _assert_finite_json_tree(item)
    elif isinstance(value, list):
        assert type(value) is list
        for item in value:
            _assert_finite_json_tree(item)
    elif isinstance(value, float):
        assert math.isfinite(value)
    else:
        assert value is None or type(value) in (str, int, bool)


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
    assert result["result"]["fitted"] == pytest.approx(
        [
            2.874,
            3.2554336993259096,
            3.7989331453603097,
            4.433170623596338,
            5.173294982018841,
        ],
        rel=1e-12,
        abs=1e-12,
    )
    assert result["result"]["forecast"] == pytest.approx(
        [6.036984191073225, 7.044867584381507], rel=1e-12, abs=1e-12
    )
    assert result["diagnostics"]["posterior_ratio_c"] == pytest.approx(
        0.014925427065723306, rel=1e-12, abs=1e-12
    )
    assert result["diagnostics"]["small_error_probability_p"] == 1.0


def test_gm11_uses_population_variance_for_the_small_error_probability() -> None:
    """Using sample variance changes this hand-derived small-error probability to 1."""
    series = [
        0.34749417654136144,
        2.4994258051126437,
        1.0004542635773273,
        1.5352244162651367,
    ]

    result = execute(
        "grey-prediction-gm11", {"series": series, "forecast_steps": 2}
    )

    assert result["result"]["fitted"] == pytest.approx(
        [
            0.34749417654136144,
            2.2576880901193594,
            1.587158390268354,
            1.11577492339345,
        ],
        rel=1e-12,
        abs=1e-12,
    )
    assert result["result"]["forecast"] == pytest.approx(
        [0.7843915813992356, 0.5514285543349087], rel=1e-12, abs=1e-12
    )
    assert result["diagnostics"]["posterior_ratio_c"] == pytest.approx(
        0.4821835657789063, rel=1e-12, abs=1e-12
    )
    assert result["diagnostics"]["small_error_probability_p"] == 0.75


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


def test_gm11_tiny_nonconstant_series_retains_positive_population_variance(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Naive squaring underflows around 1e-200 and falsely marks variance as zero."""
    forecasting = importlib.import_module("cumcm_toolkit.models.executors.forecasting")
    monkeypatch.setattr(
        forecasting.np.linalg,
        "lstsq",
        lambda *_args, **_kwargs: (np.array([0.0, 2e-200]), None, None, None),
    )

    result = execute(
        "grey-prediction-gm11",
        {"series": [1e-200, 2e-200, 2e-200, 2e-200], "forecast_steps": 1},
    )

    assert math.isfinite(result["diagnostics"]["posterior_ratio_c"])
    assert result["diagnostics"]["posterior_ratio_c"] < 1e-12
    assert result["diagnostics"]["small_error_probability_p"] == 1.0
    assert "posterior_accuracy_reason" not in result["diagnostics"]


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
        ({"family": "logistic", "x": [1, 2, 3], "y": [1, 2, 3], "initial_parameters": [1, 2, 3, 4]}, "initial_parameters"),
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


def test_nonlinear_regression_rejects_predicted_only_overflow_without_warning(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Prediction overflow must fail even when every training evaluation remains finite."""
    forecasting = importlib.import_module("cumcm_toolkit.models.executors.forecasting")
    monkeypatch.setattr(
        forecasting,
        "curve_fit",
        lambda *_args, **_kwargs: (np.array([1.0, 1000.0, 0.0]), np.eye(3)),
    )
    payload = {
        "family": "exponential",
        "x": [0.0, 1e-308, 2e-308],
        "y": [1.0, 1.0, 1.0],
        "initial_parameters": [1.0, 1.0, 0.0],
        "predict_x": [2.0],
    }

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        with pytest.raises(
            ValueError, match=r"nonlinear-regression: execution stage failed: fit"
        ):
            execute("nonlinear-regression", payload)
    assert caught == []


def test_nonlinear_regression_metric_overflow_is_suppressed_and_translated(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """R² normalization overflow must not leak a RuntimeWarning before rejection."""
    forecasting = importlib.import_module("cumcm_toolkit.models.executors.forecasting")
    monkeypatch.setattr(
        forecasting.np,
        "polyfit",
        lambda *_args, **_kwargs: np.array([0.0, 1e308]),
    )

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        with pytest.raises(
            ValueError, match=r"nonlinear-regression: execution stage failed: fit"
        ):
            execute(
                "nonlinear-regression",
                {
                    "family": "polynomial",
                    "x": [1.0, 2.0],
                    "y": [1e-300, 2e-300],
                    "degree": 1,
                },
            )
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


def test_nonlinear_regression_imperfect_constant_target_has_zero_r_squared(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The degenerate-target convention must distinguish an imperfect constant fit."""
    forecasting = importlib.import_module("cumcm_toolkit.models.executors.forecasting")
    monkeypatch.setattr(
        forecasting.np,
        "polyfit",
        lambda *_args, **_kwargs: np.array([0.0, 5.0]),
    )

    result = execute(
        "nonlinear-regression",
        {
            "family": "polynomial",
            "x": [0.0, 1.0, 2.0],
            "y": [4.0, 4.0, 4.0],
            "degree": 1,
        },
    )

    assert result["result"]["r_squared"] == 0.0
    assert result["diagnostics"]["r_squared_definition"] == (
        "1 for a numerically perfect constant-target fit; otherwise 0"
    )


@pytest.mark.parametrize(
    ("model_id", "payload", "field"),
    [
        ("grey-prediction-gm11", {"series": [True, 2, 3, 4], "forecast_steps": 1}, "series[0]"),
        ("grey-prediction-gm11", {"series": [1, 2, 3, 4], "forecast_steps": True}, "forecast_steps"),
        ("grey-prediction-gm11", {"series": [1, 2, complex(3, 1), 4], "forecast_steps": 1}, "series[2]"),
        ("grey-prediction-gm11", {"series": [1, 2, float("nan"), 4], "forecast_steps": 1}, "series[2]"),
        ("grey-prediction-gm11", {"series": [1, 2, 10**10000, 4], "forecast_steps": 1}, "series[2]"),
        ("nonlinear-regression", {"family": "polynomial", "x": [1, np.float64(2)], "y": [1, 2], "degree": 1}, "x[1]"),
        ("nonlinear-regression", {"family": "polynomial", "x": [1, 2], "y": [1, float("inf")], "degree": 1}, "y[1]"),
    ],
)
def test_forecasting_payloads_reject_non_plain_or_nonfinite_numbers(
    model_id: str, payload: dict[str, object], field: str
) -> None:
    """Coercing booleans, subclasses, complex, nonfinite, or oversized numbers violates JSON safety."""
    with pytest.raises(
        ValueError,
        match=rf"{re.escape(model_id)}: execution stage failed: {re.escape(field)}",
    ):
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


def test_arima_returns_complete_finite_forecast_contract() -> None:
    """Dropping intervals, fitted parameters, criteria, or residual diagnostics breaks the adapter contract."""
    result = execute("arima", _arima_payload())

    assert set(result["result"]) == {
        "fitted",
        "forecast",
        "confidence_interval",
        "fitted_parameters",
    }
    assert len(result["result"]["fitted"]) == len(ARIMA_SERIES)
    assert len(result["result"]["forecast"]) == 3
    assert len(result["result"]["confidence_interval"]) == 3
    assert all(len(row) == 2 for row in result["result"]["confidence_interval"])
    assert set(result["result"]["fitted_parameters"]) == {"ar.L1", "sigma2"}
    assert math.isfinite(result["diagnostics"]["aic"])
    assert math.isfinite(result["diagnostics"]["bic"])
    assert result["diagnostics"]["fitted_values_definition"] == (
        "statsmodels in-sample one-step predictions; startup and differencing "
        "initialization values are retained"
    )
    residuals = result["diagnostics"]["residual_summary"]
    assert residuals["count"] == len(ARIMA_SERIES)
    assert set(residuals) == {"count", "mean", "standard_deviation", "rmse"}
    _assert_finite_json_tree(result)


def test_arima_zero_order_without_trend_has_hand_checked_zero_forecast() -> None:
    """Adding an implicit constant would make a no-trend white-noise model forecast the sample mean."""
    result = execute(
        "arima",
        {
            "series": [1.0, -1.0, 2.0, -2.0, 1.5, -1.5, 0.5, -0.5],
            "order": [0, 0, 0],
            "forecast_steps": 2,
            "trend": "n",
        },
    )

    assert result["result"]["fitted"] == pytest.approx([0.0] * 8, abs=1e-12)
    assert result["result"]["forecast"] == pytest.approx([0.0, 0.0], abs=1e-12)


@pytest.mark.parametrize(
    "order",
    [
        (1, 0, 0),
        [1, 0],
        [1, 0, 0, 0],
        [True, 0, 0],
        [np.int64(1), 0, 0],
        [1.0, 0, 0],
        [-1, 0, 0],
        [10**4000, 0, 0],
    ],
)
def test_arima_rejects_non_plain_or_unsafe_order(order: object) -> None:
    """Coercing order containers or entries can bypass dimensional and resource bounds."""
    payload = _arima_payload()
    payload["order"] = order

    with pytest.raises(
        ValueError, match=r"arima: execution stage failed: order"
    ):
        execute("arima", payload)


def test_arima_rejects_order_list_subclass() -> None:
    """A list subclass can mutate order during iteration and must be rejected before statsmodels."""

    class ListSubclass(list[object]):
        pass

    payload = _arima_payload()
    payload["order"] = ListSubclass([1, 1, 0])
    with pytest.raises(
        ValueError, match=r"arima: execution stage failed: order"
    ):
        execute("arima", payload)


@pytest.mark.parametrize(
    "forecast_steps", [True, np.int64(1), 1.0, 0, -1, 10_001, 10**4000]
)
def test_arima_rejects_non_plain_or_unbounded_forecast_steps(
    forecast_steps: object,
) -> None:
    """Non-built-in or impractical horizons must never reach statsmodels allocation paths."""
    payload = _arima_payload()
    payload["forecast_steps"] = forecast_steps

    with pytest.raises(
        ValueError, match=r"arima: execution stage failed: forecast_steps"
    ):
        execute("arima", payload)


@pytest.mark.parametrize(
    ("trend", "order"),
    [
        ("quadratic", [1, 0, 0]),
        (1, [1, 0, 0]),
        ("c", [1, 1, 0]),
        ("ct", [1, 1, 0]),
        ("t", [1, 2, 0]),
    ],
)
def test_arima_rejects_unsupported_or_conflicting_trend(
    trend: object, order: list[int]
) -> None:
    """A trend below the differencing order is eliminated and is not identifiable."""
    payload = _arima_payload()
    payload.update({"trend": trend, "order": order})

    with pytest.raises(
        ValueError, match=r"arima: execution stage failed: trend"
    ):
        execute("arima", payload)


def test_arima_rejects_order_specific_insufficient_sample() -> None:
    """A generic nonempty-series check would admit an underidentified high-order fit."""
    with pytest.raises(
        ValueError, match=r"arima: execution stage failed: series.*requires at least"
    ):
        execute(
            "arima",
            {
                "series": [1.0, 1.2, 1.1, 1.4, 1.3, 1.5],
                "order": [2, 1, 2],
                "forecast_steps": 1,
            },
        )


def test_arima_rejects_constant_unidentifiable_series_before_fit() -> None:
    """A constant input can yield degenerate likelihood values that look superficially finite."""
    with pytest.raises(
        ValueError, match=r"arima: execution stage failed: series.*constant"
    ):
        execute(
            "arima",
            {"series": [4.0] * 12, "order": [1, 0, 0], "forecast_steps": 2},
        )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("series", [1.0, 2.0, True, 4.0, 5.0]),
        ("series", [1.0, 2.0, np.float64(3.0), 4.0, 5.0]),
        ("series", [1.0, 2.0, complex(3.0, 1.0), 4.0, 5.0]),
        ("series", [1.0, 2.0, float("nan"), 4.0, 5.0]),
        ("series", [1.0, 2.0, float("inf"), 4.0, 5.0]),
        ("series", [1.0, 2.0, 10**10000, 4.0, 5.0]),
        ("unexpected", 1),
    ],
)
def test_arima_rejects_unsafe_numbers_and_unknown_fields(
    field: str, value: object
) -> None:
    """Unsafe numeric leaves and undeclared fields must fail at their exact public field."""
    payload = _arima_payload()
    if field == "unexpected":
        payload[field] = value
    else:
        payload[field] = value

    expected_field = "series[2]" if field == "series" else field
    with pytest.raises(
        ValueError,
        match=rf"arima: execution stage failed: {re.escape(expected_field)}",
    ):
        execute("arima", payload)


def test_arima_rejects_plain_json_container_subclasses_at_the_public_boundary() -> None:
    """Deep-copying a mapping subclass before validation could execute attacker-controlled hooks."""

    class DictSubclass(dict[str, object]):
        pass

    with pytest.raises(
        ValueError, match=r"arima: payload stage failed: payload must be a plain JSON object"
    ):
        execute("arima", DictSubclass(_arima_payload()))


def test_arima_translates_fit_failure_and_nonconvergence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Library exceptions and an explicit nonconverged result must share a stable fit failure boundary."""
    forecasting = importlib.import_module("cumcm_toolkit.models.executors.forecasting")

    class FailingModel:
        def fit(self) -> object:
            raise RuntimeError("optimizer exploded")

    monkeypatch.setattr(forecasting, "ARIMA", lambda *_args, **_kwargs: FailingModel())
    with pytest.raises(
        ValueError, match=r"arima: execution stage failed: fit: optimizer exploded"
    ):
        execute("arima", _arima_payload())

    class NonconvergedModel:
        def fit(self) -> object:
            return type("Fit", (), {"mle_retvals": {"converged": False}})()

    monkeypatch.setattr(
        forecasting, "ARIMA", lambda *_args, **_kwargs: NonconvergedModel()
    )
    with pytest.raises(
        ValueError, match=r"arima: execution stage failed: fit: did not converge"
    ):
        execute("arima", _arima_payload())


def test_arima_reports_only_convergence_warning_and_leaves_other_warning_visible(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Blanket warning capture would hide an unrelated dependency warning from the caller."""
    forecasting = importlib.import_module("cumcm_toolkit.models.executors.forecasting")
    from statsmodels.tools.sm_exceptions import ConvergenceWarning

    real_arima = forecasting.ARIMA

    class WarningModel:
        def __init__(self, *args: object, **kwargs: object) -> None:
            self._model = real_arima(*args, **kwargs)

        def fit(self) -> object:
            warnings.warn("captured convergence detail", ConvergenceWarning)
            warnings.warn("caller-visible detail", UserWarning)
            return self._model.fit()

    monkeypatch.setattr(forecasting, "ARIMA", WarningModel)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        result = execute("arima", _arima_payload())

    assert result["warnings"] == ["captured convergence detail"]
    assert [(item.category, str(item.message)) for item in caught] == [
        (UserWarning, "caller-visible detail")
    ]


def test_arima_rejects_nonfinite_forecast_without_leaking_numerical_warnings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A statsmodels overflow must become a fielded failure, never a JSON Infinity."""
    forecasting = importlib.import_module("cumcm_toolkit.models.executors.forecasting")
    real_arima = forecasting.ARIMA

    class OverflowForecast:
        predicted_mean = np.array([float("inf"), 1.0, 2.0])

        def conf_int(self) -> np.ndarray:
            return np.array([[0.0, 1.0], [0.0, 1.0], [0.0, 1.0]])

    class OverflowFit:
        def __init__(self, fitted: object) -> None:
            self._fitted = fitted
            self.mle_retvals = {"converged": True}
            self.fittedvalues = fitted.fittedvalues
            self.resid = fitted.resid
            self.params = fitted.params
            self.param_names = fitted.param_names
            self.aic = fitted.aic
            self.bic = fitted.bic

        def get_forecast(self, _steps: int) -> OverflowForecast:
            return OverflowForecast()

    class OverflowModel:
        def __init__(self, *args: object, **kwargs: object) -> None:
            self._model = real_arima(*args, **kwargs)

        def fit(self) -> OverflowFit:
            return OverflowFit(self._model.fit())

    monkeypatch.setattr(forecasting, "ARIMA", OverflowModel)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        with pytest.raises(
            ValueError, match=r"arima: execution stage failed: forecast"
        ):
            execute("arima", _arima_payload())
    assert caught == []


@pytest.mark.parametrize(
    ("target", "expected_field"),
    [
        ("fitted", "fitted"),
        ("confidence_interval", "confidence_interval"),
        ("fitted_parameters", "fitted_parameters"),
        ("parameter_names", "fitted_parameters"),
        ("aic", "aic"),
        ("bic", "bic"),
        ("residuals", "residual diagnostics"),
    ],
)
def test_arima_rejects_each_nonfinite_result_component(
    monkeypatch: pytest.MonkeyPatch, target: str, expected_field: str
) -> None:
    """Every published fit component needs its own finite-value gate, not only forecasts."""
    forecasting = importlib.import_module("cumcm_toolkit.models.executors.forecasting")

    class FakeForecast:
        predicted_mean = np.array([1.0, 2.0, 3.0])

        def conf_int(self) -> np.ndarray:
            interval = np.array([[0.0, 2.0], [1.0, 3.0], [2.0, 4.0]])
            if target == "confidence_interval":
                interval[0, 0] = float("inf")
            return interval

    class FakeFit:
        mle_retvals = {"converged": True}
        fittedvalues = np.ones(len(ARIMA_SERIES))
        resid = np.ones(len(ARIMA_SERIES))
        params = np.array([0.5, 1.0])
        param_names = ["ar.L1", "sigma2"]
        aic = 10.0
        bic = 12.0

        def __init__(self) -> None:
            if target == "fitted":
                self.fittedvalues = self.fittedvalues.copy()
                self.fittedvalues[0] = float("inf")
            elif target == "fitted_parameters":
                self.params = self.params.copy()
                self.params[0] = float("inf")
            elif target == "parameter_names":
                self.param_names = None
            elif target == "aic":
                self.aic = float("inf")
            elif target == "bic":
                self.bic = float("inf")
            elif target == "residuals":
                self.resid = self.resid.copy()
                self.resid[0] = float("inf")

        def get_forecast(self, _steps: int) -> FakeForecast:
            return FakeForecast()

    class FakeModel:
        def fit(self) -> FakeFit:
            return FakeFit()

    monkeypatch.setattr(forecasting, "ARIMA", lambda *_args, **_kwargs: FakeModel())
    with pytest.raises(
        ValueError,
        match=rf"arima: execution stage failed: {re.escape(expected_field)}",
    ):
        execute("arima", _arima_payload())


def test_arima_accepts_identifiable_linear_trend_after_first_differencing() -> None:
    """Rejecting every trend for differenced data would incorrectly exclude a valid linear trend."""
    result = execute(
        "arima",
        {
            "series": ARIMA_SERIES,
            "order": [0, 1, 0],
            "forecast_steps": 2,
            "trend": "t",
        },
    )

    assert result["parameters"]["trend"] == "t"
    assert len(result["result"]["forecast"]) == 2


def test_arima_extreme_finite_scale_fails_closed_without_numerical_warning() -> None:
    """Finite leaves whose scale makes differencing overflow must fail without warning leakage."""
    payload = {
        "series": [1e308, -1e308, 1e308, -1e308, 1e308, -1e308],
        "order": [1, 1, 0],
        "forecast_steps": 1,
    }
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        with pytest.raises(
            ValueError, match=r"arima: execution stage failed: series"
        ):
            execute("arima", payload)
    assert caught == []


def test_exponential_smoothing_returns_complete_finite_forecast_contract() -> None:
    """The adapter must expose fitted values, forecasts, smoothing parameters, SSE, and residuals."""
    result = execute("exponential-smoothing", _smoothing_payload())

    assert set(result["result"]) == {"fitted", "forecast", "fitted_parameters"}
    assert len(result["result"]["fitted"]) == 16
    assert len(result["result"]["forecast"]) == 3
    assert set(result["result"]["fitted_parameters"]) == {
        "smoothing_level",
        "smoothing_trend",
    }
    assert math.isfinite(result["diagnostics"]["sse"])
    residuals = result["diagnostics"]["residual_summary"]
    assert set(residuals) == {"count", "mean", "standard_deviation", "rmse"}
    assert residuals["count"] == 16
    _assert_finite_json_tree(result)


def test_exponential_smoothing_defaults_omitted_damping_to_false() -> None:
    """Treating optional damping as required rejects the documented public payload."""
    result = execute(
        "exponential-smoothing",
        {
            "series": [10.0 + 0.5 * index for index in range(30)],
            "forecast_steps": 3,
            "trend": "add",
            "seasonal": None,
        },
    )

    assert result["parameters"]["damped_trend"] is False
    assert len(result["result"]["forecast"]) == 3


def test_exponential_smoothing_linear_trend_matches_hand_checked_forecast() -> None:
    """A wrong Holt level/trend update must not preserve only output shape and finiteness."""
    series = [10.0, 10.3, 10.6, 10.9, 11.2, 11.5, 11.8, 12.1]

    result = execute(
        "exponential-smoothing",
        {
            "series": series,
            "forecast_steps": 2,
            "trend": "add",
            "seasonal": None,
            "damped_trend": False,
        },
    )

    assert result["result"]["fitted"] == pytest.approx(series, abs=1e-5)
    assert result["result"]["forecast"] == pytest.approx(
        [12.4, 12.7], abs=2e-5
    )


def test_exponential_smoothing_constant_series_fails_closed_without_warning() -> None:
    """A degenerate exact fit must fail before statsmodels emits log-zero diagnostics."""
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        with pytest.raises(
            ValueError,
            match=r"exponential-smoothing: execution stage failed: series.*constant",
        ):
            execute(
                "exponential-smoothing",
                {
                    "series": [5.0] * 8,
                    "forecast_steps": 2,
                    "trend": None,
                    "seasonal": None,
                    "damped_trend": False,
                },
            )
    assert caught == []


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("trend", "linear"),
        ("trend", True),
        ("seasonal", "multiplicative"),
        ("seasonal", False),
        ("damped_trend", 1),
        ("damped_trend", np.bool_(True)),
        ("unexpected", 1),
    ],
)
def test_exponential_smoothing_rejects_invalid_components_and_unknown_fields(
    field: str, value: object
) -> None:
    """Coercing component choices or booleans changes the selected Holt-Winters model."""
    payload = _smoothing_payload()
    payload[field] = value

    with pytest.raises(
        ValueError,
        match=rf"exponential-smoothing: execution stage failed: {re.escape(field)}",
    ):
        execute("exponential-smoothing", payload)


def test_exponential_smoothing_requires_trend_for_damping() -> None:
    """A damped level-only model has no trend state to damp."""
    payload = _smoothing_payload()
    payload.update({"trend": None, "damped_trend": True})
    with pytest.raises(
        ValueError,
        match=r"exponential-smoothing: execution stage failed: damped_trend.*requires a trend",
    ):
        execute("exponential-smoothing", payload)


@pytest.mark.parametrize(
    ("seasonal", "seasonal_periods", "field"),
    [
        ("add", None, "seasonal_periods"),
        (None, 4, "seasonal_periods"),
        ("add", True, "seasonal_periods"),
        ("add", np.int64(4), "seasonal_periods"),
        ("add", 4.0, "seasonal_periods"),
        ("add", 1, "seasonal_periods"),
        ("add", 10_001, "seasonal_periods"),
    ],
)
def test_exponential_smoothing_enforces_exact_seasonal_period_semantics(
    seasonal: object, seasonal_periods: object, field: str
) -> None:
    """Season length must exist only for a real seasonal model and be a safe built-in integer."""
    payload = _smoothing_payload()
    payload["seasonal"] = seasonal
    if seasonal_periods is not None:
        payload["seasonal_periods"] = seasonal_periods

    with pytest.raises(
        ValueError,
        match=rf"exponential-smoothing: execution stage failed: {field}",
    ):
        execute("exponential-smoothing", payload)


def test_exponential_smoothing_rejects_explicit_null_period_for_nonseasonal_model() -> None:
    """Present-but-null seasonal_periods is not the same contract as omitting an inappropriate field."""
    payload = _smoothing_payload()
    payload["seasonal_periods"] = None
    with pytest.raises(
        ValueError,
        match=r"exponential-smoothing: execution stage failed: seasonal_periods",
    ):
        execute("exponential-smoothing", payload)


def test_exponential_smoothing_requires_two_complete_seasons() -> None:
    """One partial second season cannot identify stable seasonal states."""
    with pytest.raises(
        ValueError,
        match=r"exponential-smoothing: execution stage failed: series.*two complete seasons",
    ):
        execute(
            "exponential-smoothing",
            {
                "series": list(range(10)),
                "forecast_steps": 2,
                "trend": None,
                "seasonal": "add",
                "seasonal_periods": 6,
                "damped_trend": False,
            },
        )


@pytest.mark.parametrize(
    ("series", "trend", "damped"),
    [([1.0], None, False), ([1.0, 2.0], "add", False), ([1.0, 2.0, 3.0], "add", True)],
)
def test_exponential_smoothing_validates_component_specific_sample_sufficiency(
    series: list[float], trend: str | None, damped: bool
) -> None:
    """Level, trend, and damped models need increasing state-identification evidence."""
    with pytest.raises(
        ValueError, match=r"exponential-smoothing: execution stage failed: series.*requires at least"
    ):
        execute(
            "exponential-smoothing",
            {
                "series": series,
                "forecast_steps": 1,
                "trend": trend,
                "seasonal": None,
                "damped_trend": damped,
            },
        )


@pytest.mark.parametrize("component", ["trend", "seasonal"])
def test_exponential_smoothing_multiplicative_components_require_positive_series(
    component: str,
) -> None:
    """Multiplicative state updates are undefined for zero or negative observations."""
    payload = {
        "series": [1.0, 2.0, 0.0, 4.0, 1.0, 2.0, 3.0, 4.0],
        "forecast_steps": 1,
        "trend": None,
        "seasonal": None,
        "damped_trend": False,
    }
    payload[component] = "mul"
    if component == "seasonal":
        payload["seasonal_periods"] = 4

    with pytest.raises(
        ValueError, match=r"exponential-smoothing: execution stage failed: series.*positive"
    ):
        execute("exponential-smoothing", payload)


@pytest.mark.parametrize(
    ("field", "value", "expected_field"),
    [
        ("series", [1.0, 2.0, True, 4.0], "series[2]"),
        ("series", [1.0, 2.0, np.float64(3.0), 4.0], "series[2]"),
        ("series", [1.0, 2.0, complex(3.0, 1.0), 4.0], "series[2]"),
        ("series", [1.0, 2.0, float("nan"), 4.0], "series[2]"),
        ("series", [1.0, 2.0, float("inf"), 4.0], "series[2]"),
        ("series", [1.0, 2.0, 10**10000, 4.0], "series[2]"),
        ("forecast_steps", True, "forecast_steps"),
        ("forecast_steps", np.int64(1), "forecast_steps"),
        ("forecast_steps", 1.0, "forecast_steps"),
        ("forecast_steps", 0, "forecast_steps"),
        ("forecast_steps", 10_001, "forecast_steps"),
    ],
)
def test_exponential_smoothing_rejects_unsafe_numeric_inputs(
    field: str, value: object, expected_field: str
) -> None:
    """Every numeric leaf and horizon must keep strict finite built-in JSON semantics."""
    payload = _smoothing_payload()
    payload[field] = value
    with pytest.raises(
        ValueError,
        match=rf"exponential-smoothing: execution stage failed: {re.escape(expected_field)}",
    ):
        execute("exponential-smoothing", payload)


def test_exponential_smoothing_rejects_container_subclasses_at_the_public_boundary() -> None:
    """Neither top-level mappings nor nested series subclasses may cross the JSON boundary."""

    class DictSubclass(dict[str, object]):
        pass

    class ListSubclass(list[object]):
        pass

    with pytest.raises(
        ValueError,
        match=r"exponential-smoothing: payload stage failed: payload must be a plain JSON object",
    ):
        execute("exponential-smoothing", DictSubclass(_smoothing_payload()))

    payload = _smoothing_payload()
    payload["series"] = ListSubclass(payload["series"])
    with pytest.raises(
        ValueError, match=r"exponential-smoothing: execution stage failed: series"
    ):
        execute("exponential-smoothing", payload)


def test_exponential_smoothing_translates_fit_failure_and_nonconvergence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A failed optimizer and a returned unsuccessful optimizer state must both fail closed."""
    forecasting = importlib.import_module("cumcm_toolkit.models.executors.forecasting")

    class FailingModel:
        def fit(self) -> object:
            raise RuntimeError("smoothing optimizer exploded")

    monkeypatch.setattr(
        forecasting, "ExponentialSmoothing", lambda *_args, **_kwargs: FailingModel()
    )
    with pytest.raises(
        ValueError,
        match=r"exponential-smoothing: execution stage failed: fit: smoothing optimizer exploded",
    ):
        execute("exponential-smoothing", _smoothing_payload())

    class NonconvergedModel:
        def fit(self) -> object:
            return type("Fit", (), {"mle_retvals": {"success": False}})()

    monkeypatch.setattr(
        forecasting,
        "ExponentialSmoothing",
        lambda *_args, **_kwargs: NonconvergedModel(),
    )
    with pytest.raises(
        ValueError,
        match=r"exponential-smoothing: execution stage failed: fit: did not converge",
    ):
        execute("exponential-smoothing", _smoothing_payload())


def test_exponential_smoothing_reports_only_convergence_warning_and_leaves_other_warning_visible(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Only statsmodels convergence diagnostics belong in the result warning list."""
    forecasting = importlib.import_module("cumcm_toolkit.models.executors.forecasting")
    from statsmodels.tools.sm_exceptions import ConvergenceWarning

    real_model = forecasting.ExponentialSmoothing

    class WarningModel:
        def __init__(self, *args: object, **kwargs: object) -> None:
            self._model = real_model(*args, **kwargs)

        def fit(self) -> object:
            warnings.warn("smoothing convergence detail", ConvergenceWarning)
            warnings.warn("smoothing caller detail", FutureWarning)
            return self._model.fit()

    monkeypatch.setattr(forecasting, "ExponentialSmoothing", WarningModel)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        result = execute("exponential-smoothing", _smoothing_payload())

    assert result["warnings"] == ["smoothing convergence detail"]
    assert [(item.category, str(item.message)) for item in caught] == [
        (FutureWarning, "smoothing caller detail")
    ]


def test_exponential_smoothing_rejects_nonfinite_forecast_without_warning(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Infinite forecasts from a nominally successful fit must fail at the forecast field."""
    forecasting = importlib.import_module("cumcm_toolkit.models.executors.forecasting")
    real_model = forecasting.ExponentialSmoothing

    class OverflowFit:
        def __init__(self, fitted: object) -> None:
            self.mle_retvals = {"success": True}
            self.fittedvalues = fitted.fittedvalues
            self.params = fitted.params
            self.sse = fitted.sse

        def forecast(self, _steps: int) -> np.ndarray:
            return np.array([float("inf"), 1.0, 2.0])

    class OverflowModel:
        def __init__(self, *args: object, **kwargs: object) -> None:
            self._model = real_model(*args, **kwargs)

        def fit(self) -> OverflowFit:
            return OverflowFit(self._model.fit())

    monkeypatch.setattr(forecasting, "ExponentialSmoothing", OverflowModel)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        with pytest.raises(
            ValueError,
            match=r"exponential-smoothing: execution stage failed: forecast",
        ):
            execute("exponential-smoothing", _smoothing_payload())
    assert caught == []


@pytest.mark.parametrize(
    ("target", "expected_field"),
    [
        ("fitted", "fitted"),
        ("fitted_parameters", "fitted_parameters"),
        ("sse", "sse"),
    ],
)
def test_exponential_smoothing_rejects_each_nonfinite_fit_component(
    monkeypatch: pytest.MonkeyPatch, target: str, expected_field: str
) -> None:
    """Fitted values, smoothing coefficients, and SSE must be finite independently."""
    forecasting = importlib.import_module("cumcm_toolkit.models.executors.forecasting")

    class FakeFit:
        mle_retvals = {"success": True}
        fittedvalues = np.ones(16)
        params = {"smoothing_level": 0.5, "smoothing_trend": 0.1}
        sse = 1.0

        def __init__(self) -> None:
            if target == "fitted":
                self.fittedvalues = self.fittedvalues.copy()
                self.fittedvalues[0] = float("inf")
            elif target == "fitted_parameters":
                self.params = dict(self.params)
                self.params["smoothing_level"] = float("inf")
            elif target == "sse":
                self.sse = float("inf")

        def forecast(self, _steps: int) -> np.ndarray:
            return np.array([1.0, 2.0, 3.0])

    class FakeModel:
        def fit(self) -> FakeFit:
            return FakeFit()

    monkeypatch.setattr(
        forecasting,
        "ExponentialSmoothing",
        lambda *_args, **_kwargs: FakeModel(),
    )
    with pytest.raises(
        ValueError,
        match=rf"exponential-smoothing: execution stage failed: {expected_field}",
    ):
        execute("exponential-smoothing", _smoothing_payload())


def test_exponential_smoothing_accepts_two_complete_additive_seasons() -> None:
    """The seasonal validation branch must admit a valid two-cycle additive model."""
    result = execute(
        "exponential-smoothing",
        {
            "series": [
                10.0,
                12.0,
                11.0,
                13.0,
                10.1,
                11.9,
                11.2,
                12.8,
            ],
            "forecast_steps": 2,
            "trend": None,
            "seasonal": "add",
            "seasonal_periods": 4,
            "damped_trend": False,
        },
    )

    assert len(result["result"]["forecast"]) == 2
    assert "smoothing_seasonal" in result["result"]["fitted_parameters"]


def test_exponential_smoothing_real_forecast_overflow_fails_without_warning() -> None:
    """Real multiplicative long-horizon ufunc overflow must not warn before rejection."""
    payload = {
        "series": [1.2**index for index in range(16)],
        "forecast_steps": 10_000,
        "trend": "mul",
        "seasonal": None,
        "damped_trend": False,
    }

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        with pytest.raises(
            ValueError,
            match=r"exponential-smoothing: execution stage failed: forecast",
        ):
            execute("exponential-smoothing", payload)
    assert caught == []


def test_exponential_smoothing_real_large_scale_fit_is_rejected_without_warning() -> None:
    """A fit-scale gate must reject real matrix-overflow inputs before statsmodels."""
    payload = {
        "series": [1e154 if index % 2 == 0 else -1e154 for index in range(16)],
        "forecast_steps": 2,
        "trend": "add",
        "seasonal": None,
        "damped_trend": False,
    }

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        with pytest.raises(
            ValueError,
            match=r"exponential-smoothing: execution stage failed: series",
        ):
            execute("exponential-smoothing", payload)
    assert caught == []


def test_exponential_smoothing_extreme_finite_scale_fails_without_warning() -> None:
    """An overflow-prone finite range must be rejected before optimizer warnings can leak."""
    payload = {
        "series": [1e308, -1e308, 1e308, -1e308],
        "forecast_steps": 1,
        "trend": "add",
        "seasonal": None,
        "damped_trend": False,
    }
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        with pytest.raises(
            ValueError, match=r"exponential-smoothing: execution stage failed: series"
        ):
            execute("exponential-smoothing", payload)
    assert caught == []


@pytest.mark.parametrize(
    ("model_id", "payload", "card", "payload_fields"),
    [
        (
            "arima",
            _arima_payload(),
            "shared/knowledge/model-cards/prediction/arima.md",
            ("series", "order", "forecast_steps"),
        ),
        (
            "exponential-smoothing",
            _smoothing_payload(),
            "shared/knowledge/model-cards/prediction/exponential-smoothing.md",
            ("series", "forecast_steps", "trend", "seasonal"),
        ),
    ],
)
def test_new_forecasting_models_are_registered_deterministic_json_safe_and_immutable(
    model_id: str,
    payload: dict[str, object],
    card: str,
    payload_fields: tuple[str, ...],
) -> None:
    """Both real cards must resolve to deterministic, seedless, immutable JSON capabilities."""
    before = copy.deepcopy(payload)
    first = execute(model_id, payload)
    second = execute(model_id, payload)
    capabilities = {item["model_id"]: item for item in list_capabilities()}

    assert payload == before
    assert first == second
    assert first["reproducibility"] == {"seed": None, "deterministic": True}
    assert json.loads(json.dumps(first, allow_nan=False)) == first
    _assert_finite_json_tree(first)
    assert get_spec(model_id).function is not None
    assert capabilities[model_id] == {
        "model_id": model_id,
        "executor": "forecasting",
        "knowledge_card": card,
        "deterministic": True,
        "seed_supported": False,
        "payload_fields": payload_fields,
    }
