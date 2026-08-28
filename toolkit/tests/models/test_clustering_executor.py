from __future__ import annotations

import copy
import importlib
import json
import math
import re
import warnings
from pathlib import Path

import jsonschema
import numpy as np
import pytest
import yaml
from scipy.cluster.hierarchy import cut_tree, fcluster
from sklearn.base import BaseEstimator
from sklearn.exceptions import ConvergenceWarning

from cumcm_toolkit.models import execute
from cumcm_toolkit.models import registry as legacy_registry
from cumcm_toolkit.models.runner import run_model
from cumcm_toolkit.models.specifications import get_spec, list_capabilities


MODEL_IDS = ("kmeans", "dbscan", "hierarchical-clustering")
SCALE_WARNING = (
    "clustering is scale-sensitive; standardize features before interpreting results"
)
KMEANS_PAYLOAD: dict[str, object] = {
    "X": [[0.0, 0.0], [0.0, 2.0], [10.0, 10.0], [10.0, 12.0]],
    "params": {"n_clusters": 2, "n_init": 10},
    "seed": 7,
}
DBSCAN_PAYLOAD: dict[str, object] = {
    "X": [[0.0], [0.1], [5.0], [5.1]],
    "params": {"eps": 0.25, "min_samples": 2},
}
HIERARCHICAL_PAYLOAD: dict[str, object] = {
    "X": [[0.0], [0.2], [5.0], [5.2]],
    "params": {"n_clusters": 2, "linkage": "complete", "metric": "euclidean"},
}


def _payload_for(model_id: str) -> dict[str, object]:
    return copy.deepcopy(
        {
            "kmeans": KMEANS_PAYLOAD,
            "dbscan": DBSCAN_PAYLOAD,
            "hierarchical-clustering": HIERARCHICAL_PAYLOAD,
        }[model_id]
    )


def _assert_execution_error(model_id: str, payload: object, field: str) -> None:
    with pytest.raises(
        ValueError,
        match=rf"{re.escape(model_id)}: execution stage failed: {re.escape(field)}",
    ):
        execute(model_id, payload)  # type: ignore[arg-type]


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


def _same_partition(left: list[int], right: list[int]) -> bool:
    if len(left) != len(right):
        return False
    return all(
        (left[i] == left[j]) == (right[i] == right[j])
        for i in range(len(left))
        for j in range(len(left))
    )


def _clustering_module():
    return importlib.import_module("cumcm_toolkit.models.executors.clustering")


def test_kmeans_known_partition_centers_inertia_and_iterations() -> None:
    """Wrong fitting, center reordering, inertia, or label canonicalization breaks this fixture."""
    result = execute("kmeans", copy.deepcopy(KMEANS_PAYLOAD))

    assert result["result"]["labels"] == [0, 0, 1, 1]
    assert result["result"]["cluster_count"] == 2
    assert result["result"]["noise_count"] == 0
    assert np.allclose(result["result"]["cluster_centers"], [[0.0, 1.0], [10.0, 11.0]])
    assert result["result"]["inertia"] == pytest.approx(4.0)
    assert type(result["result"]["iteration_count"]) is int
    assert result["result"]["iteration_count"] > 0


def test_kmeans_same_seed_returns_identical_canonical_result() -> None:
    """Dropping the seed or exposing arbitrary sklearn label identities breaks repeatability."""
    first = execute("kmeans", copy.deepcopy(KMEANS_PAYLOAD))
    second = execute("kmeans", copy.deepcopy(KMEANS_PAYLOAD))

    assert first == second
    assert first["reproducibility"] == {"seed": 7, "deterministic": False}


def test_kmeans_one_sample_one_cluster_and_identical_data_succeed() -> None:
    """Valid degenerate one-cluster cases must not be confused with missing distinct clusters."""
    single = execute(
        "kmeans", {"X": [[2.5]], "params": {"n_clusters": 1}, "seed": 0}
    )
    identical = execute(
        "kmeans",
        {"X": [[3.0], [3.0], [3.0]], "params": {"n_clusters": 1}, "seed": 0},
    )

    assert single["result"] == {
        "labels": [0],
        "cluster_count": 1,
        "noise_count": 0,
        "cluster_centers": [[2.5]],
        "inertia": 0.0,
        "iteration_count": 1,
    }
    assert identical["result"]["labels"] == [0, 0, 0]
    assert identical["result"]["cluster_centers"] == [[3.0]]
    assert identical["result"]["inertia"] == pytest.approx(0.0)


def test_kmeans_n_init_auto_is_supported_without_version_warning_leakage() -> None:
    """The sklearn>=1.4 string form must remain usable without surfacing library warnings."""
    payload = copy.deepcopy(KMEANS_PAYLOAD)
    payload["params"] = {"n_clusters": 2, "n_init": "auto"}
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        result = execute("kmeans", payload)

    assert result["parameters"] == {
        "n_clusters": 2,
        "n_init": "auto",
        "standardized": False,
    }
    assert caught == []


def test_kmeans_safe_allowlisted_parameters_are_applied_and_reported() -> None:
    """Silently dropping an admitted option or opening a kwargs tunnel breaks transparency."""
    params = {
        "n_clusters": 2,
        "init": "random",
        "n_init": 4,
        "max_iter": 50,
        "tol": 1e-5,
        "algorithm": "lloyd",
        "random_state": 11,
    }
    payload = {"X": copy.deepcopy(KMEANS_PAYLOAD["X"]), "params": params}
    result = execute("kmeans", payload)

    assert result["parameters"] == {**params, "standardized": False}
    assert result["reproducibility"]["seed"] is None


@pytest.mark.parametrize(
    ("params", "field"),
    [
        ({"n_clusters": 0}, "params.n_clusters"),
        ({"n_clusters": 5}, "params.n_clusters"),
        ({"n_clusters": True}, "params.n_clusters"),
        ({"n_init": 0}, "params.n_init"),
        ({"n_init": "default"}, "params.n_init"),
        ({"n_init": True}, "params.n_init"),
        ({"max_iter": 0}, "params.max_iter"),
        ({"max_iter": 1.5}, "params.max_iter"),
        ({"tol": 0.0}, "params.tol"),
        ({"tol": -1.0}, "params.tol"),
        ({"tol": float("inf")}, "params.tol"),
        ({"tol": True}, "params.tol"),
        ({"algorithm": "full"}, "params.algorithm"),
        ({"algorithm": 1}, "params.algorithm"),
        ({"init": "callable"}, "params.init"),
        ({"init": [[0.0], [1.0]]}, "params.init"),
        ({"random_state": -1}, "params.random_state"),
        ({"random_state": 2**32}, "params.random_state"),
        ({"random_state": True}, "params.random_state"),
        ({"bogus": 1}, "params.bogus"),
    ],
)
def test_kmeans_parameter_allowlist_rejects_invalid_values(
    params: dict[str, object], field: str
) -> None:
    """Every admitted sklearn parameter needs a safe pre-construction boundary."""
    payload = copy.deepcopy(KMEANS_PAYLOAD)
    payload["params"] = params
    _assert_execution_error("kmeans", payload, field)


def test_kmeans_seed_and_random_state_boundaries() -> None:
    """Randomness must be bounded and conflicting declarations must never be ambiguous."""
    for seed in (True, -1, 2**32, 10**100):
        payload = copy.deepcopy(KMEANS_PAYLOAD)
        payload["seed"] = seed
        _assert_execution_error("kmeans", payload, "seed")

    conflict = copy.deepcopy(KMEANS_PAYLOAD)
    conflict["params"] = {"n_clusters": 2, "random_state": 3}
    _assert_execution_error("kmeans", conflict, "seed")

    nullable = copy.deepcopy(KMEANS_PAYLOAD)
    nullable["seed"] = None
    nullable["params"] = {"n_clusters": 2, "random_state": None}
    assert execute("kmeans", nullable)["parameters"]["random_state"] is None


def test_kmeans_rejects_more_requested_clusters_than_distinct_fitted_clusters() -> None:
    """A convergence warning must not disguise fewer actual clusters than requested."""
    payload = {
        "X": [[1.0], [1.0], [1.0]],
        "params": {"n_clusters": 2, "n_init": 2},
        "seed": 0,
    }
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        _assert_execution_error("kmeans", payload, "fit")
    assert caught == []


def test_dbscan_no_noise_and_standardized_warning_behavior() -> None:
    """Noise accounting and the deterministic scale warning are public DBSCAN semantics."""
    raw = execute("dbscan", copy.deepcopy(DBSCAN_PAYLOAD))
    standardized_payload = copy.deepcopy(DBSCAN_PAYLOAD)
    standardized_payload["standardized"] = True
    standardized = execute("dbscan", standardized_payload)

    assert raw["result"] == {"labels": [0, 0, 1, 1], "cluster_count": 2, "noise_count": 0}
    assert raw["warnings"] == [SCALE_WARNING]
    assert standardized["warnings"] == []
    assert standardized["parameters"] == {
        "eps": 0.25,
        "min_samples": 2,
        "standardized": True,
    }


def test_dbscan_survives_unavailable_physical_core_detection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A host CPU-probe warning must not turn a valid DBSCAN fit into failure."""
    from joblib.externals.loky.backend import context

    def deny_cpu_probe() -> int:
        raise PermissionError("physical core probe denied")

    monkeypatch.delenv("LOKY_MAX_CPU_COUNT", raising=False)
    monkeypatch.setattr(context, "physical_cores_cache", None)
    monkeypatch.setattr(context, "_count_physical_cores_win32", deny_cpu_probe)

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        result = execute(
            "dbscan",
            {
                "X": [[0, 0], [0, 0.1], [10, 10]],
                "params": {"eps": 0.3, "min_samples": 2},
                "standardized": False,
            },
        )

    assert result["result"] == {
        "labels": [0, 0, -1],
        "cluster_count": 1,
        "noise_count": 1,
    }
    assert caught == []


def test_dbscan_mixed_noise_and_all_noise_are_counted_without_fake_clusters() -> None:
    """Treating -1 as a cluster corrupts both cluster and noise counts."""
    mixed = execute(
        "dbscan",
        {"X": [[0.0], [0.1], [5.0], [5.1], [20.0]], "params": {"eps": 0.25, "min_samples": 2}},
    )
    all_noise = execute(
        "dbscan",
        {"X": [[0.0], [2.0], [4.0]], "params": {"eps": 0.1, "min_samples": 2}},
    )

    assert mixed["result"] == {
        "labels": [0, 0, 1, 1, -1],
        "cluster_count": 2,
        "noise_count": 1,
    }
    assert all_noise["result"] == {
        "labels": [-1, -1, -1],
        "cluster_count": 0,
        "noise_count": 3,
    }


def test_dbscan_single_sample_cluster_noise_and_identical_data() -> None:
    """The min_samples boundary controls valid singletons while identical rows stay clusterable."""
    cluster = execute("dbscan", {"X": [[1.0]], "params": {"eps": 0.5, "min_samples": 1}})
    noise = execute("dbscan", {"X": [[1.0]], "params": {"eps": 0.5, "min_samples": 2}})
    identical = execute(
        "dbscan",
        {"X": [[1.0], [1.0], [1.0]], "params": {"eps": 0.5, "min_samples": 2}},
    )

    assert cluster["result"]["labels"] == [0]
    assert cluster["result"]["cluster_count"] == 1
    assert noise["result"]["labels"] == [-1]
    assert noise["result"]["noise_count"] == 1
    assert identical["result"]["labels"] == [0, 0, 0]


@pytest.mark.parametrize(
    ("params", "field"),
    [
        ({"eps": 0.0}, "params.eps"),
        ({"eps": -0.1}, "params.eps"),
        ({"eps": float("nan")}, "params.eps"),
        ({"eps": float("inf")}, "params.eps"),
        ({"eps": True}, "params.eps"),
        ({"min_samples": 0}, "params.min_samples"),
        ({"min_samples": True}, "params.min_samples"),
        ({"min_samples": 1.0}, "params.min_samples"),
        ({"metric": "precomputed"}, "params.metric"),
        ({"metric": "mahalanobis"}, "params.metric"),
        ({"metric": 1}, "params.metric"),
        ({"bogus": 1}, "params.bogus"),
    ],
)
def test_dbscan_parameter_allowlist_rejects_invalid_values(
    params: dict[str, object], field: str
) -> None:
    """DBSCAN parameters must not become a callable or precomputed distance escape hatch."""
    payload = copy.deepcopy(DBSCAN_PAYLOAD)
    payload["params"] = params
    _assert_execution_error("dbscan", payload, field)


@pytest.mark.parametrize("metric", ["euclidean", "cityblock", "cosine"])
def test_dbscan_shared_safe_metrics_execute_and_are_reported(metric: str) -> None:
    """Each metric in the shared sklearn/SciPy allowlist must execute through real DBSCAN."""
    payload = {
        "X": [[1.0, 0.0], [1.0, 0.1], [5.0, 4.0]],
        "params": {"eps": 0.2, "min_samples": 1, "metric": metric},
        "standardized": True,
    }
    result = execute("dbscan", payload)
    assert result["parameters"]["metric"] == metric
    assert result["result"]["cluster_count"] >= 1


def test_dbscan_canonicalizes_permuted_nonconsecutive_labels_and_preserves_noise(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Canonicalization must use first occurrence and reserve -1 only for noise."""
    module = _clustering_module()

    class PermutedDBSCAN:
        labels_ = np.array([7, 7, -1, 3, 3])

        def __init__(self, **params: object) -> None:
            pass

        def fit(self, X: np.ndarray) -> PermutedDBSCAN:
            return self

    monkeypatch.setattr(module, "DBSCAN", PermutedDBSCAN)
    result = execute(
        "dbscan",
        {"X": [[0.0], [0.1], [2.0], [5.0], [5.1]], "params": {"eps": 0.25}},
    )

    assert result["result"] == {
        "labels": [0, 0, -1, 1, 1],
        "cluster_count": 2,
        "noise_count": 1,
    }


def test_hierarchical_n_clusters_partition_matches_scipy_linkage_cut() -> None:
    """Sklearn labels and the returned dendrogram must describe the same fixed-K partition."""
    result = execute("hierarchical-clustering", copy.deepcopy(HIERARCHICAL_PAYLOAD))
    linkage_matrix = np.asarray(result["result"]["linkage_matrix"], dtype=float)
    scipy_labels = cut_tree(linkage_matrix, n_clusters=[2]).reshape(-1).tolist()

    assert _same_partition(result["result"]["labels"], scipy_labels)
    assert result["result"]["cluster_count"] == 2
    assert result["result"]["noise_count"] == 0
    assert linkage_matrix.shape == (3, 4)
    assert np.all(np.isfinite(linkage_matrix))
    assert result["warnings"] == [SCALE_WARNING]


def test_hierarchical_distance_threshold_partition_matches_scipy_linkage_cut() -> None:
    """Threshold mode must use the same distance semantics in sklearn and SciPy outputs."""
    threshold = 1.0
    payload = {
        "X": [[0.0], [0.2], [5.0], [5.2]],
        "params": {
            "n_clusters": None,
            "distance_threshold": threshold,
            "linkage": "average",
            "metric": "euclidean",
        },
        "standardized": True,
    }
    result = execute("hierarchical-clustering", payload)
    linkage_matrix = np.asarray(result["result"]["linkage_matrix"], dtype=float)
    scipy_labels = (fcluster(linkage_matrix, threshold, criterion="distance") - 1).tolist()

    assert _same_partition(result["result"]["labels"], scipy_labels)
    assert result["result"]["cluster_count"] == 2
    assert result["warnings"] == []
    assert result["parameters"] == {**payload["params"], "standardized": True}


def test_hierarchical_distance_threshold_includes_merge_at_exact_boundary() -> None:
    """The public threshold includes a merge whose distance equals the boundary."""
    threshold = 1.0
    result = execute(
        "hierarchical-clustering",
        {
            "X": [[0.0], [1.0], [5.0]],
            "params": {
                "n_clusters": None,
                "distance_threshold": threshold,
                "linkage": "average",
                "metric": "euclidean",
            },
            "standardized": True,
        },
    )
    linkage_matrix = np.asarray(result["result"]["linkage_matrix"], dtype=float)
    scipy_labels = (
        fcluster(linkage_matrix, threshold, criterion="distance") - 1
    ).tolist()

    assert result["result"]["labels"] == [0, 0, 1]
    assert scipy_labels == [0, 0, 1]
    assert _same_partition(result["result"]["labels"], scipy_labels)


def test_hierarchical_max_finite_threshold_does_not_leak_nextafter_warning() -> None:
    """The inclusive-threshold translation must stay warning-free at binary64 max."""
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        result = execute(
            "hierarchical-clustering",
            {
                "X": [[0.0], [1.0]],
                "params": {
                    "n_clusters": None,
                    "distance_threshold": float(np.finfo(float).max),
                    "linkage": "average",
                    "metric": "euclidean",
                },
            },
        )

    assert result["result"]["labels"] == [0, 0]
    assert caught == []


def test_hierarchical_identical_data_with_one_cluster_has_valid_linkage() -> None:
    """Zero merge distances are valid and must not be rejected as nonpositive thresholds."""
    result = execute(
        "hierarchical-clustering",
        {"X": [[2.0], [2.0], [2.0]], "params": {"n_clusters": 1}},
    )
    matrix = result["result"]["linkage_matrix"]

    assert result["result"]["labels"] == [0, 0, 0]
    assert result["result"]["cluster_count"] == 1
    assert len(matrix) == 2
    assert all(row[2] == 0.0 for row in matrix)


@pytest.mark.parametrize(
    ("params", "field"),
    [
        ({}, "params"),
        ({"n_clusters": None}, "params"),
        ({"distance_threshold": None}, "params"),
        ({"n_clusters": 2, "distance_threshold": 1.0}, "params"),
        ({"n_clusters": 0}, "params.n_clusters"),
        ({"n_clusters": 5}, "params.n_clusters"),
        ({"n_clusters": True}, "params.n_clusters"),
        ({"distance_threshold": 0.0}, "params.distance_threshold"),
        ({"distance_threshold": -1.0}, "params.distance_threshold"),
        ({"distance_threshold": float("inf")}, "params.distance_threshold"),
        ({"distance_threshold": True}, "params.distance_threshold"),
        ({"n_clusters": 2, "linkage": "centroid"}, "params.linkage"),
        ({"n_clusters": 2, "metric": "precomputed"}, "params.metric"),
        ({"n_clusters": 2, "metric": "mahalanobis"}, "params.metric"),
        ({"n_clusters": 2, "metric": 1}, "params.metric"),
        ({"n_clusters": 2, "linkage": "ward", "metric": "cosine"}, "params.metric"),
        ({"n_clusters": 2, "bogus": 1}, "params.bogus"),
    ],
)
def test_hierarchical_parameter_contract_rejects_invalid_combinations(
    params: dict[str, object], field: str
) -> None:
    """Invalid cut modes and incompatible linkage metrics must fail before library calls."""
    payload = copy.deepcopy(HIERARCHICAL_PAYLOAD)
    payload["params"] = params
    _assert_execution_error("hierarchical-clustering", payload, field)


def test_hierarchical_rejects_one_sample_before_linkage() -> None:
    """Agglomerative labels alone cannot satisfy the promised nonempty linkage matrix."""
    _assert_execution_error(
        "hierarchical-clustering",
        {"X": [[1.0]], "params": {"n_clusters": 1}},
        "X",
    )


@pytest.mark.parametrize("model_id", ["dbscan", "hierarchical-clustering"])
def test_deterministic_clustering_models_reject_seed(model_id: str) -> None:
    """Advertising or silently ignoring a seed would contradict deterministic metadata."""
    payload = _payload_for(model_id)
    payload["seed"] = 7
    _assert_execution_error(model_id, payload, "seed")


@pytest.mark.parametrize("model_id", MODEL_IDS)
def test_clustering_requires_nonempty_rectangular_plain_json_matrix(model_id: str) -> None:
    """Tuples, ragged rows, and empty dimensions must never reach NumPy or a clustering library."""
    for bad in ([], [[]], [1.0, 2.0], [[[1.0]]], [[1.0], [2.0, 3.0]], ((1.0,),)):
        payload = _payload_for(model_id)
        payload["X"] = bad
        _assert_execution_error(model_id, payload, "X")


@pytest.mark.parametrize(
    ("value", "suffix"),
    [
        (True, "[0][0]"),
        (1 + 2j, "[0][0]"),
        ("1", "[0][0]"),
        (float("nan"), "[0][0]"),
        (float("inf"), "[0][0]"),
        (float("-inf"), "[0][0]"),
        (10**10000, "[0][0]"),
    ],
    ids=["bool", "complex", "string", "nan", "positive-infinity", "negative-infinity", "oversized-integer"],
)
@pytest.mark.parametrize("model_id", MODEL_IDS)
def test_clustering_rejects_non_json_nonfinite_or_unrepresentable_numeric_leaves(
    model_id: str, value: object, suffix: str
) -> None:
    """Unsafe leaves must fail at their exact matrix position before numeric conversion."""
    payload = _payload_for(model_id)
    payload["X"] = [[value], [0.0]]
    _assert_execution_error(model_id, payload, f"X{suffix}")


@pytest.mark.parametrize("model_id", MODEL_IDS)
def test_clustering_exact_binary64_integer_boundary_is_accepted(model_id: str) -> None:
    """The exact 2**53 integer remains a distinct, safe public numeric value."""
    payload = _payload_for(model_id)
    payload["X"] = [[0], [2**53]]
    if model_id == "kmeans":
        payload["params"] = {"n_clusters": 2}
    elif model_id == "dbscan":
        payload["params"] = {"eps": 1.0, "min_samples": 1}
    else:
        payload["params"] = {"n_clusters": 2}

    result = execute(model_id, payload)
    assert json.loads(json.dumps(result, allow_nan=False)) == result


@pytest.mark.parametrize("model_id", MODEL_IDS)
def test_clustering_neighboring_lossy_binary64_integer_is_rejected(model_id: str) -> None:
    """2**53+1 must not collapse onto its binary64 neighbor during array conversion."""
    payload = _payload_for(model_id)
    payload["X"] = [[0], [2**53 + 1]]
    _assert_execution_error(model_id, payload, "X[1][0]")


@pytest.mark.parametrize("model_id", MODEL_IDS)
def test_clustering_payload_and_nested_container_subclasses_are_rejected(model_id: str) -> None:
    """Container subclass hooks must never cross the strict plain-JSON snapshot boundary."""

    class DictSubclass(dict[str, object]):
        pass

    class ListSubclass(list[object]):
        pass

    with pytest.raises(
        ValueError,
        match=rf"{re.escape(model_id)}: payload stage failed: payload must be a plain JSON object",
    ):
        execute(model_id, DictSubclass(_payload_for(model_id)))

    payload = _payload_for(model_id)
    payload["X"] = ListSubclass([[0.0], [1.0]])
    _assert_execution_error(model_id, payload, "X")

    payload = _payload_for(model_id)
    payload["params"] = DictSubclass()
    _assert_execution_error(model_id, payload, "params")


@pytest.mark.parametrize("model_id", MODEL_IDS)
def test_clustering_numeric_subclasses_are_rejected_without_conversion(model_id: str) -> None:
    """A numeric subclass must not run conversion hooks after being mistaken for a JSON number."""

    class FloatSubclass(float):
        def __float__(self) -> float:
            raise AssertionError("conversion hook must not run")

    payload = _payload_for(model_id)
    payload["X"] = [[FloatSubclass(1.0)], [2.0]]
    _assert_execution_error(model_id, payload, "X[0][0]")


@pytest.mark.parametrize("model_id", MODEL_IDS)
def test_clustering_rejects_non_string_json_object_keys(model_id: str) -> None:
    """JSON objects with numeric keys must fail before unknown-parameter sorting or sklearn."""
    payload = _payload_for(model_id)
    payload["params"] = {1: 2}
    _assert_execution_error(model_id, payload, "params")


@pytest.mark.parametrize("model_id", MODEL_IDS)
def test_clustering_rejects_unknown_top_level_fields_and_non_boolean_standardized(
    model_id: str,
) -> None:
    """Misspelled fields and numeric truthiness must not silently change scale diagnostics."""
    payload = _payload_for(model_id)
    payload["extra"] = 1
    _assert_execution_error(model_id, payload, "extra")

    for value in (0, 1, None, "true"):
        payload = _payload_for(model_id)
        payload["standardized"] = value
        _assert_execution_error(model_id, payload, "standardized")


@pytest.mark.parametrize("model_id", MODEL_IDS)
def test_clustering_missing_X_fails_at_payload_fields_stage(model_id: str) -> None:
    """Registration must advertise X as required so missing input fails before execution."""
    payload = _payload_for(model_id)
    del payload["X"]
    with pytest.raises(
        ValueError,
        match=rf"{re.escape(model_id)}: payload fields stage failed: missing X",
    ):
        execute(model_id, payload)


@pytest.mark.parametrize("model_id", MODEL_IDS)
def test_clustering_execution_does_not_mutate_reused_payload(model_id: str) -> None:
    """Estimator fitting and normalization must leave payload, rows, and params reusable."""
    payload = _payload_for(model_id)
    before = copy.deepcopy(payload)
    first = execute(model_id, payload)
    second = execute(model_id, payload)

    assert payload == before
    assert first == second


@pytest.mark.parametrize("model_id", MODEL_IDS)
def test_clustering_results_are_finite_plain_json_without_estimators(model_id: str) -> None:
    """The modern path must round-trip strict JSON and never expose fitted objects."""
    result = execute(model_id, _payload_for(model_id))

    assert json.loads(json.dumps(result, allow_nan=False)) == result
    _assert_finite_plain_json(result)
    _assert_no_estimator(result)
    assert result["executor"] == "clustering"


@pytest.mark.parametrize("model_id", ["dbscan", "hierarchical-clustering"])
def test_deterministic_clustering_results_repeat_exactly(model_id: str) -> None:
    """Deterministic metadata requires byte-equivalent normalized results on reused inputs."""
    payload = _payload_for(model_id)
    first = execute(model_id, payload)
    second = execute(model_id, payload)

    assert first == second
    assert first["reproducibility"] == {"seed": None, "deterministic": True}


@pytest.mark.parametrize(
    ("model_id", "params"),
    [
        ("kmeans", {"n_clusters": 2}),
        ("dbscan", {"eps": 1e99, "min_samples": 1}),
        ("hierarchical-clustering", {"n_clusters": 2}),
    ],
)
def test_clustering_safe_extreme_scale_remains_finite(
    model_id: str, params: dict[str, object]
) -> None:
    """Large but distance-safe binary64 values must not be rejected by an arbitrary low cap."""
    result = execute(model_id, {"X": [[-1e100], [1e100]], "params": params, **({"seed": 0} if model_id == "kmeans" else {})})
    _assert_finite_plain_json(result)


@pytest.mark.parametrize("model_id", MODEL_IDS)
def test_clustering_unsafe_extreme_scale_fails_without_warning(model_id: str) -> None:
    """Overflow-prone finite coordinates must fail before pairwise-distance warnings leak."""
    payload = _payload_for(model_id)
    payload["X"] = [[-1e308], [1e308]]
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        _assert_execution_error(model_id, payload, "X")
    assert caught == []


class _FakeKMeans:
    def __init__(self) -> None:
        self.labels_: object = np.array([0, 0, 1, 1])
        self.cluster_centers_: object = np.array([[0.0], [10.0]])
        self.inertia_: object = 1.0
        self.n_iter_: object = 2

    def fit(self, X: np.ndarray) -> _FakeKMeans:
        return self


@pytest.mark.parametrize(
    ("attribute", "value", "field"),
    [
        ("labels_", np.array([[0, 1]]), "labels"),
        ("labels_", np.array([0, 1, 0]), "labels"),
        ("labels_", np.array([0.0, 0.0, 1.5, 1.0]), "labels"),
        ("labels_", np.array([0.0, 0.0, np.nan, 1.0]), "labels"),
        ("labels_", np.array([0, 0, 2, 2]), "labels"),
        ("labels_", np.array([0, 0, 0, 0]), "cluster_count"),
        ("cluster_centers_", np.array([[0.0, 1.0], [10.0, 11.0]]), "cluster_centers"),
        ("cluster_centers_", np.array([[0.0], [np.inf]]), "cluster_centers"),
        ("cluster_centers_", np.array([["0.0"], ["10.0"]]), "cluster_centers"),
        ("cluster_centers_", np.array([[True], [False]]), "cluster_centers"),
        (
            "cluster_centers_",
            np.array([[0.0 + 1.0j], [10.0 + 2.0j]]),
            "cluster_centers",
        ),
        ("inertia_", -1.0, "inertia"),
        ("inertia_", float("inf"), "inertia"),
        ("n_iter_", 0, "iteration_count"),
        ("n_iter_", 1.5, "iteration_count"),
    ],
)
def test_kmeans_malformed_or_nonfinite_fitted_outputs_fail_closed(
    monkeypatch: pytest.MonkeyPatch, attribute: str, value: object, field: str
) -> None:
    """Every fitted attribute must be shape-, type-, and finiteness-checked before JSON."""
    estimator = _FakeKMeans()
    setattr(estimator, attribute, value)
    monkeypatch.setattr(
        legacy_registry,
        "get_model",
        lambda name: lambda *, seed, params: estimator,
    )
    payload = {"X": [[0.0], [0.1], [10.0], [10.1]], "params": {"n_clusters": 2}}
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        _assert_execution_error("kmeans", payload, field)
    assert caught == []


@pytest.mark.parametrize(
    "labels",
    [np.array([[0, 1]]), np.array([0, 1]), np.array([0.0, 1.5, 1.0, 0.0]), np.array([0.0, np.nan, 1.0, 1.0])],
)
@pytest.mark.parametrize("model_id", ["dbscan", "hierarchical-clustering"])
def test_non_kmeans_malformed_labels_fail_closed(
    monkeypatch: pytest.MonkeyPatch, model_id: str, labels: np.ndarray
) -> None:
    """Canonicalization must reject wrong length, dimensions, fractional, and nonfinite labels."""
    module = _clustering_module()

    class FakeEstimator:
        labels_ = labels

        def __init__(self, **params: object) -> None:
            pass

        def fit(self, X: np.ndarray) -> FakeEstimator:
            return self

    monkeypatch.setattr(
        module,
        "DBSCAN" if model_id == "dbscan" else "AgglomerativeClustering",
        FakeEstimator,
    )
    _assert_execution_error(model_id, _payload_for(model_id), "labels")


@pytest.mark.parametrize(
    "bad_linkage",
    [
        np.zeros((2, 4)),
        np.array([[0.0, 1.0, np.nan, 2.0], [2.0, 4.0, 1.0, 2.0], [3.0, 5.0, 2.0, 4.0]]),
        np.array([[0.0, 1.0, -1.0, 2.0], [2.0, 4.0, 1.0, 3.0], [3.0, 5.0, 2.0, 4.0]]),
        np.array([[0.5, 1.0, 0.1, 2.0], [2.0, 4.0, 1.0, 3.0], [3.0, 5.0, 2.0, 4.0]]),
        np.array([[0.0, 4.0, 0.1, 2.0], [1.0, 2.0, 1.0, 2.0], [3.0, 5.0, 2.0, 4.0]]),
        np.array([[0.0, 1.0, 0.1, 3.0], [2.0, 4.0, 1.0, 3.0], [3.0, 5.0, 2.0, 4.0]]),
        np.array(
            [
                ["0", "1", "0.1", "2"],
                ["2", "3", "0.1", "2"],
                ["4", "5", "5.0", "4"],
            ]
        ),
        np.array(
            [
                [0.0, 1.0, 0.1 + 1.0j, 2.0],
                [2.0, 3.0, 0.1 + 1.0j, 2.0],
                [4.0, 5.0, 5.0 + 1.0j, 4.0],
            ]
        ),
    ],
)
def test_hierarchical_malformed_linkage_output_fails_closed(
    monkeypatch: pytest.MonkeyPatch, bad_linkage: np.ndarray
) -> None:
    """A linkage-shaped array still needs valid indices, distances, and merge counts."""
    module = _clustering_module()
    monkeypatch.setattr(module, "scipy_linkage", lambda *args, **kwargs: bad_linkage)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        _assert_execution_error(
            "hierarchical-clustering", HIERARCHICAL_PAYLOAD, "linkage_matrix"
        )
    assert caught == []


@pytest.mark.parametrize("model_id", MODEL_IDS)
def test_library_warnings_fail_closed_without_leaking(
    monkeypatch: pytest.MonkeyPatch, model_id: str
) -> None:
    """Convergence, runtime, and other library warnings must become fielded failures."""
    module = _clustering_module()

    if model_id == "kmeans":
        class WarningEstimator(_FakeKMeans):
            def fit(self, X: np.ndarray) -> WarningEstimator:
                warnings.warn("did not converge", ConvergenceWarning)
                return self

        monkeypatch.setattr(
            legacy_registry,
            "get_model",
            lambda name: lambda *, seed, params: WarningEstimator(),
        )
    else:
        class WarningEstimator:
            labels_ = np.array([0, 0, 1, 1])

            def __init__(self, **params: object) -> None:
                pass

            def fit(self, X: np.ndarray) -> WarningEstimator:
                category = RuntimeWarning if model_id == "dbscan" else UserWarning
                warnings.warn("library warning", category)
                return self

        monkeypatch.setattr(
            module,
            "DBSCAN" if model_id == "dbscan" else "AgglomerativeClustering",
            WarningEstimator,
        )

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        _assert_execution_error(model_id, _payload_for(model_id), "fit")
    assert caught == []


@pytest.mark.parametrize("model_id", ["dbscan", "hierarchical-clustering"])
def test_post_fit_attribute_warnings_fail_closed_without_leaking(
    monkeypatch: pytest.MonkeyPatch, model_id: str
) -> None:
    """Warnings raised while reading fitted labels must stay inside the executor."""
    module = _clustering_module()

    class WarningAttributeEstimator:
        def __init__(self, **params: object) -> None:
            pass

        def fit(self, X: np.ndarray) -> WarningAttributeEstimator:
            return self

        @property
        def labels_(self) -> np.ndarray:
            warnings.warn("attribute warning", RuntimeWarning)
            return np.array([0, 0, 1, 1])

    monkeypatch.setattr(
        module,
        "DBSCAN" if model_id == "dbscan" else "AgglomerativeClustering",
        WarningAttributeEstimator,
    )
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        _assert_execution_error(model_id, _payload_for(model_id), "fitted attributes")
    assert caught == []


@pytest.mark.parametrize("model_id", MODEL_IDS)
def test_handled_library_exceptions_are_translated_with_stage_context(
    monkeypatch: pytest.MonkeyPatch, model_id: str
) -> None:
    """Expected numerical/library errors must not escape as raw sklearn or SciPy exceptions."""
    module = _clustering_module()

    if model_id == "kmeans":
        monkeypatch.setattr(
            legacy_registry,
            "get_model",
            lambda name: lambda *, seed, params: (_ for _ in ()).throw(TypeError("bad params")),
        )
        field = "params"
    elif model_id == "dbscan":
        class BrokenDBSCAN:
            def __init__(self, **params: object) -> None:
                pass

            def fit(self, X: np.ndarray) -> None:
                raise RuntimeError("bad fit")

        monkeypatch.setattr(module, "DBSCAN", BrokenDBSCAN)
        field = "fit"
    else:
        monkeypatch.setattr(
            module,
            "scipy_linkage",
            lambda *args, **kwargs: (_ for _ in ()).throw(ValueError("bad linkage")),
        )
        field = "linkage"

    _assert_execution_error(model_id, _payload_for(model_id), field)


def test_programming_defects_are_not_misreported_as_user_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Catching every Exception would conceal an executor integration defect."""

    class DefectiveDBSCAN:
        def __init__(self, **params: object) -> None:
            pass

        def fit(self, X: np.ndarray) -> None:
            raise KeyError("internal invariant")

    monkeypatch.setattr(_clustering_module(), "DBSCAN", DefectiveDBSCAN)
    with pytest.raises(KeyError, match="internal invariant"):
        execute("dbscan", copy.deepcopy(DBSCAN_PAYLOAD))


def test_kmeans_legacy_and_json_interfaces_coexist() -> None:
    """The estimator-returning runner must remain intact beside the strict JSON executor."""
    legacy = run_model(
        "kmeans",
        KMEANS_PAYLOAD["X"],
        None,
        seed=7,
        params={"n_clusters": 2, "n_init": 10},
    )
    modern = execute("kmeans", copy.deepcopy(KMEANS_PAYLOAD))

    assert set(legacy) == {"model", "fitted", "params", "seed"}
    assert legacy["model"] == "kmeans"
    assert hasattr(legacy["fitted"], "predict")
    assert modern["result"]["cluster_count"] == 2
    _assert_no_estimator(modern)


@pytest.mark.parametrize(
    ("model_id", "card", "deterministic", "seed_supported"),
    [
        ("kmeans", "shared/knowledge/model-cards/classification/kmeans.md", False, True),
        ("dbscan", "shared/knowledge/model-cards/classification/dbscan.md", True, False),
        (
            "hierarchical-clustering",
            "shared/knowledge/model-cards/classification/hierarchical-clustering.md",
            True,
            False,
        ),
    ],
)
def test_clustering_capabilities_are_registered_exactly(
    project_root: Path,
    model_id: str,
    card: str,
    deterministic: bool,
    seed_supported: bool,
) -> None:
    """Wrong executor, required fields, seed facts, or card paths would misroute callers."""
    capabilities = {item["model_id"]: item for item in list_capabilities()}
    capability = capabilities[model_id]

    assert capability == {
        "model_id": model_id,
        "executor": "clustering",
        "knowledge_card": card,
        "deterministic": deterministic,
        "seed_supported": seed_supported,
        "payload_fields": ("X",),
    }
    assert (project_root / card).is_file()
    assert get_spec(model_id).function is not None


def test_clustering_cards_validate_and_match_catalog(project_root: Path) -> None:
    """Executable registrations need schema-valid cards with matching catalog identities."""
    schema = json.loads(
        (project_root / "shared/knowledge/model-card.schema.json").read_text(encoding="utf-8")
    )
    validator = jsonschema.Draft202012Validator(schema)
    catalog = yaml.safe_load(
        (project_root / "shared/knowledge/model-catalog.yaml").read_text(encoding="utf-8")
    )
    entries = {entry["model_id"]: entry for entry in catalog["cards"]}

    for model_id in MODEL_IDS:
        spec = get_spec(model_id)
        text = (project_root / spec.knowledge_card).read_text(encoding="utf-8")
        front_matter = yaml.safe_load(text.split("---", 2)[1])
        assert list(validator.iter_errors(front_matter)) == []
        assert front_matter["model_id"] == model_id
        assert front_matter["file"] == spec.knowledge_card
        assert entries[model_id]["file"] == spec.knowledge_card
