from __future__ import annotations

from typing import Any, Callable

from .estimator_factories import (
    decision_tree_factory,
    kmeans_factory,
    linear_regression_factory,
    seed_kwargs as _seed_kwargs,
)

_REGISTRY: dict[str, Callable[..., Any]] = {}


def register_model(name: str, factory: Callable[..., Any]) -> None:
    if not isinstance(name, str) or not name:
        raise ValueError("model name must be a non-empty string")
    _REGISTRY[name] = factory


def list_models() -> list[str]:
    return sorted(_REGISTRY)


def get_model(name: str) -> Callable[..., Any]:
    if name not in _REGISTRY:
        raise KeyError(f"unknown model: {name}")
    return _REGISTRY[name]


def _register_builtins() -> None:
    register_model("linear-regression", linear_regression_factory)
    register_model("decision-tree", decision_tree_factory)
    register_model("kmeans", kmeans_factory)


_register_builtins()
