from __future__ import annotations

import copy
import json
import math
import re
import warnings
from pathlib import Path

import numpy as np
import pytest
import yaml
from sklearn.base import BaseEstimator
from sklearn.linear_model import LogisticRegression

from cumcm_toolkit.models import execute
from cumcm_toolkit.models import registry as legacy_registry
from cumcm_toolkit.models.registry import get_model
from cumcm_toolkit.models.runner import run_model
from cumcm_toolkit.models.specifications import get_spec, list_capabilities


LINEAR_PAYLOAD: dict[str, object] = {
    "X": [[1.0], [2.0], [3.0]],
    "y": [3.0, 5.0, 7.0],
    "predict_X": [[4.0]],
}
TREE_PAYLOAD: dict[str, object] = {
    "X": [[0.0], [1.0], [2.0], [3.0]],
    "y": ["low", "low", "high", "high"],
    "predict_X": [[0.5], [2.5]],
    "params": {"max_depth": 1},
    "seed": 7,
}
LOGISTIC_PAYLOAD: dict[str, object] = {
    "X": [[-2.0], [-1.0], [1.0], [2.0]],
    "y": ["negative", "negative", "positive", "positive"],
    "predict_X": [[-3.0], [3.0]],
    "params": {"C": 1000.0, "max_iter": 1000, "solver": "liblinear"},
    "seed": 7,
}


def _payload_for(model_id: str) -> dict[str, object]:
    return copy.deepcopy(
        {
            "linear-regression": LINEAR_PAYLOAD,
            "decision-tree": TREE_PAYLOAD,
            "logistic-regression": LOGISTIC_PAYLOAD,
        }[model_id]
    )


def _assert_finite_plain_json(value: object) -> None:
    if type(value) is dict:
        for key, item in value.items():  # type: ignore[union-attr]
            assert type(key) is str
            _assert_finite_plain_json(item)
        return
    if type(value) is list:
        for item in value:  # type: ignore[union-attr]
            _assert_finite_plain_json(item)
        return
    if type(value) is float:
        assert math.isfinite(value)
        return
    assert value is None or type(value) in (str, int, bool)


def _assert_no_estimator(value: object) -> None:
    assert not isinstance(value, BaseEstimator)
    if type(value) is dict:
        assert not ({"fitted", "estimator", "model_object"} & set(value))  # type: ignore[arg-type]
        for item in value.values():  # type: ignore[union-attr]
            _assert_no_estimator(item)
    elif type(value) is list:
        for item in value:  # type: ignore[union-attr]
            _assert_no_estimator(item)


def _assert_execution_error(model_id: str, payload: object, field: str) -> None:
    with pytest.raises(
        ValueError,
        match=rf"{re.escape(model_id)}: execution stage failed: {re.escape(field)}",
    ):
        execute(model_id, payload)  # type: ignore[arg-type]


def test_linear_regression_known_answer_and_metrics() -> None:
    """A wrong factory, prediction name, coefficient, or metric formula breaks this literal line."""
    result = execute("linear-regression", copy.deepcopy(LINEAR_PAYLOAD))

    assert result["result"]["training_predictions"] == pytest.approx([3.0, 5.0, 7.0])
    assert result["result"]["predictions"] == pytest.approx([9.0])
    assert result["result"]["coefficients"] == pytest.approx([2.0])
    assert result["result"]["intercept"] == pytest.approx(1.0)
    assert result["result"]["rmse"] == pytest.approx(0.0, abs=1e-12)
    assert result["result"]["mae"] == pytest.approx(0.0, abs=1e-12)
    assert result["result"]["r_squared"] == pytest.approx(1.0)


def test_decision_tree_known_answer_probability_order_and_normalization() -> None:
    """Reversing estimator class order or returning leaf counts instead of probabilities fails."""
    result = execute("decision-tree", copy.deepcopy(TREE_PAYLOAD))

    assert result["result"]["classes"] == ["high", "low"]
    assert result["result"]["training_predictions"] == ["low", "low", "high", "high"]
    assert result["result"]["predictions"] == ["low", "high"]
    assert np.allclose(
        result["result"]["probabilities"], [[0.0, 1.0], [1.0, 0.0]]
    )
    assert result["result"]["feature_importances"] == pytest.approx([1.0])
    assert result["result"]["tree_depth"] == 1
    assert result["result"]["accuracy"] == pytest.approx(1.0)
    assert all(math.isclose(sum(row), 1.0, rel_tol=1e-12, abs_tol=1e-12) for row in result["result"]["probabilities"])


def test_logistic_regression_known_answer_probability_order_and_normalization() -> None:
    """A non-logistic classifier, reversed classes, or unnormalized scores breaks this symmetric case."""
    result = execute("logistic-regression", copy.deepcopy(LOGISTIC_PAYLOAD))

    assert result["result"]["classes"] == ["negative", "positive"]
    assert result["result"]["training_predictions"] == [
        "negative",
        "negative",
        "positive",
        "positive",
    ]
    assert result["result"]["predictions"] == ["negative", "positive"]
    assert result["result"]["accuracy"] == pytest.approx(1.0)
    assert len(result["result"]["coefficients"]) == 1
    assert result["result"]["coefficients"][0][0] > 0.0
    assert result["result"]["intercept"] == pytest.approx([0.0], abs=1e-10)
    probabilities = result["result"]["probabilities"]
    assert probabilities[0][0] > probabilities[0][1]
    assert probabilities[1][1] > probabilities[1][0]
    assert all(math.isclose(sum(row), 1.0, rel_tol=1e-12, abs_tol=1e-12) for row in probabilities)


@pytest.mark.parametrize("model_id", ["linear-regression", "decision-tree", "logistic-regression"])
def test_supervised_results_are_plain_finite_json_without_estimators_and_inputs_are_immutable(
    model_id: str,
) -> None:
    """Returning sklearn state, nonfinite leaves, or mutating caller data violates the public boundary."""
    payload = _payload_for(model_id)
    before = copy.deepcopy(payload)

    result = execute(model_id, payload)

    assert payload == before
    assert json.loads(json.dumps(result, allow_nan=False)) == result
    _assert_finite_plain_json(result)
    _assert_no_estimator(result)


@pytest.mark.parametrize("model_id", ["linear-regression", "decision-tree", "logistic-regression"])
def test_prediction_only_fields_are_omitted_without_predict_X(model_id: str) -> None:
    """Inventing empty prediction outputs makes absence indistinguishable from zero requested rows."""
    payload = _payload_for(model_id)
    del payload["predict_X"]

    result = execute(model_id, payload)

    assert "predictions" not in result["result"]
    assert "probabilities" not in result["result"]
    assert "training_predictions" in result["result"]


def test_constant_target_regression_uses_explicit_finite_r_squared_convention() -> None:
    """Delegating constant-target R-squared to sklearn would emit an ambiguous or unstable value."""
    result = execute(
        "linear-regression",
        {"X": [[0.0], [1.0], [2.0]], "y": [4.0, 4.0, 4.0]},
    )

    assert result["result"]["r_squared"] == 1.0
    assert result["diagnostics"]["r_squared_definition"] == (
        "1 for a numerically perfect constant-target fit; otherwise 0"
    )


def test_imperfect_constant_target_regression_uses_zero_r_squared(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An imperfect constant-target fit must use the documented zero convention, never NaN."""

    class ImperfectLinear:
        coef_ = np.array([0.0])
        intercept_ = 0.0

        def fit(self, X: np.ndarray, y: np.ndarray) -> ImperfectLinear:
            return self

        def predict(self, X: np.ndarray) -> np.ndarray:
            return np.zeros(X.shape[0])

    monkeypatch.setattr(
        legacy_registry,
        "get_model",
        lambda name: lambda *, seed, params: ImperfectLinear(),
    )
    result = execute(
        "linear-regression",
        {"X": [[0.0], [1.0], [2.0]], "y": [4.0, 4.0, 4.0]},
    )

    assert result["result"]["r_squared"] == 0.0
    assert result["diagnostics"]["r_squared_definition"] == (
        "1 for a numerically perfect constant-target fit; otherwise 0"
    )


@pytest.mark.parametrize("model_id", ["decision-tree", "logistic-regression"])
def test_classifiers_require_at_least_two_target_classes(model_id: str) -> None:
    """Fitting a one-class classifier would defer a stable applicability error to sklearn."""
    payload = _payload_for(model_id)
    payload["y"] = ["only"] * 4
    _assert_execution_error(model_id, payload, "y")


@pytest.mark.parametrize("model_id", ["linear-regression", "decision-tree", "logistic-regression"])
def test_supervised_models_reject_X_y_length_mismatch(model_id: str) -> None:
    """Sklearn-specific length messages must not replace the shared fielded validation error."""
    payload = _payload_for(model_id)
    payload["y"] = list(payload["y"])[1:]  # type: ignore[arg-type]
    _assert_execution_error(model_id, payload, "X and y")


@pytest.mark.parametrize("model_id", ["linear-regression", "decision-tree", "logistic-regression"])
def test_supervised_models_reject_prediction_feature_width_mismatch(model_id: str) -> None:
    """A prediction matrix with a different schema must fail before estimator prediction."""
    payload = _payload_for(model_id)
    payload["predict_X"] = [[0.0, 1.0]]
    _assert_execution_error(model_id, payload, "predict_X")


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("X", []),
        ("X", [[]]),
        ("X", [1.0, 2.0]),
        ("X", [[[1.0]]]),
        ("X", [[1.0], [2.0, 3.0]]),
        ("y", []),
        ("y", [[1.0], [2.0], [3.0]]),
        ("predict_X", []),
        ("predict_X", [1.0]),
        ("predict_X", [[1.0], [2.0, 3.0]]),
    ],
)
def test_linear_regression_rejects_empty_ragged_or_wrong_dimensional_arrays(
    field: str, value: object
) -> None:
    """Relaxing array shape validation would pass malformed structures into NumPy/sklearn."""
    payload = copy.deepcopy(LINEAR_PAYLOAD)
    payload[field] = value
    _assert_execution_error("linear-regression", payload, field)


@pytest.mark.parametrize(
    ("payload", "field"),
    [
        ({"X": [[True], [1.0]], "y": [1.0, 2.0]}, "X[0][0]"),
        ({"X": [[1.0], [2.0]], "y": [True, 2.0]}, "y[0]"),
        ({"X": [[1.0], [float("nan")]], "y": [1.0, 2.0]}, "X[1][0]"),
        ({"X": [[1.0], [float("inf")]], "y": [1.0, 2.0]}, "X[1][0]"),
        ({"X": [[1.0], [2.0]], "y": [1.0, float("-inf")]}, "y[1]"),
        ({"X": [[1.0], [10**10000]], "y": [1.0, 2.0]}, "X[1][0]"),
        ({"X": [[1.0], [2.0]], "y": [1.0, 10**10000]}, "y[1]"),
        ({"X": [[1.0], [2.0]], "y": [1.0, 2.0], "predict_X": [[float("nan")]]}, "predict_X[0][0]"),
    ],
)
def test_supervised_numeric_inputs_reject_bool_nonfinite_and_oversized_values(
    payload: dict[str, object], field: str
) -> None:
    """Unsafe JSON numeric leaves must fail at their exact public field before NumPy coercion."""
    _assert_execution_error("linear-regression", payload, field)


@pytest.mark.parametrize(
    ("payload", "field"),
    [
        ({"X": [[1 + 2j]], "y": [1.0]}, "X[0][0]"),
        ({"X": [[np.float64(1.0)]], "y": [1.0]}, "X[0][0]"),
    ],
)
def test_supervised_payload_snapshot_rejects_complex_and_numeric_subclasses(
    payload: dict[str, object], field: str
) -> None:
    """Calling conversion hooks on non-JSON numeric objects would cross the trust boundary."""
    _assert_execution_error("linear-regression", payload, field)


def test_supervised_payload_snapshot_rejects_container_subclasses() -> None:
    """Dict/list subclass iteration hooks must never run inside the supervised boundary."""

    class DictSubclass(dict[str, object]):
        pass

    class ListSubclass(list[object]):
        pass

    with pytest.raises(
        ValueError,
        match=r"linear-regression: payload stage failed: payload must be a plain JSON object",
    ):
        execute("linear-regression", DictSubclass(X=[[1.0]], y=[1.0]))
    _assert_execution_error(
        "linear-regression",
        {"X": ListSubclass([[1.0]]), "y": [1.0]},
        "X",
    )
    _assert_execution_error(
        "linear-regression",
        {"X": [[1.0]], "y": [1.0], "params": DictSubclass()},
        "params",
    )


@pytest.mark.parametrize("model_id", ["linear-regression", "decision-tree", "logistic-regression"])
def test_supervised_models_reject_unknown_top_level_fields_without_mutation(model_id: str) -> None:
    """Silently ignoring a misspelled field would change the requested model configuration."""
    payload = _payload_for(model_id)
    payload["extra"] = {"nested": [1, 2, 3]}
    before = copy.deepcopy(payload)

    _assert_execution_error(model_id, payload, "extra")

    assert payload == before


@pytest.mark.parametrize("model_id", ["linear-regression", "decision-tree", "logistic-regression"])
def test_supervised_models_require_plain_params_objects(model_id: str) -> None:
    """An array of pairs or scalar params value must not be coerced into estimator kwargs."""
    payload = _payload_for(model_id)
    payload["params"] = []
    _assert_execution_error(model_id, payload, "params")


@pytest.mark.parametrize("model_id", ["linear-regression", "decision-tree", "logistic-regression"])
def test_supervised_parameter_allowlists_reject_unknown_names(model_id: str) -> None:
    """The public params object must not become an arbitrary sklearn kwargs tunnel."""
    payload = _payload_for(model_id)
    payload["params"] = {"bogus": 1}
    _assert_execution_error(model_id, payload, "params.bogus")


@pytest.mark.parametrize(
    ("model_id", "params", "field"),
    [
        ("linear-regression", {"fit_intercept": 1}, "params.fit_intercept"),
        ("linear-regression", {"tol": True}, "params.tol"),
        ("decision-tree", {"max_depth": 1.0}, "params.max_depth"),
        ("decision-tree", {"min_samples_split": True}, "params.min_samples_split"),
        ("decision-tree", {"criterion": 1}, "params.criterion"),
        ("logistic-regression", {"C": True}, "params.C"),
        ("logistic-regression", {"max_iter": 2.5}, "params.max_iter"),
        ("logistic-regression", {"solver": 1}, "params.solver"),
    ],
)
def test_supervised_parameter_allowlists_reject_unsafe_value_types(
    model_id: str, params: dict[str, object], field: str
) -> None:
    """Sklearn coercion must not reinterpret booleans or wrong scalar kinds as parameters."""
    payload = _payload_for(model_id)
    payload["params"] = params
    _assert_execution_error(model_id, payload, field)


@pytest.mark.parametrize(
    ("model_id", "params", "field"),
    [
        ("linear-regression", {"n_jobs": 10**100}, "params.n_jobs"),
        ("decision-tree", {"max_depth": 10**100}, "params.max_depth"),
        ("logistic-regression", {"max_iter": 10**100}, "params.max_iter"),
    ],
)
def test_supervised_parameters_reject_integers_too_large_for_sklearn(
    model_id: str, params: dict[str, object], field: str
) -> None:
    """Native estimator integer parameters cannot safely consume arbitrary-size JSON integers."""
    payload = _payload_for(model_id)
    payload["params"] = params
    _assert_execution_error(model_id, payload, field)


def test_classifier_labels_reject_integers_too_large_for_numpy() -> None:
    """Object-dtype giant integers must not be deferred to sklearn target-type inference."""
    payload = _payload_for("logistic-regression")
    payload["y"] = [0, 0, 10**100, 10**100]
    _assert_execution_error("logistic-regression", payload, "y[2]")


@pytest.mark.parametrize(
    ("model_id", "params", "expected"),
    [
        (
            "linear-regression",
            {"fit_intercept": False, "copy_X": True, "tol": 1e-5, "n_jobs": 1, "positive": False},
            {"fit_intercept": False, "copy_X": True, "tol": 1e-5, "n_jobs": 1, "positive": False},
        ),
        (
            "decision-tree",
            {
                "criterion": "entropy",
                "splitter": "best",
                "max_depth": 2,
                "min_samples_split": 2,
                "min_samples_leaf": 1,
                "max_features": 1,
                "max_leaf_nodes": 3,
                "min_impurity_decrease": 0.0,
                "ccp_alpha": 0.0,
            },
            {
                "criterion": "entropy",
                "splitter": "best",
                "max_depth": 2,
                "min_samples_split": 2,
                "min_samples_leaf": 1,
                "max_features": 1,
                "max_leaf_nodes": 3,
                "min_impurity_decrease": 0.0,
                "ccp_alpha": 0.0,
            },
        ),
        (
            "logistic-regression",
            {
                "C": 2.0,
                "tol": 1e-5,
                "fit_intercept": True,
                "intercept_scaling": 1.0,
                "solver": "liblinear",
                "max_iter": 500,
                "warm_start": False,
                "n_jobs": 1,
            },
            {
                "C": 2.0,
                "tol": 1e-5,
                "fit_intercept": True,
                "intercept_scaling": 1.0,
                "solver": "liblinear",
                "max_iter": 500,
                "warm_start": False,
                "n_jobs": 1,
            },
        ),
    ],
)
def test_supervised_safe_documented_parameters_are_applied_and_reported(
    model_id: str, params: dict[str, object], expected: dict[str, object]
) -> None:
    """Dropping an admitted parameter or reporting defaults as caller input breaks transparency."""
    payload = _payload_for(model_id)
    payload["params"] = params
    result = execute(model_id, payload)

    assert result["parameters"] == expected


def test_linear_regression_rejects_seed_because_legacy_factory_does_not_support_it() -> None:
    """Advertising an ignored seed for deterministic linear regression is misleading."""
    payload = copy.deepcopy(LINEAR_PAYLOAD)
    payload["seed"] = 7
    _assert_execution_error("linear-regression", payload, "seed")


@pytest.mark.parametrize("model_id", ["decision-tree", "logistic-regression"])
def test_seeded_classifiers_reject_invalid_seed_values(model_id: str) -> None:
    """A bool or out-of-range integer must not leak into sklearn random_state handling."""
    for seed in (True, -1, 2**32, 10**10000):
        payload = _payload_for(model_id)
        payload["seed"] = seed
        _assert_execution_error(model_id, payload, "seed")


@pytest.mark.parametrize("model_id", ["decision-tree", "logistic-regression"])
def test_seed_random_state_conflict_and_hidden_random_state_are_rejected(model_id: str) -> None:
    """All randomness must enter through the public top-level seed field."""
    conflict = _payload_for(model_id)
    conflict["params"] = {"random_state": 3}
    _assert_execution_error(model_id, conflict, "seed")

    hidden = _payload_for(model_id)
    del hidden["seed"]
    hidden["params"] = {"random_state": 3}
    _assert_execution_error(model_id, hidden, "params.random_state")


@pytest.mark.parametrize("model_id", ["decision-tree", "logistic-regression"])
def test_same_seed_produces_repeatable_classifier_results(model_id: str) -> None:
    """Failing to pass seed through the legacy factory would make repeated public results diverge."""
    payload = _payload_for(model_id)
    if model_id == "decision-tree":
        payload["params"] = {"max_depth": 2, "splitter": "random"}

    first = execute(model_id, payload)
    second = execute(model_id, payload)

    assert first == second
    assert first["reproducibility"]["seed"] == 7


def test_json_wrappers_resolve_and_call_legacy_factories(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Constructing a second estimator path would drift from legacy parameter and seed semantics."""
    calls: list[tuple[str, int | None, dict[str, object]]] = []

    class RecordingLinear:
        coef_ = np.array([2.0])
        intercept_ = 1.0

        def fit(self, X: np.ndarray, y: np.ndarray) -> RecordingLinear:
            return self

        def predict(self, X: np.ndarray) -> np.ndarray:
            return 2.0 * X[:, 0] + 1.0

    def fake_get_model(name: str):
        def factory(*, seed: int | None, params: dict[str, object]) -> RecordingLinear:
            calls.append((name, seed, dict(params)))
            return RecordingLinear()

        return factory

    monkeypatch.setattr(legacy_registry, "get_model", fake_get_model)
    result = execute(
        "linear-regression",
        {**copy.deepcopy(LINEAR_PAYLOAD), "params": {"fit_intercept": True}},
    )

    assert calls == [("linear-regression", None, {"fit_intercept": True})]
    assert result["result"]["predictions"] == pytest.approx([9.0])


def test_logistic_factory_is_registered_with_legacy_seed_semantics() -> None:
    """A JSON-only constructor would leave run_model and registry users on divergent behavior."""
    factory = get_model("logistic-regression")
    estimator = factory(seed=7, params={"C": 0.5})

    assert isinstance(estimator, LogisticRegression)
    assert estimator.get_params()["C"] == 0.5
    assert estimator.get_params()["random_state"] == 7
    with pytest.raises(ValueError, match="conflict: both seed and random_state provided"):
        factory(seed=7, params={"random_state": 3})


def test_existing_linear_model_new_and_old_interfaces_coexist() -> None:
    """The JSON envelope must not replace the estimator-returning legacy result."""
    legacy = run_model("linear-regression", [[1], [2], [3]], [3, 5, 7])
    modern = execute("linear-regression", copy.deepcopy(LINEAR_PAYLOAD))

    assert set(legacy) == {"model", "fitted", "params", "seed"}
    assert legacy["model"] == "linear-regression"
    assert hasattr(legacy["fitted"], "predict")
    assert modern["result"]["predictions"] == pytest.approx([9.0])
    assert "fitted" not in modern["result"]


def test_logistic_regression_legacy_and_json_interfaces_coexist() -> None:
    """Registering logistic regression must preserve the old object-return interface shape."""
    legacy = run_model(
        "logistic-regression",
        LOGISTIC_PAYLOAD["X"],
        LOGISTIC_PAYLOAD["y"],
        seed=7,
        params={"solver": "liblinear", "max_iter": 1000},
    )
    modern = execute("logistic-regression", copy.deepcopy(LOGISTIC_PAYLOAD))

    assert set(legacy) == {"model", "fitted", "params", "seed"}
    assert isinstance(legacy["fitted"], LogisticRegression)
    assert modern["result"]["classes"] == legacy["fitted"].classes_.tolist()
    _assert_no_estimator(modern)


def test_model_construction_failures_are_translated(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Raw sklearn constructor text must retain a stable params field and execution stage."""
    monkeypatch.setattr(
        legacy_registry,
        "get_model",
        lambda name: lambda *, seed, params: (_ for _ in ()).throw(TypeError("bad option")),
    )
    _assert_execution_error("linear-regression", LINEAR_PAYLOAD, "params")


def test_fit_failures_and_their_warnings_are_translated_without_leakage(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Handled sklearn fit failures must not emit partial results or numerical warnings."""

    class BrokenFit:
        def fit(self, X: np.ndarray, y: np.ndarray) -> None:
            warnings.warn("overflow while fitting", RuntimeWarning)
            raise ValueError("cannot fit")

    monkeypatch.setattr(
        legacy_registry,
        "get_model",
        lambda name: lambda *, seed, params: BrokenFit(),
    )
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        _assert_execution_error("linear-regression", LINEAR_PAYLOAD, "fit")
    assert caught == []


def test_predict_failures_and_their_warnings_are_translated_without_leakage(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Handled sklearn prediction failures must retain a stable prediction field."""

    class BrokenPredict:
        coef_ = np.array([1.0])
        intercept_ = 0.0

        def fit(self, X: np.ndarray, y: np.ndarray) -> BrokenPredict:
            return self

        def predict(self, X: np.ndarray) -> np.ndarray:
            warnings.warn("invalid prediction", RuntimeWarning)
            raise RuntimeError("cannot predict")

    monkeypatch.setattr(
        legacy_registry,
        "get_model",
        lambda name: lambda *, seed, params: BrokenPredict(),
    )
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        _assert_execution_error("linear-regression", LINEAR_PAYLOAD, "prediction")
    assert caught == []


def test_probability_failures_and_their_warnings_are_translated_without_leakage(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Handled predict_proba failures must not leak warnings or a labels-only partial result."""

    class BrokenProbability:
        classes_ = np.array(["high", "low"])
        feature_importances_ = np.array([1.0])

        def fit(self, X: np.ndarray, y: np.ndarray) -> BrokenProbability:
            return self

        def predict(self, X: np.ndarray) -> np.ndarray:
            return np.array(["low"] * X.shape[0])

        def predict_proba(self, X: np.ndarray) -> np.ndarray:
            warnings.warn("invalid probability", RuntimeWarning)
            raise RuntimeError("cannot calculate probabilities")

        def get_depth(self) -> int:
            return 1

    monkeypatch.setattr(
        legacy_registry,
        "get_model",
        lambda name: lambda *, seed, params: BrokenProbability(),
    )
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        _assert_execution_error("decision-tree", TREE_PAYLOAD, "probabilities")
    assert caught == []


def test_programming_defects_are_not_misreported_as_user_input_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Catching every Exception would conceal an executor/estimator integration defect."""

    class DefectiveFit:
        def fit(self, X: np.ndarray, y: np.ndarray) -> None:
            raise KeyError("internal invariant")

    monkeypatch.setattr(
        legacy_registry,
        "get_model",
        lambda name: lambda *, seed, params: DefectiveFit(),
    )
    with pytest.raises(KeyError, match="internal invariant"):
        execute("linear-regression", copy.deepcopy(LINEAR_PAYLOAD))


def test_nonfinite_predictions_fail_closed_without_warning(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A fitted estimator returning infinity must never reach result normalization as success."""

    class NonfinitePrediction:
        coef_ = np.array([1.0])
        intercept_ = 0.0

        def fit(self, X: np.ndarray, y: np.ndarray) -> NonfinitePrediction:
            return self

        def predict(self, X: np.ndarray) -> np.ndarray:
            return np.full(X.shape[0], np.inf)

    monkeypatch.setattr(
        legacy_registry,
        "get_model",
        lambda name: lambda *, seed, params: NonfinitePrediction(),
    )
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        _assert_execution_error("linear-regression", LINEAR_PAYLOAD, "training_predictions")
    assert caught == []


def test_nonfinite_fitted_attributes_fail_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Estimator coefficients are result data and must receive the same finite checks as predictions."""

    class NonfiniteCoefficient:
        coef_ = np.array([np.nan])
        intercept_ = 0.0

        def fit(self, X: np.ndarray, y: np.ndarray) -> NonfiniteCoefficient:
            return self

        def predict(self, X: np.ndarray) -> np.ndarray:
            return np.zeros(X.shape[0])

    monkeypatch.setattr(
        legacy_registry,
        "get_model",
        lambda name: lambda *, seed, params: NonfiniteCoefficient(),
    )
    _assert_execution_error("linear-regression", LINEAR_PAYLOAD, "coefficients")


def test_nonfinite_metric_arithmetic_fails_closed_without_warning(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Finite predictions whose residual subtraction overflows must not leak RuntimeWarning or inf."""

    class OverflowingResiduals:
        coef_ = np.array([1.0])
        intercept_ = 0.0

        def fit(self, X: np.ndarray, y: np.ndarray) -> OverflowingResiduals:
            return self

        def predict(self, X: np.ndarray) -> np.ndarray:
            values = np.array([np.finfo(float).max, -np.finfo(float).max, 0.0])
            return values[: X.shape[0]]

    monkeypatch.setattr(
        legacy_registry,
        "get_model",
        lambda name: lambda *, seed, params: OverflowingResiduals(),
    )
    payload = {"X": [[0.0], [1.0], [2.0]], "y": [-1.0, 1.0, 0.0]}
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        _assert_execution_error("linear-regression", payload, "metrics")
    assert caught == []


@pytest.mark.parametrize("bad_probabilities", [[[0.4, 0.4]], [[float("nan"), 1.0]]])
def test_invalid_probability_results_fail_closed(
    monkeypatch: pytest.MonkeyPatch, bad_probabilities: list[list[float]]
) -> None:
    """Probabilities must be finite, class-aligned, bounded, and normalized before success."""

    class InvalidProbability:
        classes_ = np.array(["high", "low"])
        feature_importances_ = np.array([1.0])

        def fit(self, X: np.ndarray, y: np.ndarray) -> InvalidProbability:
            return self

        def predict(self, X: np.ndarray) -> np.ndarray:
            return np.array(["low"] * X.shape[0])

        def predict_proba(self, X: np.ndarray) -> np.ndarray:
            return np.asarray(bad_probabilities * X.shape[0], dtype=float)

        def get_depth(self) -> int:
            return 1

    monkeypatch.setattr(
        legacy_registry,
        "get_model",
        lambda name: lambda *, seed, params: InvalidProbability(),
    )
    _assert_execution_error("decision-tree", TREE_PAYLOAD, "probabilities")


def test_real_extreme_scale_fit_fails_closed_without_warning() -> None:
    """An overflow-prone but finite training matrix must fail before LAPACK/sklearn warnings leak."""
    payload = {
        "X": [[1e308], [-1e308], [5e307]],
        "y": [1.0, -1.0, 0.5],
    }
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        _assert_execution_error("linear-regression", payload, "X")
    assert caught == []


@pytest.mark.parametrize(
    ("model_id", "payload", "card", "deterministic", "seed_supported"),
    [
        (
            "linear-regression",
            LINEAR_PAYLOAD,
            "shared/knowledge/model-cards/prediction/linear-regression.md",
            True,
            False,
        ),
        (
            "decision-tree",
            TREE_PAYLOAD,
            "shared/knowledge/model-cards/classification/decision-tree.md",
            False,
            True,
        ),
        (
            "logistic-regression",
            LOGISTIC_PAYLOAD,
            "shared/knowledge/model-cards/classification/logistic-regression.md",
            False,
            True,
        ),
    ],
)
def test_supervised_capabilities_are_registered_with_real_cards_and_isolated_metadata(
    project_root: Path,
    model_id: str,
    payload: dict[str, object],
    card: str,
    deterministic: bool,
    seed_supported: bool,
) -> None:
    """Wrong executor, seed facts, payload fields, or card paths would misroute public capability users."""
    capabilities = {item["model_id"]: item for item in list_capabilities()}
    capability = capabilities[model_id]

    assert capability == {
        "model_id": model_id,
        "executor": "supervised",
        "knowledge_card": card,
        "deterministic": deterministic,
        "seed_supported": seed_supported,
        "payload_fields": ("X", "y"),
    }
    assert (project_root / card).is_file()
    assert get_spec(model_id).function is not None
    result = execute(model_id, copy.deepcopy(payload))
    assert result["executor"] == "supervised"
    assert result["reproducibility"]["deterministic"] is deterministic

    capability["payload_fields"] = ("tampered",)
    assert get_spec(model_id).payload_fields == ("X", "y")


def test_supervised_knowledge_cards_match_catalog_metadata(project_root: Path) -> None:
    """A real path with stale catalog identity would still break capability documentation lookup."""
    catalog = yaml.safe_load(
        (project_root / "shared/knowledge/model-catalog.yaml").read_text(encoding="utf-8")
    )
    entries = {entry["model_id"]: entry for entry in catalog["cards"]}

    for model_id in ("linear-regression", "decision-tree", "logistic-regression"):
        spec = get_spec(model_id)
        card_text = (project_root / spec.knowledge_card).read_text(encoding="utf-8")
        assert f"model_id: {model_id}" in card_text
        assert f"file: {spec.knowledge_card}" in card_text
        assert entries[model_id]["file"] == spec.knowledge_card


@pytest.mark.parametrize("missing", ["X", "y"])
def test_supervised_missing_required_fields_fail_at_payload_fields_stage(missing: str) -> None:
    """A generic unknown-model error must never satisfy required-field coverage during RED."""
    payload = copy.deepcopy(LINEAR_PAYLOAD)
    del payload[missing]
    with pytest.raises(
        ValueError,
        match=rf"linear-regression: payload fields stage failed: missing {missing}",
    ):
        execute("linear-regression", payload)
