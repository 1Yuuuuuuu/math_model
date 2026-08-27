"""Plain-JSON wrappers around the legacy supervised estimator factories."""

from __future__ import annotations

import json
import math
import sys
import warnings
from collections.abc import Callable, Mapping
from typing import TypeVar

import numpy as np
from sklearn.exceptions import ConvergenceWarning
from sklearn.linear_model import LogisticRegression

from .. import registry as legacy_registry
from .base import json_finite_number, required_field


_ModelResult = TypeVar("_ModelResult")
_HANDLED_ESTIMATOR_ERRORS = (
    TypeError,
    ValueError,
    RuntimeError,
    OverflowError,
    FloatingPointError,
    np.linalg.LinAlgError,
)
_MODEL_IDS = frozenset(
    {"linear-regression", "decision-tree", "logistic-regression"}
)
_COMMON_FIELDS = frozenset({"X", "y", "predict_X", "params"})
_SEEDED_FIELDS = _COMMON_FIELDS | {"seed"}
_LINEAR_PARAMS = frozenset({"fit_intercept", "copy_X", "n_jobs", "positive"})
_TREE_PARAMS = frozenset(
    {
        "criterion",
        "splitter",
        "max_depth",
        "min_samples_split",
        "min_samples_leaf",
        "min_weight_fraction_leaf",
        "max_features",
        "max_leaf_nodes",
        "min_impurity_decrease",
        "class_weight",
        "ccp_alpha",
        "monotonic_cst",
    }
)
_LOGISTIC_PARAMS = frozenset(
    {
        "penalty",
        "C",
        "l1_ratio",
        "dual",
        "tol",
        "fit_intercept",
        "intercept_scaling",
        "class_weight",
        "solver",
        "max_iter",
        "verbose",
        "warm_start",
        "n_jobs",
    }
)
_PROBABILITY_TOLERANCE = 1e-12


def _logistic_factory(seed: int | None, params: dict[str, object]) -> object:
    """Construct logistic regression with the legacy random-state convention."""
    return LogisticRegression(**legacy_registry._seed_kwargs(seed, params))


legacy_registry.register_model("logistic-regression", _logistic_factory)


def _exact_finite_number(value: object, field: str) -> float:
    """Convert a JSON number only when an integer survives binary64 exactly."""
    number = float(json_finite_number(value, field))
    if type(value) is int and int(number) != value:
        raise ValueError(
            f"{field}: integer cannot be represented exactly as a floating-point number"
        )
    return number


def _reject_unknown_fields(
    payload: Mapping[str, object], model_id: str
) -> None:
    allowed = _COMMON_FIELDS if model_id == "linear-regression" else _SEEDED_FIELDS
    unknown = sorted(set(payload) - allowed)
    if unknown:
        raise ValueError(f"{unknown[0]}: is not a supported payload field")


def _finite_matrix(payload: Mapping[str, object], field: str) -> np.ndarray:
    value = required_field(payload, field)
    if type(value) is not list or not value:
        raise ValueError(f"{field}: must be a nonempty plain JSON two-dimensional array")

    rows: list[list[float]] = []
    width: int | None = None
    for row_index, row in enumerate(value):
        if type(row) is not list or not row:
            raise ValueError(
                f"{field}[{row_index}]: must be a nonempty plain JSON array"
            )
        if width is None:
            width = len(row)
        elif len(row) != width:
            raise ValueError(f"{field}: must be a rectangular two-dimensional array")
        rows.append(
            [
                _exact_finite_number(
                    item, f"{field}[{row_index}][{column_index}]"
                )
                for column_index, item in enumerate(row)
            ]
        )

    try:
        matrix = np.asarray(rows, dtype=float)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f"{field}: must contain safely representable finite numbers") from exc
    if matrix.ndim != 2 or matrix.shape[0] == 0 or matrix.shape[1] == 0:
        raise ValueError(f"{field}: must be a nonempty two-dimensional array")
    if not np.all(np.isfinite(matrix)):
        raise ValueError(f"{field}: must contain only finite numbers")
    return matrix


def _regression_target(payload: Mapping[str, object]) -> tuple[np.ndarray, list[float]]:
    value = required_field(payload, "y")
    if type(value) is not list or not value:
        raise ValueError("y: must be a nonempty plain JSON one-dimensional array")
    normalized = [
        _exact_finite_number(item, f"y[{index}]")
        for index, item in enumerate(value)
    ]
    try:
        target = np.asarray(normalized, dtype=float)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("y: must contain safely representable finite numbers") from exc
    if target.ndim != 1 or not np.all(np.isfinite(target)):
        raise ValueError("y: must be a finite one-dimensional numeric array")
    return target, normalized


def _classification_label(value: object, field: str) -> str | int | float:
    if type(value) is str:
        return value
    if type(value) is int:
        json_finite_number(value, field)
        if value < -sys.maxsize - 1 or value > sys.maxsize:
            raise ValueError(
                f"{field}: integer is outside the safely representable native range"
            )
        return value
    if type(value) is float:
        number = float(json_finite_number(value, field))
        if not number.is_integer():
            raise ValueError(
                f"{field}: numeric classifier labels must be integer-valued"
            )
        return number
    raise ValueError(f"{field}: must be a plain JSON string or finite number")


def _classification_target(
    payload: Mapping[str, object],
) -> tuple[np.ndarray, list[str | int | float]]:
    value = required_field(payload, "y")
    if type(value) is not list or not value:
        raise ValueError("y: must be a nonempty plain JSON one-dimensional array")
    normalized = [
        _classification_label(item, f"y[{index}]")
        for index, item in enumerate(value)
    ]
    has_strings = any(type(item) is str for item in normalized)
    if has_strings and not all(type(item) is str for item in normalized):
        raise ValueError("y: must not mix string and numeric class labels")
    try:
        target = np.asarray(normalized)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("y: must contain safely representable class labels") from exc
    if target.ndim != 1:
        raise ValueError("y: must be a one-dimensional class-label array")
    try:
        class_count = int(np.unique(target).size)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("y: class labels cannot be ordered safely") from exc
    if class_count < 2:
        raise ValueError("y: classifiers require at least two target classes")
    return target, normalized


def _safe_numeric_scale(array: np.ndarray, field: str) -> None:
    """Reject magnitudes that make common centered least-squares paths overflow."""
    scale = float(np.max(np.abs(array)))
    safe_upper = math.sqrt(sys.float_info.max / max(1, int(array.size))) / 16.0
    if scale > safe_upper:
        raise ValueError(f"{field}: scale is outside the safe finite fitting range")


def _plain_bool(value: object, field: str) -> bool:
    if type(value) is not bool:
        raise ValueError(f"{field}: must be a built-in boolean")
    return value


def _plain_integer(
    value: object,
    field: str,
    *,
    minimum: int | None = None,
    maximum: int | None = None,
) -> int:
    if type(value) is not int:
        raise ValueError(f"{field}: must be a built-in integer")
    if value < -sys.maxsize - 1 or value > sys.maxsize:
        raise ValueError(
            f"{field}: integer is outside the safely representable native range"
        )
    if minimum is not None and value < minimum:
        raise ValueError(f"{field}: must be at least {minimum}")
    if maximum is not None and value > maximum:
        raise ValueError(f"{field}: must be at most {maximum}")
    return value


def _finite_parameter(
    value: object,
    field: str,
    *,
    minimum: float | None = None,
    maximum: float | None = None,
    exclusive_minimum: bool = False,
) -> float:
    number = _exact_finite_number(value, field)
    if minimum is not None and (
        number < minimum or (exclusive_minimum and number == minimum)
    ):
        comparator = "greater than" if exclusive_minimum else "at least"
        raise ValueError(f"{field}: must be {comparator} {minimum}")
    if maximum is not None and number > maximum:
        raise ValueError(f"{field}: must be at most {maximum}")
    return number


def _plain_enum(value: object, field: str, choices: frozenset[str]) -> str:
    if type(value) is not str or value not in choices:
        raise ValueError(f"{field}: must be one of {', '.join(sorted(choices))}")
    return value


def _n_jobs(value: object, field: str) -> int | None:
    if value is None:
        return None
    result = _plain_integer(value, field)
    if result == 0:
        raise ValueError(f"{field}: must be nonzero or null")
    return result


def _class_weight(value: object, field: str) -> object:
    if value is None or value == "balanced":
        return value
    if type(value) is not dict:
        raise ValueError(f"{field}: must be 'balanced', null, or a plain JSON object")
    weights: dict[str, float] = {}
    for label, weight in dict.items(value):
        if type(label) is not str:
            raise ValueError(f"{field}: class keys must be strings")
        weights[label] = _finite_parameter(
            weight, f"{field}.{label}", minimum=0.0
        )
    if not weights:
        raise ValueError(f"{field}: class-weight object must not be empty")
    return weights


def _native_class_weight(
    weights: dict[str, float], classes: list[str | int | float], field: str
) -> dict[str | int | float, float]:
    """Map JSON object keys to the exact normalized estimator classes."""
    mapped: dict[str | int | float, float] = {}
    string_classes = all(type(label) is str for label in classes)
    for key, weight in weights.items():
        if string_classes:
            candidate: object = key
        else:
            try:
                candidate = json.loads(
                    key,
                    parse_constant=lambda value: (_ for _ in ()).throw(
                        ValueError(value)
                    ),
                )
            except (TypeError, ValueError, json.JSONDecodeError) as exc:
                raise ValueError(
                    f"{field}: numeric class keys must be JSON numbers"
                ) from exc
            if type(candidate) not in (int, float) or (
                type(candidate) is float and not math.isfinite(candidate)
            ):
                raise ValueError(
                    f"{field}: numeric class keys must be finite JSON numbers"
                )

        matches = [label for label in classes if candidate == label]
        if len(matches) != 1:
            raise ValueError(f"{field}: class key {key!r} does not match a target class")
        actual = matches[0]
        if actual in mapped:
            raise ValueError(f"{field}: multiple keys map to the same target class")
        mapped[actual] = weight

    if len(mapped) != len(classes):
        raise ValueError(f"{field}: class keys must cover every target class")
    return mapped


def _validate_linear_params(params: dict[str, object]) -> dict[str, object]:
    normalized: dict[str, object] = {}
    for name, value in dict.items(params):
        field = f"params.{name}"
        if name not in _LINEAR_PARAMS:
            raise ValueError(f"{field}: is not a supported parameter")
        if name in {"fit_intercept", "copy_X", "positive"}:
            normalized[name] = _plain_bool(value, field)
        else:
            normalized[name] = _n_jobs(value, field)
    return normalized


def _tree_fraction_or_count(
    value: object, field: str, *, integer_minimum: int, allow_one: bool
) -> int | float:
    if type(value) is int:
        return _plain_integer(value, field, minimum=integer_minimum)
    number = _finite_parameter(
        value, field, minimum=0.0, maximum=1.0, exclusive_minimum=True
    )
    if not allow_one and number == 1.0:
        raise ValueError(f"{field}: fractional form must be less than 1.0")
    return number


def _validate_tree_params(
    params: dict[str, object], feature_count: int
) -> dict[str, object]:
    normalized: dict[str, object] = {}
    for name, value in dict.items(params):
        field = f"params.{name}"
        if name == "random_state":
            raise ValueError(f"{field}: use top-level seed instead")
        if name not in _TREE_PARAMS:
            raise ValueError(f"{field}: is not a supported parameter")
        if name == "criterion":
            normalized[name] = _plain_enum(
                value, field, frozenset({"gini", "entropy", "log_loss"})
            )
        elif name == "splitter":
            normalized[name] = _plain_enum(
                value, field, frozenset({"best", "random"})
            )
        elif name == "max_depth":
            normalized[name] = (
                None if value is None else _plain_integer(value, field, minimum=1)
            )
        elif name == "min_samples_split":
            normalized[name] = _tree_fraction_or_count(
                value, field, integer_minimum=2, allow_one=True
            )
        elif name == "min_samples_leaf":
            normalized[name] = _tree_fraction_or_count(
                value, field, integer_minimum=1, allow_one=False
            )
        elif name == "min_weight_fraction_leaf":
            normalized[name] = _finite_parameter(
                value, field, minimum=0.0, maximum=0.5
            )
        elif name == "max_features":
            if value is None:
                normalized[name] = None
            elif type(value) is int:
                normalized[name] = _plain_integer(
                    value, field, minimum=1, maximum=feature_count
                )
            elif type(value) in (float,):
                normalized[name] = _finite_parameter(
                    value,
                    field,
                    minimum=0.0,
                    maximum=1.0,
                    exclusive_minimum=True,
                )
            else:
                normalized[name] = _plain_enum(
                    value, field, frozenset({"sqrt", "log2"})
                )
        elif name == "max_leaf_nodes":
            normalized[name] = (
                None if value is None else _plain_integer(value, field, minimum=2)
            )
        elif name in {"min_impurity_decrease", "ccp_alpha"}:
            normalized[name] = _finite_parameter(value, field, minimum=0.0)
        elif name == "class_weight":
            normalized[name] = _class_weight(value, field)
        else:
            if value is None:
                normalized[name] = None
            elif type(value) is not list or len(value) != feature_count:
                raise ValueError(
                    f"{field}: must be null or contain one constraint per feature"
                )
            else:
                normalized[name] = [
                    _plain_integer(item, f"{field}[{index}]", minimum=-1, maximum=1)
                    for index, item in enumerate(value)
                ]
    return normalized


def _validate_logistic_params(params: dict[str, object]) -> dict[str, object]:
    normalized: dict[str, object] = {}
    for name, value in dict.items(params):
        field = f"params.{name}"
        if name == "random_state":
            raise ValueError(f"{field}: use top-level seed instead")
        if name not in _LOGISTIC_PARAMS:
            raise ValueError(f"{field}: is not a supported parameter")
        if name == "penalty":
            if value is None:
                normalized[name] = None
            else:
                normalized[name] = _plain_enum(
                    value, field, frozenset({"l1", "l2", "elasticnet"})
                )
        elif name in {"C", "tol", "intercept_scaling"}:
            normalized[name] = _finite_parameter(
                value, field, minimum=0.0, exclusive_minimum=True
            )
        elif name == "l1_ratio":
            normalized[name] = _finite_parameter(
                value, field, minimum=0.0, maximum=1.0
            )
        elif name in {"dual", "fit_intercept", "warm_start"}:
            normalized[name] = _plain_bool(value, field)
        elif name == "class_weight":
            normalized[name] = _class_weight(value, field)
        elif name == "solver":
            normalized[name] = _plain_enum(
                value,
                field,
                frozenset(
                    {
                        "lbfgs",
                        "liblinear",
                        "newton-cg",
                        "newton-cholesky",
                        "sag",
                        "saga",
                    }
                ),
            )
        elif name in {"max_iter", "verbose"}:
            normalized[name] = _plain_integer(
                value, field, minimum=1 if name == "max_iter" else 0
            )
        else:
            normalized[name] = _n_jobs(value, field)
    return normalized


def _validated_params(
    payload: Mapping[str, object],
    model_id: str,
    feature_count: int,
    classes: list[str | int | float] | None,
) -> tuple[dict[str, object], dict[str, object]]:
    raw = payload.get("params", {})
    if type(raw) is not dict:
        raise ValueError("params: must be a plain JSON object")
    if "random_state" in raw and payload.get("seed") is not None:
        raise ValueError("seed: conflicts with params.random_state")
    if model_id == "linear-regression":
        public = _validate_linear_params(raw)
    elif model_id == "decision-tree":
        public = _validate_tree_params(raw, feature_count)
    else:
        public = _validate_logistic_params(raw)

    factory = dict(public)
    class_weight = public.get("class_weight")
    if type(class_weight) is dict:
        assert classes is not None
        factory["class_weight"] = _native_class_weight(
            class_weight, classes, "params.class_weight"
        )
    return public, factory


def _validated_seed(payload: Mapping[str, object], model_id: str) -> int | None:
    if model_id == "linear-regression":
        if "seed" in payload:
            raise ValueError("seed: is not supported for linear-regression")
        return None
    if "seed" not in payload or payload["seed"] is None:
        return None
    return _plain_integer(
        payload["seed"], "seed", minimum=0, maximum=2**32 - 1
    )


def _warning_summary(stage: str, captured: list[warnings.WarningMessage]) -> list[str]:
    summaries: list[str] = []
    for item in captured:
        if issubclass(item.category, ConvergenceWarning):
            summaries.append(
                f"{stage} emitted a convergence warning; review max_iter and feature scaling"
            )
        elif issubclass(item.category, RuntimeWarning):
            summaries.append(f"{stage} emitted a numerical runtime warning")
        else:
            summaries.append(f"{stage} emitted {item.category.__name__}")
    return sorted(set(summaries))


def _safe_estimator_call(
    stage: str, function: Callable[[], _ModelResult]
) -> tuple[_ModelResult, list[str]]:
    captured: list[warnings.WarningMessage]
    failure: Exception | None = None
    result: _ModelResult | None = None
    with warnings.catch_warnings(record=True) as captured:
        warnings.simplefilter("always")
        with np.errstate(all="ignore"):
            try:
                result = function()
            except _HANDLED_ESTIMATOR_ERRORS as exc:
                failure = exc
    if failure is not None:
        action = {
            "params": "model construction",
            "fit": "model fitting",
            "prediction": "model prediction",
            "probabilities": "probability prediction",
            "fitted attributes": "fitted attribute extraction",
        }.get(stage, stage)
        raise ValueError(f"{stage}: {action} failed: {failure}") from failure
    return result, _warning_summary(stage, captured)  # type: ignore[return-value]


def _construct_estimator(
    model_id: str, seed: int | None, params: dict[str, object]
) -> tuple[object, list[str]]:
    factory = legacy_registry.get_model(model_id)
    return _safe_estimator_call(
        "params", lambda: factory(seed=seed, params=dict(params))
    )


def _finite_output_array(
    value: object,
    field: str,
    *,
    ndim: int,
    shape: tuple[int, ...] | None = None,
) -> np.ndarray:
    try:
        array = np.asarray(value, dtype=float)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f"{field}: model output must be a finite numeric array") from exc
    if array.ndim != ndim or (shape is not None and array.shape != shape):
        raise ValueError(f"{field}: model output has an unexpected shape")
    if not np.all(np.isfinite(array)):
        raise ValueError(f"{field}: model produced non-finite values")
    return array


def _output_label(value: object, field: str) -> str | int | float:
    if isinstance(value, np.generic):
        value = value.item()
    return _classification_label(value, field)


def _label_output_array(value: object, field: str, length: int) -> list[object]:
    try:
        array = np.asarray(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f"{field}: model output must be a one-dimensional label array") from exc
    if array.ndim != 1 or array.size != length:
        raise ValueError(f"{field}: model output has an unexpected shape")
    return [
        _output_label(item, f"{field}[{index}]")
        for index, item in enumerate(array)
    ]


def _regression_metrics(
    target: np.ndarray, predictions: np.ndarray
) -> tuple[float, float, float, str]:
    with warnings.catch_warnings(record=True):
        warnings.simplefilter("always")
        with np.errstate(
            over="ignore", under="ignore", invalid="ignore", divide="ignore"
        ):
            residuals = target - predictions
            if not np.all(np.isfinite(residuals)):
                raise ValueError("metrics: residual calculation produced non-finite values")
            residual_scale = float(np.max(np.abs(residuals)))
            if residual_scale == 0.0:
                rmse = 0.0
                mae = 0.0
            else:
                scaled_residuals = residuals / residual_scale
                rmse = residual_scale * math.sqrt(
                    float(np.mean(scaled_residuals**2))
                )
                mae = residual_scale * float(np.mean(np.abs(scaled_residuals)))

            if np.all(target == target[0]):
                r_squared = 1.0 if residual_scale == 0.0 else 0.0
                definition = (
                    "1 for a numerically perfect constant-target fit; otherwise 0"
                )
            else:
                target_scale = float(np.max(np.abs(target)))
                scaled_target = target / target_scale if target_scale else target
                centered = scaled_target - float(np.mean(scaled_target))
                scaled_residuals = (
                    residuals / target_scale if target_scale else residuals
                )
                target_ss = float(np.sum(centered**2))
                residual_ss = float(np.sum(scaled_residuals**2))
                if target_ss == 0.0:
                    raise ValueError("metrics: target variation is numerically unresolved")
                r_squared = 1.0 - residual_ss / target_ss
                definition = (
                    "1 - residual sum of squares / target total sum of squares"
                )
    if not all(math.isfinite(value) for value in (rmse, mae, r_squared)):
        raise ValueError("metrics: model produced non-finite values")
    return rmse, mae, r_squared, definition


def _classes(estimator: object) -> list[object]:
    try:
        values = getattr(estimator, "classes_")
    except AttributeError as exc:
        raise ValueError("classes: fitted estimator did not expose classes") from exc
    classes = _label_output_array(values, "classes", int(np.asarray(values).size))
    if len(classes) < 2:
        raise ValueError("classes: fitted estimator returned fewer than two classes")
    return classes


def _probabilities(
    estimator: object, predict_X: np.ndarray, class_count: int
) -> tuple[list[list[float]], list[str]]:
    values, call_warnings = _safe_estimator_call(
        "probabilities", lambda: estimator.predict_proba(predict_X)  # type: ignore[attr-defined]
    )
    probabilities = _finite_output_array(
        values,
        "probabilities",
        ndim=2,
        shape=(predict_X.shape[0], class_count),
    )
    if np.any(probabilities < 0.0) or np.any(probabilities > 1.0):
        raise ValueError("probabilities: values must be between zero and one")
    row_sums = np.sum(probabilities, axis=1)
    if not np.allclose(
        row_sums,
        np.ones(row_sums.shape, dtype=float),
        rtol=_PROBABILITY_TOLERANCE,
        atol=_PROBABILITY_TOLERANCE,
    ):
        raise ValueError(
            "probabilities: every row must sum to one within tolerance 1e-12"
        )
    return probabilities.tolist(), call_warnings


def _execute_linear(
    estimator: object,
    X: np.ndarray,
    target: np.ndarray,
    predict_X: np.ndarray | None,
) -> tuple[dict[str, object], dict[str, object], list[str]]:
    training_raw, warning_messages = _safe_estimator_call(
        "prediction", lambda: estimator.predict(X)  # type: ignore[attr-defined]
    )
    training_predictions = _finite_output_array(
        training_raw,
        "training_predictions",
        ndim=1,
        shape=(X.shape[0],),
    )
    attributes_raw, attribute_warnings = _safe_estimator_call(
        "fitted attributes",
        lambda: (getattr(estimator, "coef_"), getattr(estimator, "intercept_")),
    )
    coefficients = _finite_output_array(
        attributes_raw[0],
        "coefficients",
        ndim=1,
        shape=(X.shape[1],),
    )
    intercept_array = _finite_output_array(
        [attributes_raw[1]], "intercept", ndim=1, shape=(1,)
    )
    rmse, mae, r_squared, definition = _regression_metrics(
        target, training_predictions
    )
    result: dict[str, object] = {
        "training_predictions": training_predictions.tolist(),
        "coefficients": coefficients.tolist(),
        "intercept": float(intercept_array[0]),
        "rmse": rmse,
        "mae": mae,
        "r_squared": r_squared,
    }
    if predict_X is not None:
        predicted_raw, prediction_warnings = _safe_estimator_call(
            "prediction", lambda: estimator.predict(predict_X)  # type: ignore[attr-defined]
        )
        predicted = _finite_output_array(
            predicted_raw,
            "predictions",
            ndim=1,
            shape=(predict_X.shape[0],),
        )
        result["predictions"] = predicted.tolist()
        warning_messages.extend(prediction_warnings)
    return (
        result,
        {"r_squared_definition": definition},
        warning_messages + attribute_warnings,
    )


def _execute_classifier(
    model_id: str,
    estimator: object,
    X: np.ndarray,
    target_labels: list[str | int | float],
    predict_X: np.ndarray | None,
) -> tuple[dict[str, object], dict[str, object], list[str]]:
    training_raw, warning_messages = _safe_estimator_call(
        "prediction", lambda: estimator.predict(X)  # type: ignore[attr-defined]
    )
    training_predictions = _label_output_array(
        training_raw, "training_predictions", X.shape[0]
    )
    classes = _classes(estimator)
    accuracy = sum(
        predicted == actual
        for predicted, actual in zip(training_predictions, target_labels)
    ) / len(target_labels)
    if not math.isfinite(accuracy):
        raise ValueError("accuracy: model produced a non-finite metric")

    result: dict[str, object] = {
        "training_predictions": training_predictions,
        "classes": classes,
        "accuracy": accuracy,
    }
    if model_id == "decision-tree":
        attributes_raw, attribute_warnings = _safe_estimator_call(
            "fitted attributes",
            lambda: (
                getattr(estimator, "feature_importances_"),
                estimator.get_depth(),  # type: ignore[attr-defined]
            ),
        )
        importances = _finite_output_array(
            attributes_raw[0],
            "feature_importances",
            ndim=1,
            shape=(X.shape[1],),
        )
        depth = attributes_raw[1]
        if type(depth) not in (int, np.int64, np.int32) or int(depth) < 0:
            raise ValueError("tree_depth: fitted estimator returned an invalid depth")
        result["feature_importances"] = importances.tolist()
        result["tree_depth"] = int(depth)
    else:
        attributes_raw, attribute_warnings = _safe_estimator_call(
            "fitted attributes",
            lambda: (getattr(estimator, "coef_"), getattr(estimator, "intercept_")),
        )
        coefficients = _finite_output_array(
            attributes_raw[0], "coefficients", ndim=2
        )
        expected_rows = 1 if len(classes) == 2 else len(classes)
        if (
            coefficients.shape[1] != X.shape[1]
            or coefficients.shape[0] != expected_rows
        ):
            raise ValueError("coefficients: model output has an unexpected shape")
        intercept = _finite_output_array(
            attributes_raw[1],
            "intercept",
            ndim=1,
            shape=(coefficients.shape[0],),
        )
        result["coefficients"] = coefficients.tolist()
        result["intercept"] = intercept.tolist()
    warning_messages.extend(attribute_warnings)

    if predict_X is not None:
        predictions_raw, prediction_warnings = _safe_estimator_call(
            "prediction", lambda: estimator.predict(predict_X)  # type: ignore[attr-defined]
        )
        result["predictions"] = _label_output_array(
            predictions_raw, "predictions", predict_X.shape[0]
        )
        probabilities, probability_warnings = _probabilities(
            estimator, predict_X, len(classes)
        )
        result["probabilities"] = probabilities
        warning_messages.extend(prediction_warnings)
        warning_messages.extend(probability_warnings)

    diagnostics = {
        "training_metric_scope": "accuracy is computed on the supplied training samples",
        "probability_class_order": (
            "probability columns follow result.classes in exact estimator order"
        ),
        "probability_sum_tolerance": _PROBABILITY_TOLERANCE,
    }
    return result, diagnostics, warning_messages


def _execute_supervised(
    model_id: str, payload: Mapping[str, object]
) -> Mapping[str, object]:
    if model_id not in _MODEL_IDS:
        raise KeyError(f"unsupported supervised model: {model_id}")
    _reject_unknown_fields(payload, model_id)
    X = _finite_matrix(payload, "X")
    predict_X = _finite_matrix(payload, "predict_X") if "predict_X" in payload else None
    if predict_X is not None and predict_X.shape[1] != X.shape[1]:
        raise ValueError("predict_X: feature width must equal X feature width")
    _safe_numeric_scale(X, "X")
    if predict_X is not None:
        _safe_numeric_scale(predict_X, "predict_X")

    if model_id == "linear-regression":
        target, target_labels = _regression_target(payload)
        _safe_numeric_scale(target, "y")
        classes = None
    else:
        target, target_labels = _classification_target(payload)
        classes = [
            item.item() if isinstance(item, np.generic) else item
            for item in np.unique(target)
        ]
    if X.shape[0] != target.shape[0]:
        raise ValueError("X and y: sample counts must be equal")

    evaluation_X = X.copy() if model_id == "linear-regression" else X
    evaluation_target = target.copy() if model_id == "linear-regression" else target

    seed = _validated_seed(payload, model_id)
    params, factory_params = _validated_params(
        payload, model_id, X.shape[1], classes
    )
    estimator, warning_messages = _construct_estimator(
        model_id, seed, factory_params
    )
    _, fit_warnings = _safe_estimator_call(
        "fit", lambda: estimator.fit(X, target)  # type: ignore[attr-defined]
    )
    warning_messages.extend(fit_warnings)

    if model_id == "linear-regression":
        result, diagnostics, execution_warnings = _execute_linear(
            estimator, evaluation_X, evaluation_target, predict_X
        )
    else:
        result, diagnostics, execution_warnings = _execute_classifier(
            model_id, estimator, X, target_labels, predict_X
        )
    warning_messages.extend(execution_warnings)
    return {
        "parameters": params,
        "input_summary": {
            "rows": int(X.shape[0]),
            "columns": int(X.shape[1]),
            "prediction_rows": 0 if predict_X is None else int(predict_X.shape[0]),
        },
        "result": result,
        "diagnostics": diagnostics,
        "warnings": sorted(set(warning_messages)),
        "seed": seed,
    }


def execute_linear_regression(payload: Mapping[str, object]) -> Mapping[str, object]:
    """Execute legacy linear regression through the JSON-safe supervised boundary."""
    return _execute_supervised("linear-regression", payload)


def execute_decision_tree(payload: Mapping[str, object]) -> Mapping[str, object]:
    """Execute the legacy decision-tree classifier through the JSON-safe boundary."""
    return _execute_supervised("decision-tree", payload)


def execute_logistic_regression(payload: Mapping[str, object]) -> Mapping[str, object]:
    """Execute logistic regression through the legacy factory and JSON-safe boundary."""
    return _execute_supervised("logistic-regression", payload)
