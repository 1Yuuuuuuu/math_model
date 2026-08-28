"""Strict plain-JSON execution for clustering models."""

from __future__ import annotations

import math
import os
import sys
import warnings
from collections.abc import Callable, Mapping
from typing import TypeVar

import numpy as np
from scipy.cluster.hierarchy import fcluster as scipy_fcluster
from scipy.cluster.hierarchy import linkage as scipy_linkage
from sklearn.cluster import AgglomerativeClustering, DBSCAN

from .. import estimator_factories
from .base import json_finite_number, required_field


_CallResult = TypeVar("_CallResult")
_MODEL_IDS = frozenset({"kmeans", "dbscan", "hierarchical-clustering"})
_COMMON_FIELDS = frozenset({"X", "params", "standardized"})
_KMEANS_FIELDS = _COMMON_FIELDS | {"seed"}
_KMEANS_PARAMS = frozenset(
    {"n_clusters", "init", "n_init", "max_iter", "tol", "algorithm", "random_state"}
)
_DBSCAN_PARAMS = frozenset({"eps", "min_samples", "metric"})
_HIERARCHICAL_PARAMS = frozenset(
    {"n_clusters", "distance_threshold", "linkage", "metric"}
)
_SAFE_METRICS = frozenset({"euclidean", "cityblock", "cosine"})
_LINKAGES = frozenset({"ward", "complete", "average", "single"})
_SCALE_WARNING = (
    "clustering is scale-sensitive; standardize features before interpreting results"
)
_HANDLED_LIBRARY_ERRORS = (
    AttributeError,
    TypeError,
    ValueError,
    RuntimeError,
    OverflowError,
    FloatingPointError,
    np.linalg.LinAlgError,
)


class _OutputValidationError(ValueError):
    """An invalid fitted value whose public field prefix must be preserved."""


def _exact_finite_number(value: object, field: str) -> float:
    number = float(json_finite_number(value, field))
    if type(value) is int and int(number) != value:
        raise ValueError(
            f"{field}: integer cannot be represented exactly as a floating-point number"
        )
    return number


def _finite_matrix(payload: Mapping[str, object]) -> np.ndarray:
    value = required_field(payload, "X")
    if type(value) is not list or not value:
        raise ValueError("X: must be a nonempty plain JSON two-dimensional array")

    rows: list[list[float]] = []
    width: int | None = None
    for row_index, row in enumerate(value):
        if type(row) is not list or not row:
            raise ValueError(f"X[{row_index}]: must be a nonempty plain JSON array")
        if width is None:
            width = len(row)
        elif len(row) != width:
            raise ValueError("X: must be a rectangular two-dimensional array")
        rows.append(
            [
                _exact_finite_number(item, f"X[{row_index}][{column_index}]")
                for column_index, item in enumerate(row)
            ]
        )

    try:
        matrix = np.asarray(rows, dtype=float)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("X: must contain safely representable finite numbers") from exc
    if matrix.ndim != 2 or matrix.shape[0] == 0 or matrix.shape[1] == 0:
        raise ValueError("X: must be a nonempty two-dimensional array")
    if not np.all(np.isfinite(matrix)):
        raise ValueError("X: must contain only finite numbers")
    _validate_numeric_scale(matrix)
    return matrix


def _validate_numeric_scale(matrix: np.ndarray) -> None:
    scale = float(np.max(np.abs(matrix)))
    safe_upper = math.sqrt(sys.float_info.max / max(1, matrix.shape[1])) / 16.0
    if scale > safe_upper:
        raise ValueError("X: scale is outside the safe finite distance range")


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
        raise ValueError(f"{field}: integer is outside the safely representable native range")
    if minimum is not None and value < minimum:
        raise ValueError(f"{field}: must be at least {minimum}")
    if maximum is not None and value > maximum:
        raise ValueError(f"{field}: must be at most {maximum}")
    return value


def _positive_finite_number(value: object, field: str) -> float:
    number = _exact_finite_number(value, field)
    if number <= 0.0:
        raise ValueError(f"{field}: must be greater than 0")
    return number


def _plain_enum(value: object, field: str, choices: frozenset[str]) -> str:
    if type(value) is not str or value not in choices:
        raise ValueError(f"{field}: must be one of {', '.join(sorted(choices))}")
    return value


def _plain_bool(value: object, field: str) -> bool:
    if type(value) is not bool:
        raise ValueError(f"{field}: must be a built-in boolean")
    return value


def _reject_unknown_fields(payload: Mapping[str, object], model_id: str) -> None:
    allowed = _KMEANS_FIELDS if model_id == "kmeans" else _COMMON_FIELDS
    unknown = sorted(set(payload) - allowed)
    if unknown:
        raise ValueError(f"{unknown[0]}: is not a supported payload field")


def _raw_params(payload: Mapping[str, object]) -> dict[str, object]:
    raw = payload.get("params", {})
    if type(raw) is not dict:
        raise ValueError("params: must be a plain JSON object")
    return raw


def _standardized(payload: Mapping[str, object]) -> bool:
    return _plain_bool(payload.get("standardized", False), "standardized")


def _kmeans_seed(payload: Mapping[str, object], raw_params: dict[str, object]) -> int | None:
    if payload.get("seed") is not None and raw_params.get("random_state") is not None:
        raise ValueError("seed: conflicts with params.random_state")
    if "seed" not in payload or payload["seed"] is None:
        return None
    return _plain_integer(payload["seed"], "seed", minimum=0, maximum=2**32 - 1)


def _validate_kmeans_params(
    raw: dict[str, object], sample_count: int
) -> tuple[dict[str, object], int]:
    normalized: dict[str, object] = {}
    for name, value in dict.items(raw):
        field = f"params.{name}"
        if name not in _KMEANS_PARAMS:
            raise ValueError(f"{field}: is not a supported parameter")
        if name == "n_clusters":
            normalized[name] = _plain_integer(
                value, field, minimum=1, maximum=sample_count
            )
        elif name == "init":
            normalized[name] = _plain_enum(
                value, field, frozenset({"k-means++", "random"})
            )
        elif name == "n_init":
            if value == "auto" and type(value) is str:
                normalized[name] = "auto"
            else:
                normalized[name] = _plain_integer(value, field, minimum=1)
        elif name == "max_iter":
            normalized[name] = _plain_integer(value, field, minimum=1)
        elif name == "tol":
            normalized[name] = _positive_finite_number(value, field)
        elif name == "algorithm":
            normalized[name] = _plain_enum(
                value, field, frozenset({"lloyd", "elkan"})
            )
        else:
            normalized[name] = (
                None
                if value is None
                else _plain_integer(value, field, minimum=0, maximum=2**32 - 1)
            )

    requested = int(normalized.get("n_clusters", 3))
    if requested > sample_count:
        raise ValueError("params.n_clusters: must not exceed the sample count")
    return normalized, requested


def _validate_dbscan_params(raw: dict[str, object]) -> dict[str, object]:
    normalized: dict[str, object] = {}
    for name, value in dict.items(raw):
        field = f"params.{name}"
        if name not in _DBSCAN_PARAMS:
            raise ValueError(f"{field}: is not a supported parameter")
        if name == "eps":
            normalized[name] = _positive_finite_number(value, field)
        elif name == "min_samples":
            normalized[name] = _plain_integer(value, field, minimum=1)
        else:
            normalized[name] = _plain_enum(value, field, _SAFE_METRICS)
    return normalized


def _validate_hierarchical_params(
    raw: dict[str, object], sample_count: int
) -> tuple[dict[str, object], dict[str, object]]:
    normalized: dict[str, object] = {}
    for name, value in dict.items(raw):
        field = f"params.{name}"
        if name not in _HIERARCHICAL_PARAMS:
            raise ValueError(f"{field}: is not a supported parameter")
        if name == "n_clusters":
            normalized[name] = (
                None
                if value is None
                else _plain_integer(value, field, minimum=1, maximum=sample_count)
            )
        elif name == "distance_threshold":
            normalized[name] = (
                None if value is None else _positive_finite_number(value, field)
            )
        elif name == "linkage":
            normalized[name] = _plain_enum(value, field, _LINKAGES)
        else:
            normalized[name] = _plain_enum(value, field, _SAFE_METRICS)

    n_clusters = normalized.get("n_clusters")
    distance_threshold = normalized.get("distance_threshold")
    if (n_clusters is None) == (distance_threshold is None):
        raise ValueError(
            "params: exactly one of n_clusters and distance_threshold must be non-null"
        )
    linkage_method = str(normalized.get("linkage", "ward"))
    metric = str(normalized.get("metric", "euclidean"))
    if linkage_method == "ward" and metric != "euclidean":
        raise ValueError("params.metric: ward linkage requires euclidean metric")

    estimator_params = {
        "n_clusters": n_clusters,
        "distance_threshold": distance_threshold,
        "linkage": linkage_method,
        "metric": metric,
    }
    if distance_threshold is not None:
        inclusive_threshold = math.nextafter(distance_threshold, math.inf)
        if math.isfinite(inclusive_threshold):
            estimator_params["distance_threshold"] = inclusive_threshold
        estimator_params["compute_full_tree"] = True
    return normalized, estimator_params


def _safe_library_call(stage: str, function: Callable[[], _CallResult]) -> _CallResult:
    captured: list[warnings.WarningMessage]
    failure: Exception | None = None
    validation_failure: _OutputValidationError | None = None
    result: _CallResult | None = None
    with warnings.catch_warnings(record=True) as captured:
        warnings.simplefilter("always")
        with np.errstate(all="ignore"):
            try:
                result = function()
            except _OutputValidationError as exc:
                validation_failure = exc
            except _HANDLED_LIBRARY_ERRORS as exc:
                failure = exc
    if validation_failure is not None:
        raise ValueError(str(validation_failure)) from validation_failure
    if failure is not None:
        raise ValueError(f"{stage}: library operation failed: {failure}") from failure
    if captured:
        categories = ", ".join(sorted({item.category.__name__ for item in captured}))
        raise ValueError(f"{stage}: library emitted warning(s): {categories}")
    return result  # type: ignore[return-value]


def _canonical_labels(
    value: object, sample_count: int, *, preserve_noise: bool
) -> tuple[list[int], list[int], list[int]]:
    try:
        array = np.asarray(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise _OutputValidationError(
            "labels: model output must be a one-dimensional integer array"
        ) from exc
    if array.ndim != 1 or array.size != sample_count:
        raise _OutputValidationError("labels: model output has an unexpected shape")

    original: list[int] = []
    for index, item in enumerate(array):
        if isinstance(item, np.generic):
            item = item.item()
        if type(item) is not int:
            raise _OutputValidationError(
                f"labels[{index}]: model output must be an integer"
            )
        if item < 0 and not (preserve_noise and item == -1):
            raise _OutputValidationError(
                f"labels[{index}]: model output contains an invalid label"
            )
        original.append(item)

    mapping: dict[int, int] = {}
    order: list[int] = []
    canonical: list[int] = []
    for label in original:
        if preserve_noise and label == -1:
            canonical.append(-1)
            continue
        if label not in mapping:
            mapping[label] = len(mapping)
            order.append(label)
        canonical.append(mapping[label])
    return canonical, original, order


def _finite_output_array(
    value: object, field: str, *, shape: tuple[int, ...]
) -> np.ndarray:
    try:
        array = np.asarray(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise _OutputValidationError(
            f"{field}: model output must be a finite numeric array"
        ) from exc
    if array.shape != shape:
        raise _OutputValidationError(f"{field}: model output has an unexpected shape")
    if (
        not np.issubdtype(array.dtype, np.number)
        or np.issubdtype(array.dtype, np.bool_)
        or np.issubdtype(array.dtype, np.complexfloating)
    ):
        raise _OutputValidationError(
            f"{field}: model output must use a real numeric dtype"
        )
    try:
        normalized = array.astype(float, copy=False)
    except (TypeError, ValueError, OverflowError) as exc:
        raise _OutputValidationError(
            f"{field}: model output must be a finite numeric array"
        ) from exc
    if not np.all(np.isfinite(normalized)):
        raise _OutputValidationError(f"{field}: model produced non-finite values")
    return normalized


def _finite_output_number(value: object, field: str, *, minimum: float) -> float:
    if isinstance(value, np.generic):
        value = value.item()
    if type(value) not in (int, float):
        raise _OutputValidationError(f"{field}: model output must be a finite number")
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise _OutputValidationError(
            f"{field}: model output must be a finite number"
        ) from exc
    if not math.isfinite(number) or number < minimum:
        raise _OutputValidationError(
            f"{field}: model output must be finite and at least {minimum}"
        )
    return number


def _positive_output_integer(value: object, field: str) -> int:
    if isinstance(value, np.generic):
        value = value.item()
    if type(value) is not int or value < 1:
        raise _OutputValidationError(
            f"{field}: model output must be a positive integer"
        )
    return value


def _validated_linkage(value: object, sample_count: int) -> list[list[float]]:
    matrix = _finite_output_array(
        value, "linkage_matrix", shape=(sample_count - 1, 4)
    )
    node_counts: dict[int, int] = {index: 1 for index in range(sample_count)}
    used: set[int] = set()
    previous_distance = -math.inf
    for row_index, row in enumerate(matrix):
        left_value, right_value, distance, count_value = row.tolist()
        if not left_value.is_integer() or not right_value.is_integer():
            raise _OutputValidationError(
                "linkage_matrix: merge indices must be integers"
            )
        left = int(left_value)
        right = int(right_value)
        maximum_child = sample_count + row_index
        if (
            left < 0
            or right < 0
            or left >= maximum_child
            or right >= maximum_child
            or left == right
            or left in used
            or right in used
        ):
            raise _OutputValidationError("linkage_matrix: merge indices are invalid")
        if distance < 0.0 or distance < previous_distance:
            raise _OutputValidationError(
                "linkage_matrix: merge distances must be nonnegative and ordered"
            )
        expected_count = node_counts[left] + node_counts[right]
        if not count_value.is_integer() or int(count_value) != expected_count:
            raise _OutputValidationError(
                "linkage_matrix: merge sample counts are invalid"
            )
        used.update((left, right))
        node_counts[maximum_child] = expected_count
        previous_distance = distance
    if node_counts[2 * sample_count - 2] != sample_count:
        raise _OutputValidationError("linkage_matrix: final merge count is invalid")
    return matrix.tolist()


def _same_partition(left: list[int], right: list[int]) -> bool:
    return all(
        (left[first] == left[second]) == (right[first] == right[second])
        for first in range(len(left))
        for second in range(len(left))
    )


def _validated_kmeans_outputs(
    estimator: object,
    *,
    sample_count: int,
    feature_count: int,
    requested_clusters: int,
) -> tuple[list[int], int, np.ndarray, float, int]:
    labels, _, label_order = _canonical_labels(
        getattr(estimator, "labels_"), sample_count, preserve_noise=False
    )
    cluster_count = len(label_order)
    if cluster_count != requested_clusters:
        raise _OutputValidationError(
            "cluster_count: fitted result did not supply the requested clusters"
        )
    if any(label < 0 or label >= requested_clusters for label in label_order):
        raise _OutputValidationError(
            "labels: fitted labels do not index cluster centers"
        )
    centers = _finite_output_array(
        getattr(estimator, "cluster_centers_"),
        "cluster_centers",
        shape=(requested_clusters, feature_count),
    )
    canonical_centers = centers[np.asarray(label_order, dtype=int), :]
    inertia = _finite_output_number(
        getattr(estimator, "inertia_"), "inertia", minimum=0.0
    )
    iteration_count = _positive_output_integer(
        getattr(estimator, "n_iter_"), "iteration_count"
    )
    return labels, cluster_count, canonical_centers, inertia, iteration_count


def _base_raw_result(
    matrix: np.ndarray,
    parameters: dict[str, object],
    result: dict[str, object],
    *,
    standardized: bool,
    seed: int | None,
    scale_warning: bool,
) -> Mapping[str, object]:
    return {
        "parameters": {**parameters, "standardized": standardized},
        "input_summary": {
            "rows": int(matrix.shape[0]),
            "columns": int(matrix.shape[1]),
        },
        "result": result,
        "diagnostics": {
            "label_canonicalization": "cluster labels follow first occurrence; DBSCAN preserves -1 as noise"
        },
        "warnings": [_SCALE_WARNING] if scale_warning and not standardized else [],
        "seed": seed,
    }


def execute_kmeans(payload: Mapping[str, object]) -> Mapping[str, object]:
    """Execute legacy KMeans while returning only validated plain JSON data."""
    _reject_unknown_fields(payload, "kmeans")
    matrix = _finite_matrix(payload)
    standardized = _standardized(payload)
    raw_params = _raw_params(payload)
    params, requested_clusters = _validate_kmeans_params(raw_params, matrix.shape[0])
    seed = _kmeans_seed(payload, raw_params)

    factory = estimator_factories.get_estimator_factory("kmeans")
    estimator = _safe_library_call(
        "params", lambda: factory(seed=seed, params=dict(params))
    )
    previous_cpu_count = os.environ.get("LOKY_MAX_CPU_COUNT")
    if previous_cpu_count is None:
        os.environ["LOKY_MAX_CPU_COUNT"] = "1"
    try:
        _safe_library_call("fit", lambda: estimator.fit(matrix))  # type: ignore[attr-defined]
    finally:
        if previous_cpu_count is None:
            os.environ.pop("LOKY_MAX_CPU_COUNT", None)
    (
        labels,
        cluster_count,
        canonical_centers,
        inertia,
        iteration_count,
    ) = _safe_library_call(
        "fitted attributes",
        lambda: _validated_kmeans_outputs(
            estimator,
            sample_count=matrix.shape[0],
            feature_count=matrix.shape[1],
            requested_clusters=requested_clusters,
        ),
    )

    return _base_raw_result(
        matrix,
        params,
        {
            "labels": labels,
            "cluster_count": cluster_count,
            "noise_count": 0,
            "cluster_centers": canonical_centers.tolist(),
            "inertia": inertia,
            "iteration_count": iteration_count,
        },
        standardized=standardized,
        seed=seed,
        scale_warning=False,
    )


def execute_dbscan(payload: Mapping[str, object]) -> Mapping[str, object]:
    """Execute DBSCAN with canonical cluster labels and explicit noise counts."""
    _reject_unknown_fields(payload, "dbscan")
    matrix = _finite_matrix(payload)
    standardized = _standardized(payload)
    params = _validate_dbscan_params(_raw_params(payload))
    estimator = _safe_library_call("params", lambda: DBSCAN(**dict(params)))
    previous_cpu_count = os.environ.get("LOKY_MAX_CPU_COUNT")
    if previous_cpu_count is None:
        os.environ["LOKY_MAX_CPU_COUNT"] = "1"
    try:
        _safe_library_call("fit", lambda: estimator.fit(matrix))
    finally:
        if previous_cpu_count is None:
            os.environ.pop("LOKY_MAX_CPU_COUNT", None)
    labels, _, label_order = _safe_library_call(
        "fitted attributes",
        lambda: _canonical_labels(
            getattr(estimator, "labels_", None),
            matrix.shape[0],
            preserve_noise=True,
        ),
    )
    result = {
        "labels": labels,
        "cluster_count": len(label_order),
        "noise_count": labels.count(-1),
    }
    return _base_raw_result(
        matrix,
        params,
        result,
        standardized=standardized,
        seed=None,
        scale_warning=True,
    )


def execute_hierarchical_clustering(
    payload: Mapping[str, object],
) -> Mapping[str, object]:
    """Execute agglomerative clustering and return its corresponding SciPy linkage."""
    _reject_unknown_fields(payload, "hierarchical-clustering")
    matrix = _finite_matrix(payload)
    if matrix.shape[0] < 2:
        raise ValueError("X: hierarchical clustering requires at least two samples")
    standardized = _standardized(payload)
    params, estimator_params = _validate_hierarchical_params(
        _raw_params(payload), matrix.shape[0]
    )
    estimator = _safe_library_call(
        "params", lambda: AgglomerativeClustering(**dict(estimator_params))
    )
    _safe_library_call("fit", lambda: estimator.fit(matrix))
    labels, _, label_order = _safe_library_call(
        "fitted attributes",
        lambda: _canonical_labels(
            getattr(estimator, "labels_", None),
            matrix.shape[0],
            preserve_noise=False,
        ),
    )
    requested = estimator_params["n_clusters"]
    if requested is not None and len(label_order) != requested:
        raise ValueError("cluster_count: fitted result did not supply the requested clusters")

    linkage_matrix = _safe_library_call(
        "linkage",
        lambda: _validated_linkage(
            scipy_linkage(
                matrix,
                method=str(estimator_params["linkage"]),
                metric=str(estimator_params["metric"]),
            ),
            matrix.shape[0],
        ),
    )
    public_threshold = params.get("distance_threshold")
    if public_threshold is not None:
        scipy_labels, _, _ = _safe_library_call(
            "linkage partition",
            lambda: _canonical_labels(
                scipy_fcluster(
                    np.asarray(linkage_matrix, dtype=float),
                    float(public_threshold),
                    criterion="distance",
                ),
                matrix.shape[0],
                preserve_noise=False,
            ),
        )
        if not _same_partition(labels, scipy_labels):
            raise ValueError(
                "labels: fitted partition does not match linkage_matrix at "
                "params.distance_threshold"
            )
    return _base_raw_result(
        matrix,
        params,
        {
            "labels": labels,
            "cluster_count": len(label_order),
            "noise_count": 0,
            "linkage_matrix": linkage_matrix,
        },
        standardized=standardized,
        seed=None,
        scale_warning=True,
    )
