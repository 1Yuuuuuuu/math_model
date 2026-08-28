"""Neutral sklearn estimator constructors shared by legacy and JSON runtimes."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

from sklearn.cluster import KMeans
from sklearn.linear_model import LinearRegression, LogisticRegression
from sklearn.tree import DecisionTreeClassifier


EstimatorFactory = Callable[..., Any]


def seed_kwargs(seed: int | None, params: Mapping[str, Any]) -> dict[str, Any]:
    """Copy estimator parameters and apply one unambiguous random state."""
    kwargs = dict(params)
    if seed is not None:
        if "random_state" in kwargs:
            raise ValueError("conflict: both seed and random_state provided")
        kwargs["random_state"] = seed
    return kwargs


def linear_regression_factory(
    seed: int | None, params: Mapping[str, Any]
) -> LinearRegression:
    """Construct the deterministic legacy linear-regression estimator."""
    return LinearRegression(**dict(params))


def decision_tree_factory(
    seed: int | None, params: Mapping[str, Any]
) -> DecisionTreeClassifier:
    """Construct a decision tree with shared seed semantics."""
    return DecisionTreeClassifier(**seed_kwargs(seed, params))


def kmeans_factory(seed: int | None, params: Mapping[str, Any]) -> KMeans:
    """Construct KMeans with the legacy three-cluster default."""
    kwargs = seed_kwargs(seed, params)
    kwargs.setdefault("n_clusters", 3)
    return KMeans(**kwargs)


def logistic_regression_factory(
    seed: int | None, params: Mapping[str, Any]
) -> LogisticRegression:
    """Construct the modern logistic-regression capability."""
    return LogisticRegression(**seed_kwargs(seed, params))


_FACTORIES: dict[str, EstimatorFactory] = {
    "linear-regression": linear_regression_factory,
    "decision-tree": decision_tree_factory,
    "kmeans": kmeans_factory,
    "logistic-regression": logistic_regression_factory,
}


def get_estimator_factory(model_id: str) -> EstimatorFactory:
    """Return one immutable-by-convention built-in estimator constructor."""
    try:
        return _FACTORIES[model_id]
    except KeyError as exc:
        raise KeyError(f"unknown estimator factory: {model_id}") from exc
