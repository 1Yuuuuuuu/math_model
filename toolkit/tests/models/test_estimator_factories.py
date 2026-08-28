from __future__ import annotations

import pytest
from sklearn.cluster import KMeans
from sklearn.linear_model import LinearRegression, LogisticRegression
from sklearn.tree import DecisionTreeClassifier

from cumcm_toolkit.models.estimator_factories import get_estimator_factory


@pytest.mark.parametrize(
    ("model_id", "seed", "params", "estimator_type", "expected"),
    [
        (
            "linear-regression",
            None,
            {"fit_intercept": False},
            LinearRegression,
            {"fit_intercept": False},
        ),
        (
            "decision-tree",
            7,
            {"max_depth": 2},
            DecisionTreeClassifier,
            {"max_depth": 2, "random_state": 7},
        ),
        (
            "kmeans",
            11,
            {},
            KMeans,
            {"n_clusters": 3, "random_state": 11},
        ),
        (
            "logistic-regression",
            13,
            {"C": 0.5},
            LogisticRegression,
            {"C": 0.5, "random_state": 13},
        ),
    ],
)
def test_neutral_estimator_factories_preserve_constructor_semantics(
    model_id: str,
    seed: int | None,
    params: dict[str, object],
    estimator_type: type[object],
    expected: dict[str, object],
) -> None:
    """Wrong constructor, seed mapping, or KMeans default changes public estimates."""
    estimator = get_estimator_factory(model_id)(seed=seed, params=params)

    assert isinstance(estimator, estimator_type)
    estimator_params = estimator.get_params()  # type: ignore[attr-defined]
    for name, value in expected.items():
        assert estimator_params[name] == value


@pytest.mark.parametrize(
    "model_id", ["decision-tree", "kmeans", "logistic-regression"]
)
def test_neutral_seeded_factories_reject_random_state_conflicts(
    model_id: str,
) -> None:
    """Allowing seed plus random_state would make reproducibility precedence ambiguous."""
    factory = get_estimator_factory(model_id)

    with pytest.raises(
        ValueError, match="conflict: both seed and random_state provided"
    ):
        factory(seed=7, params={"random_state": 3})


def test_neutral_factory_lookup_rejects_unknown_models() -> None:
    """Falling back to a constructor would silently run the wrong estimator family."""
    with pytest.raises(KeyError, match="unknown estimator factory: absent-model"):
        get_estimator_factory("absent-model")
